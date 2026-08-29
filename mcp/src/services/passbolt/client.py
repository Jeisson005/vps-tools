import os
import re
import json
import time
import hmac
import base64
import struct
import hashlib
import logging
import urllib.parse
from typing import Dict, Any, List, Optional
import httpx

logger = logging.getLogger("mcp.passbolt")

def generate_totp(secret: str, digits: int = 6, period: int = 30) -> Dict[str, Any]:
    """Generate RFC 6238 TOTP code using standard library."""
    if not secret:
        return {}
    try:
        # Extract secret if otpauth URI provided
        if secret.startswith("otpauth://"):
            parsed = urllib.parse.urlparse(secret)
            qs = urllib.parse.parse_qs(parsed.query)
            secret = qs.get("secret", [secret])[0]
            if "digits" in qs:
                digits = int(qs["digits"][0])
            if "period" in qs:
                period = int(qs["period"][0])

        # Clean secret (remove spaces, padding)
        clean_secret = secret.replace(" ", "").upper()
        missing_padding = len(clean_secret) % 8
        if missing_padding:
            clean_secret += "=" * (8 - missing_padding)

        key = base64.b32decode(clean_secret, casefold=True)
        current_time = int(time.time())
        time_step = current_time // period
        time_remaining = period - (current_time % period)

        msg = struct.pack(">Q", time_step)
        h = hmac.new(key, msg, hashlib.sha1).digest()
        offset = h[-1] & 0x0F
        code_int = struct.unpack(">I", h[offset:offset+4])[0] & 0x7FFFFFFF
        code = str(code_int % (10 ** digits)).zfill(digits)

        return {
            "code": code,
            "expires_in_seconds": time_remaining,
            "period": period,
            "digits": digits
        }
    except Exception as e:
        logger.debug(f"Failed to generate TOTP: {e}")
        return {"error": str(e)}

