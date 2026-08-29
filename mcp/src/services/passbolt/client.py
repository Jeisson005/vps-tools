import os
import re
import json
import logging
from typing import Dict, Any, List, Optional
import httpx

logger = logging.getLogger("mcp.passbolt")

class PassboltClient:
    """Passbolt API Client with GPG authentication and decryption."""

    def __init__(
        self,
        base_url: str,
        private_key_armored: str,
        passphrase: str = "",
        server_key_armored: str = "",
        user_email: str = "",
        fingerprint: str = "",
        verify_ssl: bool = True
    ):
        self.base_url = (base_url or "").rstrip("/")
        self.private_key_armored = (private_key_armored or "").strip()
        self.passphrase = passphrase or ""
        self.server_key_armored = (server_key_armored or "").strip()
        self.user_email = user_email or ""
        self.fingerprint = (fingerprint or "").strip()
        self.verify_ssl = verify_ssl
        self._session_cookies: Dict[str, str] = {}
        self._csrf_token: Optional[str] = None
        self._user_info: Optional[Dict[str, Any]] = None

    def is_configured(self) -> bool:
        return bool(self.base_url and self.private_key_armored)

    def _extract_fingerprint_from_key(self) -> str:
        """Extract or normalize fingerprint using PGPy or gnupg if not provided."""
        if self.fingerprint:
            return self.fingerprint.replace(" ", "").upper()
        
        try:
            import pgpy
            key, _ = pgpy.PGPKey.from_blob(self.private_key_armored)
            return str(key.fingerprint).replace(" ", "").upper()
        except Exception:
            pass

        try:
            import gnupg
            gpg = gnupg.GPG()
            import_result = gpg.import_keys(self.private_key_armored)
            if import_result.fingerprints:
                return import_result.fingerprints[0].upper()
        except Exception:
            pass

        return ""

    def decrypt_pgp_message(self, armored_text: str) -> str:
        """Decrypt an OpenPGP encrypted message using the private key & passphrase."""
        if not armored_text:
            return ""

        # Try PGPy first (pure python)
        try:
            import pgpy
            key, _ = pgpy.PGPKey.from_blob(self.private_key_armored)
            if key.is_protected and self.passphrase:
                with key.unlock(self.passphrase):
                    msg = pgpy.PGPMessage.from_blob(armored_text)
                    decrypted = key.decrypt(msg)
                    return decrypted.message if hasattr(decrypted, "message") else str(decrypted)
            else:
                msg = pgpy.PGPMessage.from_blob(armored_text)
                decrypted = key.decrypt(msg)
                return decrypted.message if hasattr(decrypted, "message") else str(decrypted)
        except Exception as pgpy_err:
            logger.debug(f"PGPy decrypt failed, attempting python-gnupg: {pgpy_err}")

        # Fallback to python-gnupg
        try:
            import gnupg
            gpg = gnupg.GPG()
            import_res = gpg.import_keys(self.private_key_armored)
            decrypted_data = gpg.decrypt(armored_text, passphrase=self.passphrase)
            if decrypted_data.ok:
                return str(decrypted_data.data.decode("utf-8", errors="ignore"))
            raise RuntimeError(f"GPG decrypt failed: {decrypted_data.status}")
        except Exception as gnupg_err:
            raise RuntimeError(f"Failed to decrypt with GPG: {gnupg_err}")

    async def _login(self, client: httpx.AsyncClient) -> bool:
        """Perform Passbolt GPG Challenge-Response handshake."""
        fp = self._extract_fingerprint_from_key()
        if not fp:
            raise ValueError("Could not determine GPG fingerprint from private key or config.")

        # Step 1: Request GPG Challenge
        verify_url = f"{self.base_url}/auth/verify.json"
        body = {
            "data": {
                "gpg_auth": {
                    "keyid": fp
                }
            }
        }
        res = await client.post(verify_url, json=body, headers={"Accept": "application/json"})
        if res.status_code != 200:
            raise RuntimeError(f"Verify handshake failed ({res.status_code}): {res.text}")

        verify_json = res.json()
        encrypted_token = verify_json.get("body")
        if not encrypted_token:
            # Check alternative Passbolt response format
            encrypted_token = verify_json.get("data", {}).get("token") or verify_json.get("data")
            if isinstance(encrypted_token, dict):
                encrypted_token = encrypted_token.get("token")

        if not encrypted_token or not isinstance(encrypted_token, str):
            raise RuntimeError(f"Passbolt did not return an encrypted authentication token: {verify_json}")

        # Step 2: Decrypt Challenge Token
        decrypted_token = self.decrypt_pgp_message(encrypted_token).strip()

        # Step 3: Send Decrypted Token to Login
        login_url = f"{self.base_url}/auth/login.json"
        login_body = {
            "data": {
                "gpg_auth": {
                    "keyid": fp,
                    "user_token": decrypted_token
                }
            }
        }
        
        login_res = await client.post(login_url, json=login_body, headers={"Accept": "application/json"})
        if login_res.status_code != 200:
            raise RuntimeError(f"Login authentication failed ({login_res.status_code}): {login_res.text}")

        login_data = login_res.json()
        self._user_info = login_data.get("body", {}).get("User") or login_data.get("data", {}).get("User")
        return True

    async def test_connection(self) -> Dict[str, Any]:
        """Test authentication and connectivity against Passbolt server."""
        if not self.is_configured():
            return {
                "ok": False,
                "message": "Passbolt is not fully configured (missing Server URL or Private Key).",
                "details": {}
            }

        try:
            async with httpx.AsyncClient(verify=self.verify_ssl, timeout=15.0) as client:
                # 1. Health/Check Server Version
                status_url = f"{self.base_url}/auth/verify.json"
                await self._login(client)
                
                user_email = (self._user_info or {}).get("username") or self.user_email or "Authenticated User"
                return {
                    "ok": True,
                    "message": f"Successfully connected and authenticated with Passbolt as {user_email}!",
                    "details": {
                        "user": self._user_info or {"email": user_email},
                        "fingerprint": self._extract_fingerprint_from_key(),
                        "base_url": self.base_url
                    }
                }
        except Exception as e:
            return {
                "ok": False,
                "message": f"Connection test failed: {str(e)}",
                "details": {"error": str(e)}
            }

    async def search_resources(self, query: str = "", folder_id: Optional[str] = None, limit: int = 25) -> List[Dict[str, Any]]:
        """Search resources without exposing plaintext secrets in listing."""
        async with httpx.AsyncClient(verify=self.verify_ssl, timeout=20.0) as client:
            await self._login(client)
            
            params: Dict[str, Any] = {"contain[secret]": "0"}
            if folder_id:
                params["filter[folder_id]"] = folder_id
            if query:
                params["filter[search]"] = query
                
            url = f"{self.base_url}/resources.json"
            res = await client.get(url, params=params, headers={"Accept": "application/json"})
            if res.status_code != 200:
                raise RuntimeError(f"Error fetching resources ({res.status_code}): {res.text}")
                
            body = res.json().get("body", [])
            results = []
            for item in body[:limit]:
                # Sanitize item - NEVER include secret data in search results
                results.append({
                    "id": item.get("id"),
                    "name": item.get("name"),
                    "username": item.get("username"),
                    "uri": item.get("uri"),
                    "description": item.get("description"),
                    "folder_id": item.get("folder_parent_id"),
                    "modified": item.get("modified"),
                })
            return results

    async def get_secret(self, resource_id: str) -> Dict[str, Any]:
        """Fetch and decrypt the secret associated with a specific resource."""
        async with httpx.AsyncClient(verify=self.verify_ssl, timeout=20.0) as client:
            await self._login(client)
            
            # Fetch resource metadata
            res_url = f"{self.base_url}/resources/{resource_id}.json"
            res = await client.get(res_url, headers={"Accept": "application/json"})
            if res.status_code != 200:
                raise RuntimeError(f"Resource not found or access denied ({res.status_code})")
                
            resource_info = res.json().get("body", {})
            
            # Fetch encrypted secret
            sec_url = f"{self.base_url}/secrets/resource/{resource_id}.json"
            sec_res = await client.get(sec_url, headers={"Accept": "application/json"})
            if sec_res.status_code != 200:
                raise RuntimeError(f"Secret not found for resource {resource_id} ({sec_res.status_code})")
                
            sec_body = sec_res.json().get("body", {})
            armored_data = sec_body.get("data")
            if not armored_data:
                raise RuntimeError("Secret response did not contain encrypted data payload.")
                
            decrypted_secret = self.decrypt_pgp_message(armored_data)
            
            return {
                "id": resource_info.get("id"),
                "name": resource_info.get("name"),
                "username": resource_info.get("username"),
                "uri": resource_info.get("uri"),
                "description": resource_info.get("description"),
                "password": decrypted_secret,
                "folder_id": resource_info.get("folder_parent_id")
            }

    async def list_folders(self, parent_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """List folders hierarchy."""
        async with httpx.AsyncClient(verify=self.verify_ssl, timeout=15.0) as client:
            await self._login(client)
            
            url = f"{self.base_url}/folders.json"
            res = await client.get(url, headers={"Accept": "application/json"})
            if res.status_code != 200:
                raise RuntimeError(f"Error fetching folders ({res.status_code}): {res.text}")
                
            body = res.json().get("body", [])
            results = []
            for f in body:
                if parent_id is None or f.get("folder_parent_id") == parent_id:
                    results.append({
                        "id": f.get("id"),
                        "name": f.get("name"),
                        "parent_id": f.get("folder_parent_id"),
                        "personal": f.get("personal", False)
                    })
            return results
