import os
import re
import json
import logging
import urllib.parse
from typing import Dict, Any, List, Optional
import httpx

logger = logging.getLogger("mcp.passbolt")

class PassboltClient:
    """Passbolt API Client with GPG authentication and decryption (Passbolt v3/v4+ compatible)."""

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
        self._user_info: Optional[Dict[str, Any]] = None

    def is_configured(self) -> bool:
        return bool(self.base_url and self.private_key_armored)

    def _extract_fingerprint_from_key(self) -> str:
        """Extract fingerprint from private key or config."""
        if self.fingerprint:
            return self.fingerprint.replace(" ", "").upper()

        try:
            import gnupg
            gpg = gnupg.GPG()
            import_result = gpg.import_keys(self.private_key_armored)
            if import_result.fingerprints:
                return import_result.fingerprints[0].upper()
        except Exception:
            pass

        try:
            import pgpy
            key, _ = pgpy.PGPKey.from_blob(self.private_key_armored)
            return str(key.fingerprint).replace(" ", "").upper()
        except Exception:
            pass

        return ""

    def decrypt_pgp_message(self, armored_text: str) -> str:
        """Decrypt an OpenPGP encrypted message using python-gnupg or PGPy."""
        if not armored_text:
            return ""

        # Method 1: python-gnupg (preferred for system GPG support)
        try:
            import gnupg
            gpg = gnupg.GPG()
            gpg.import_keys(self.private_key_armored)
            decrypted = gpg.decrypt(armored_text, passphrase=self.passphrase)
            if decrypted.ok:
                return str(decrypted.data.decode("utf-8", errors="ignore"))
        except Exception as e:
            logger.debug(f"gnupg decrypt attempt: {e}")

        # Method 2: PGPy (pure python fallback)
        try:
            import pgpy
            key, _ = pgpy.PGPKey.from_blob(self.private_key_armored)
            if key.is_protected and self.passphrase:
                with key.unlock(self.passphrase):
                    msg = pgpy.PGPMessage.from_blob(armored_text)
                    dec = key.decrypt(msg)
                    return dec.message if hasattr(dec, "message") else str(dec)
            else:
                msg = pgpy.PGPMessage.from_blob(armored_text)
                dec = key.decrypt(msg)
                return dec.message if hasattr(dec, "message") else str(dec)
        except Exception as e:
            logger.debug(f"PGPy decrypt attempt: {e}")

        raise RuntimeError("Failed to decrypt OpenPGP payload with provided private key and passphrase.")

    async def _login(self, client: httpx.AsyncClient) -> bool:
        """Perform Passbolt GPGAuth challenge-response authentication."""
        fp = self._extract_fingerprint_from_key()
        if not fp:
            raise ValueError("Could not extract GPG fingerprint from private key. Please check key validity.")

        login_url = f"{self.base_url}/auth/login.json"

        # Stage 1: Request GPG Challenge
        stage1_res = await client.post(
            login_url,
            json={"gpg_auth": {"keyid": fp}},
            headers={"Accept": "application/json"}
        )
        if stage1_res.status_code != 200:
            raise RuntimeError(f"Passbolt challenge request failed (HTTP {stage1_res.status_code}): {stage1_res.text}")

        raw_token = stage1_res.headers.get("X-GPGAuth-User-Auth-Token")
        if not raw_token:
            # Check verify.json fallback
            verify_res = await client.post(
                f"{self.base_url}/auth/verify.json",
                json={"data": {"gpg_auth": {"keyid": fp}}},
                headers={"Accept": "application/json"}
            )
            raw_token = verify_res.headers.get("X-GPGAuth-User-Auth-Token")

        if not raw_token:
            raise RuntimeError("Passbolt server did not return an X-GPGAuth-User-Auth-Token challenge header.")

        # Stage 2: Decrypt challenge token
        cleaned_token = urllib.parse.unquote(raw_token).replace(r"\+", " ")
        decrypted_token = self.decrypt_pgp_message(cleaned_token).strip()
        if not decrypted_token:
            raise RuntimeError("Failed to decrypt authentication challenge nonce with private key.")

        # Stage 3: Submit decrypted nonce (user_token_result)
        stage2_res = await client.post(
            login_url,
            json={"gpg_auth": {"keyid": fp, "user_token_result": decrypted_token}},
            headers={"Accept": "application/json"}
        )
        if stage2_res.status_code != 200:
            raise RuntimeError(f"Passbolt login verification failed (HTTP {stage2_res.status_code}): {stage2_res.text}")

        login_json = stage2_res.json()
        if login_json.get("header", {}).get("status") != "success":
            msg = login_json.get("header", {}).get("message", "Authentication rejected")
            raise RuntimeError(f"Passbolt authentication failed: {msg}")

        self._user_info = login_json.get("body", {})
        return True

    async def test_connection(self) -> Dict[str, Any]:
        """Test live authentication and connectivity against Passbolt server."""
        if not self.is_configured():
            return {
                "ok": False,
                "message": "Passbolt no está configurado (falta URL del servidor o Clave Privada GPG).",
                "details": {}
            }

        try:
            async with httpx.AsyncClient(verify=self.verify_ssl, timeout=15.0) as client:
                await self._login(client)
                
                user = self._user_info or {}
                profile = user.get("profile", {})
                first_name = profile.get("first_name", "")
                last_name = profile.get("last_name", "")
                full_name = f"{first_name} {last_name}".strip()
                username = user.get("username") or self.user_email or "Usuario Autenticado"
                
                # Check resource count in vault
                res_check = await client.get(f"{self.base_url}/resources.json", headers={"Accept": "application/json"})
                vault_count = len(res_check.json().get("body", [])) if res_check.status_code == 200 else 0

                return {
                    "ok": True,
                    "message": f"¡Conexión y autenticación criptográfica GPG exitosa con Passbolt!",
                    "details": {
                        "user": username,
                        "name": full_name or username,
                        "fingerprint": self._extract_fingerprint_from_key(),
                        "vault_resources_count": vault_count,
                        "server_url": self.base_url
                    }
                }
        except Exception as e:
            logger.error(f"Passbolt test connection failed: {e}", exc_info=True)
            return {
                "ok": False,
                "message": f"Error de conexión con Passbolt: {str(e)}",
                "details": {"error": str(e)}
            }

    async def search_resources(self, query: str = "", folder_id: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        """Search and list resources with metadata decryption (without exposing passwords in list)."""
        async with httpx.AsyncClient(verify=self.verify_ssl, timeout=25.0) as client:
            await self._login(client)

            params: Dict[str, Any] = {}
            if folder_id:
                params["filter[folder_id]"] = folder_id

            url = f"{self.base_url}/resources.json"
            res = await client.get(url, params=params, headers={"Accept": "application/json"})
            if res.status_code != 200:
                raise RuntimeError(f"Error fetching resources ({res.status_code}): {res.text}")

            items = res.json().get("body", [])
            results = []
            query_lower = query.lower().strip() if query else ""

            for item in items:
                res_id = item.get("id")
                name = item.get("name") or ""
                username = item.get("username") or ""
                uri = item.get("uri") or ""
                description = item.get("description") or ""

                # Decrypt Passbolt v4+ encrypted metadata if present
                meta_encrypted = item.get("metadata")
                if meta_encrypted and isinstance(meta_encrypted, str) and "BEGIN PGP MESSAGE" in meta_encrypted:
                    try:
                        dec_meta_str = self.decrypt_pgp_message(meta_encrypted)
                        if dec_meta_str:
                            meta_json = json.loads(dec_meta_str)
                            name = meta_json.get("name") or name
                            username = meta_json.get("username") or username
                            uris = meta_json.get("uris", [])
                            if uris:
                                uri = uris[0] if isinstance(uris, list) else str(uris)
                            description = meta_json.get("description") or description
                    except Exception as e:
                        logger.debug(f"Metadata decrypt error for {res_id}: {e}")

                # Query filter matching
                if query_lower:
                    search_space = f"{name} {username} {uri} {description}".lower()
                    if query_lower not in search_space:
                        continue

                results.append({
                    "id": res_id,
                    "name": name,
                    "username": username,
                    "uri": uri,
                    "description": description,
                    "folder_id": item.get("folder_parent_id"),
                    "modified": item.get("modified")
                })

                if len(results) >= limit:
                    break

            return results

    async def get_secret(self, resource_id: str) -> Dict[str, Any]:
        """Fetch and decrypt the secret (password, username, uri) for a specific resource ID."""
        async with httpx.AsyncClient(verify=self.verify_ssl, timeout=20.0) as client:
            await self._login(client)

            # 1. Fetch resource info
            res_url = f"{self.base_url}/resources/{resource_id}.json"
            res = await client.get(res_url, headers={"Accept": "application/json"})
            if res.status_code != 200:
                raise RuntimeError(f"Resource not found or access denied ({res.status_code})")

            resource_info = res.json().get("body", {})
            name = resource_info.get("name") or ""
            username = resource_info.get("username") or ""
            uri = resource_info.get("uri") or ""
            description = resource_info.get("description") or ""

            # Decrypt metadata if encrypted
            meta_encrypted = resource_info.get("metadata")
            if meta_encrypted and isinstance(meta_encrypted, str) and "BEGIN PGP MESSAGE" in meta_encrypted:
                try:
                    dec_meta_str = self.decrypt_pgp_message(meta_encrypted)
                    if dec_meta_str:
                        meta_json = json.loads(dec_meta_str)
                        name = meta_json.get("name") or name
                        username = meta_json.get("username") or username
                        uris = meta_json.get("uris", [])
                        if uris:
                            uri = uris[0] if isinstance(uris, list) else str(uris)
                        description = meta_json.get("description") or description
                except Exception as e:
                    logger.debug(f"Metadata decrypt error for {resource_id}: {e}")

            # 2. Fetch encrypted secret
            sec_url = f"{self.base_url}/secrets/resource/{resource_id}.json"
            sec_res = await client.get(sec_url, headers={"Accept": "application/json"})
            if sec_res.status_code != 200:
                raise RuntimeError(f"Secret not found for resource {resource_id} ({sec_res.status_code})")

            sec_body = sec_res.json().get("body", {})
            armored_data = sec_body.get("data")
            if not armored_data:
                raise RuntimeError("Secret response did not contain encrypted data payload.")

            decrypted_raw = self.decrypt_pgp_message(armored_data)
            password = decrypted_raw
            custom_fields = {}

            # Handle Passbolt v4 secret data JSON format
            try:
                sec_json = json.loads(decrypted_raw)
                if isinstance(sec_json, dict):
                    password = sec_json.get("password") or password
                    custom_fields = sec_json.get("custom_fields") or {}
            except Exception:
                pass

            return {
                "id": resource_info.get("id"),
                "name": name,
                "username": username,
                "uri": uri,
                "description": description,
                "password": password,
                "custom_fields": custom_fields,
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