class PassboltClient:
    """Complete Passbolt API Client with GPG authentication, CRUD, and TOTP support."""

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

        try:
            import gnupg
            gpg = gnupg.GPG()
            gpg.import_keys(self.private_key_armored)
            decrypted = gpg.decrypt(armored_text, passphrase=self.passphrase)
            if decrypted.ok:
                return str(decrypted.data.decode("utf-8", errors="ignore"))
        except Exception as e:
            logger.debug(f"gnupg decrypt attempt: {e}")

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

    def encrypt_pgp_message(self, plaintext: str) -> str:
        """Encrypt message using user's OpenPGP public key."""
        fp = self._extract_fingerprint_from_key()
        try:
            import gnupg
            gpg = gnupg.GPG()
            gpg.import_keys(self.private_key_armored)
            enc = gpg.encrypt(plaintext, recipients=[fp], always_trust=True)
            if enc.ok:
                return str(enc)
        except Exception as e:
            logger.debug(f"gnupg encrypt attempt: {e}")

        try:
            import pgpy
            key, _ = pgpy.PGPKey.from_blob(self.private_key_armored)
            pubkey = key.pubkey
            msg = pgpy.PGPMessage.new(plaintext)
            enc = pubkey.encrypt(msg)
            return str(enc)
        except Exception as e:
            logger.debug(f"PGPy encrypt attempt: {e}")

        raise RuntimeError("Failed to encrypt OpenPGP payload.")

    async def _login(self, client: httpx.AsyncClient) -> bool:
        """Perform Passbolt GPGAuth challenge-response authentication and retrieve session."""
        fp = self._extract_fingerprint_from_key()
        if not fp:
            raise ValueError("Could not extract GPG fingerprint from private key.")

        login_url = f"{self.base_url}/auth/login.json"

        # Stage 1: Challenge
        stage1_res = await client.post(
            login_url,
            json={"gpg_auth": {"keyid": fp}},
            headers={"Accept": "application/json"}
        )
        if stage1_res.status_code != 200:
            raise RuntimeError(f"Passbolt challenge request failed (HTTP {stage1_res.status_code}): {stage1_res.text}")

        raw_token = stage1_res.headers.get("X-GPGAuth-User-Auth-Token")
        if not raw_token:
            # Fallback
            verify_res = await client.post(
                f"{self.base_url}/auth/verify.json",
                json={"data": {"gpg_auth": {"keyid": fp}}},
                headers={"Accept": "application/json"}
            )
            raw_token = verify_res.headers.get("X-GPGAuth-User-Auth-Token")

        if not raw_token:
            raise RuntimeError("Passbolt server did not return challenge header X-GPGAuth-User-Auth-Token.")

        # Stage 2: Decrypt
        cleaned_token = urllib.parse.unquote(raw_token).replace(r"\+", " ")
        decrypted_token = self.decrypt_pgp_message(cleaned_token).strip()
        if not decrypted_token:
            raise RuntimeError("Failed to decrypt authentication challenge nonce with private key.")

        # Stage 3: Verification
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

        # Obtain CSRF token for mutating requests
        await client.get(f"{self.base_url}/users/me.json", headers={"Accept": "application/json"})
        return True

    def _get_csrf_headers(self, client: httpx.AsyncClient) -> Dict[str, str]:
        csrf = client.cookies.get("csrfToken") or ""
        return {
            "Accept": "application/json",
            "X-CSRF-Token": csrf
        }

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
                
                res_check = await client.get(f"{self.base_url}/resources.json", headers={"Accept": "application/json"})
                vault_count = len(res_check.json().get("body", [])) if res_check.status_code == 200 else 0

                return {
                    "ok": True,
                    "message": "¡Conexión y autenticación criptográfica GPG exitosa con Passbolt!",
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
        """Search and list resources with metadata decryption (without exposing plaintext passwords in list)."""
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
        """Fetch and decrypt secret (password, username, uri, TOTP, custom fields) for a resource UUID."""
        async with httpx.AsyncClient(verify=self.verify_ssl, timeout=20.0) as client:
            await self._login(client)

            # 1. Fetch resource metadata
            res_url = f"{self.base_url}/resources/{resource_id}.json"
            res = await client.get(res_url, headers={"Accept": "application/json"})
            if res.status_code != 200:
                raise RuntimeError(f"Resource not found or access denied ({res.status_code})")

            resource_info = res.json().get("body", {})
            name = resource_info.get("name") or ""
            username = resource_info.get("username") or ""
            uri = resource_info.get("uri") or ""
            description = resource_info.get("description") or ""

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
            totp_info = {}

            # Handle Passbolt v4 / v5 secret JSON format & TOTP
            try:
                sec_json = json.loads(decrypted_raw)
                if isinstance(sec_json, dict):
                    password = sec_json.get("password") or password
                    custom_fields = sec_json.get("custom_fields") or {}
                    
                    totp_data = sec_json.get("totp")
                    if totp_data:
                        totp_secret = totp_data.get("secret_key") if isinstance(totp_data, dict) else str(totp_data)
                        totp_info = generate_totp(totp_secret)
            except Exception:
                pass

            # Check if URI or description has otpauth://
            if not totp_info:
                for check_str in [uri, description]:
                    if "otpauth://" in check_str:
                        match = re.search(r"otpauth://[^\s]+", check_str)
                        if match:
                            totp_info = generate_totp(match.group(0))
                            break

            return {
                "id": resource_info.get("id"),
                "name": name,
                "username": username,
                "uri": uri,
                "description": description,
                "password": password,
                "totp": totp_info,
                "custom_fields": custom_fields,
                "folder_id": resource_info.get("folder_parent_id")
            }

    async def create_resource(
        self,
        name: str,
        password: str,
        username: str = "",
        uri: str = "",
        description: str = "",
        folder_id: Optional[str] = None,
        totp_secret: Optional[str] = None,
        custom_fields: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Create a new credential resource in Passbolt with OpenPGP client-side encryption."""
        async with httpx.AsyncClient(verify=self.verify_ssl, timeout=25.0) as client:
            await self._login(client)
            headers = self._get_csrf_headers(client)

            user_id = self._user_info.get("id")
            key_id = self._user_info.get("gpgkey", {}).get("id")

            # Prepare secret data payload
            secret_payload: Dict[str, Any] = {
                "object_type": "PASSBOLT_SECRET_DATA",
                "password": password
            }
            if totp_secret:
                secret_payload["totp"] = {
                    "secret_key": totp_secret,
                    "digits": 6,
                    "algorithm": "SHA1",
                    "period": 30
                }
            if custom_fields:
                secret_payload["custom_fields"] = custom_fields

            enc_secret_str = self.encrypt_pgp_message(json.dumps(secret_payload))

            # Prepare metadata payload
            meta_payload = {
                "object_type": "PASSBOLT_RESOURCE_METADATA",
                "resource_type_id": "dd1f723d-0d1e-513f-8218-4055dc0530d0",
                "name": name,
                "username": username,
                "uris": [uri] if uri else [],
                "description": description
            }
            enc_meta_str = self.encrypt_pgp_message(json.dumps(meta_payload))

            create_body: Dict[str, Any] = {
                "resource_type_id": "dd1f723d-0d1e-513f-8218-4055dc0530d0",
                "metadata_key_id": key_id,
                "metadata_key_type": "user_key",
                "metadata": enc_meta_str,
                "secrets": [
                    {
                        "user_id": user_id,
                        "data": enc_secret_str
                    }
                ]
            }
            if folder_id:
                create_body["folder_parent_id"] = folder_id

            res = await client.post(f"{self.base_url}/resources.json", json=create_body, headers=headers)
            if res.status_code not in (200, 201):
                err_msg = res.json().get("header", {}).get("message") or res.text
                raise RuntimeError(f"Failed to create resource in Passbolt: {err_msg}")

            created_data = res.json().get("body", {})
            return {
                "ok": True,
                "message": f"Credencial '{name}' creada exitosamente en Passbolt.",
                "id": created_data.get("id"),
                "name": name,
                "username": username,
                "uri": uri,
                "folder_id": folder_id
            }

    async def update_resource(
        self,
        resource_id: str,
        name: Optional[str] = None,
        password: Optional[str] = None,
        username: Optional[str] = None,
        uri: Optional[str] = None,
        description: Optional[str] = None,
        folder_id: Optional[str] = None,
        totp_secret: Optional[str] = None,
        custom_fields: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Update an existing credential resource in Passbolt with OpenPGP re-encryption."""
        async with httpx.AsyncClient(verify=self.verify_ssl, timeout=25.0) as client:
            await self._login(client)
            headers = self._get_csrf_headers(client)

            # Get current values first
            current = await self.get_secret(resource_id)
            final_name = name if name is not None else current.get("name", "")
            final_user = username if username is not None else current.get("username", "")
            final_uri = uri if uri is not None else current.get("uri", "")
            final_desc = description if description is not None else current.get("description", "")
            final_pass = password if password is not None else current.get("password", "")
            final_folder = folder_id if folder_id is not None else current.get("folder_id")

            user_id = self._user_info.get("id")
            key_id = self._user_info.get("gpgkey", {}).get("id")

            secret_payload: Dict[str, Any] = {
                "object_type": "PASSBOLT_SECRET_DATA",
                "password": final_pass
            }
            if totp_secret:
                secret_payload["totp"] = {
                    "secret_key": totp_secret,
                    "digits": 6,
                    "algorithm": "SHA1",
                    "period": 30
                }
            if custom_fields is not None:
                secret_payload["custom_fields"] = custom_fields
            elif current.get("custom_fields"):
                secret_payload["custom_fields"] = current.get("custom_fields")

            enc_secret_str = self.encrypt_pgp_message(json.dumps(secret_payload))

            meta_payload = {
                "object_type": "PASSBOLT_RESOURCE_METADATA",
                "resource_type_id": "dd1f723d-0d1e-513f-8218-4055dc0530d0",
                "name": final_name,
                "username": final_user,
                "uris": [final_uri] if final_uri else [],
                "description": final_desc
            }
            enc_meta_str = self.encrypt_pgp_message(json.dumps(meta_payload))

            update_body: Dict[str, Any] = {
                "resource_type_id": "dd1f723d-0d1e-513f-8218-4055dc0530d0",
                "metadata_key_id": key_id,
                "metadata_key_type": "user_key",
                "metadata": enc_meta_str,
                "secrets": [
                    {
                        "user_id": user_id,
                        "data": enc_secret_str
                    }
                ]
            }
            if final_folder:
                update_body["folder_parent_id"] = final_folder

            res = await client.put(f"{self.base_url}/resources/{resource_id}.json", json=update_body, headers=headers)
            if res.status_code not in (200, 201):
                err_msg = res.json().get("header", {}).get("message") or res.text
                raise RuntimeError(f"Failed to update resource in Passbolt: {err_msg}")

            return {
                "ok": True,
                "message": f"Credencial '{final_name}' (ID: {resource_id}) actualizada exitosamente en Passbolt.",
                "id": resource_id,
                "name": final_name,
                "username": final_user,
                "uri": final_uri
            }

    async def delete_resource(self, resource_id: str) -> Dict[str, Any]:
        """Delete / remove a credential resource from Passbolt vault."""
        async with httpx.AsyncClient(verify=self.verify_ssl, timeout=15.0) as client:
            await self._login(client)
            headers = self._get_csrf_headers(client)

            res = await client.delete(f"{self.base_url}/resources/{resource_id}.json", headers=headers)
            if res.status_code not in (200, 204):
                err_msg = res.json().get("header", {}).get("message") or res.text
                raise RuntimeError(f"Failed to delete resource in Passbolt: {err_msg}")

            return {
                "ok": True,
                "message": f"Recurso '{resource_id}' eliminado exitosamente de Passbolt.",
                "id": resource_id
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

    async def create_folder(self, name: str, parent_id: Optional[str] = None) -> Dict[str, Any]:
        """Create a new folder in Passbolt vault."""
        async with httpx.AsyncClient(verify=self.verify_ssl, timeout=15.0) as client:
            await self._login(client)
            headers = self._get_csrf_headers(client)

            body: Dict[str, Any] = {"name": name}
            if parent_id:
                body["folder_parent_id"] = parent_id

            res = await client.post(f"{self.base_url}/folders.json", json=body, headers=headers)
            if res.status_code not in (200, 201):
                err_msg = res.json().get("header", {}).get("message") or res.text
                raise RuntimeError(f"Failed to create folder in Passbolt: {err_msg}")

            created = res.json().get("body", {})
            return {
                "ok": True,
                "message": f"Carpeta '{name}' creada exitosamente.",
                "id": created.get("id"),
                "name": name,
                "parent_id": parent_id
            }
