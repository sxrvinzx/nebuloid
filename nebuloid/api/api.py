from quart import make_response, jsonify
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
import base64, os
import secrets
import json

from .auth import NebuloidAuth
from .data import NebuloidDataAPI

def aes_encrypt(aes_key_bytes: bytes, plaintext: str) -> dict:
    # Generate random 96-bit (12 byte) nonce
    nonce = os.urandom(12)
    aesgcm = AESGCM(aes_key_bytes)

    # Encrypt (plaintext must be bytes)
    ciphertext = aesgcm.encrypt(nonce, plaintext.encode(), None)

    return {
        "nonce": base64.b64encode(nonce).decode(),
        "ciphertext": base64.b64encode(ciphertext).decode()
    }


def aes_decrypt(aes_key_bytes: bytes, data: dict) -> str:
    nonce = base64.b64decode(data["nonce"])
    ciphertext = base64.b64decode(data["ciphertext"])

    aesgcm = AESGCM(aes_key_bytes)
    plaintext_bytes = aesgcm.decrypt(nonce, ciphertext, None)

    return plaintext_bytes.decode()


class NebuloidAPI:
    def __init__(self, services):
        services.inject_services(self)

        self.auth = NebuloidAuth(services)
        self.dataapi = NebuloidDataAPI(services)
    
    def mount(self):
        private_key = self.storage.file('private_key.pem', "rb")
        with private_key as f:
            self.private_key = serialization.load_pem_private_key(f.read(), password=None)

    async def handle(self, url, content, session_id) -> dict:
        if url != "/api":
            if (existing := await self.orm.get_key(session_id)) is not None:
                aes_key = existing.key
            else:
                response = await make_response(jsonify({"error": "invalid_session"}), 403)

                response.set_cookie(
                    "session_id",
                    value="",
                    max_age=0,
                    expires=0,
                    path="/",
                    secure=True,
                    httponly=True,
                    samesite="Lax"
                )

                return response

            api_name = url[5:]

            data = aes_decrypt(aes_key, json.loads(content).get("data"))

            resp_data, resp_code =  await self.handle_raw(api_name, json.loads(data), session_id=session_id)
            return await make_response(jsonify(aes_encrypt(aes_key, json.dumps(resp_data))), resp_code)
        data = json.loads(content).get("data")
        
        # Decrypt
        decrypted = self.private_key.decrypt(
            base64.b64decode(data),
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None
            )
        )
        data = json.loads(decrypted.decode())


        if not session_id:
            session_id = secrets.token_urlsafe(32)
            await self.orm.add_key(session_id, base64.b64decode(data['key']))
        else:
            if existing := await self.orm.get_key(session_id):
                await self.orm.update_key(session_id, base64.b64decode(data['key']))
            else:
                await self.orm.add_key(session_id, base64.b64decode(data['key']))

        resp_data = {'info': "com_ok", "session": session_id}

        response = await make_response(jsonify(aes_encrypt(base64.b64decode(data['key']), json.dumps(resp_data))), 200)

        response.set_cookie(
            "session_id",               # cookie name
            value=session_id,           # cookie value
            max_age=3600,               # optional, seconds
            httponly=True,              # cannot be accessed by JS
            secure=True,                # HTTPS only
            samesite="Lax"              # Lax/Strict/None
        )

        return response
    
    async def handle_raw(self, api_name, data, session_id=None, user_id=None):
        if api_name == "auth":
            resp_data = await self.auth.handle(data, session_id)
        elif api_name == "data":
            resp_data = await self.dataapi.handle(data, session_id=session_id, user_id=user_id)
            print("Data API response:", resp_data)
        else:
            return {"error": "unknown_api"}, 404
        print(resp_data)
        return resp_data, 200