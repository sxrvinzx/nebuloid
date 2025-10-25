import bcrypt

def hash_password(plain_password: str) -> str:
    return bcrypt.hashpw(plain_password.encode(), bcrypt.gensalt()).decode()

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode(), hashed_password.encode())
class NebuloidAuth:
    def __init__(self, services):
        services.inject_services(self)

    async def handle(self, data, session_id) -> dict:
        # Ensure data is a dict
        if isinstance(data, str):
            import json
            try:
                data = json.loads(data)
            except json.JSONDecodeError:
                return {"status": "error", "message": "Invalid JSON data."}    

        if data.get("info") == "request_data":
            if data.get("data") == "auth_params":
                return {"info": "auth_params", "data" : {"AUTH_MODE": self.manifest.data['auth']['mode']}}
            else:
                return {"status": "error", "message": "Unknown data request."}
        elif data.get("info") == "authorize":
            username = data.get("username")
            password = data.get("password")
            if not username or not password:
                return {"status": "error", "message": "Username and password required."}

            user = await self.orm.get_user_by_username(username)
            if not user or not verify_password(password, user.password_hash):
                return {"status": "error", "message": "Invalid username or password."}
            
            await self.orm.update_user_login_status(session_id, user.id, True)


            # Generate token (simple example)ss
            token = username
            return {"status": "success", "token": token, "message": "Authorization successful."}

        elif data.get("info") == "signup":
            username = data.get("username")
            password = data.get("password")
            if not username or not password:
                return {"status": "error", "message": "Username and password required."}

            existing_user = await self.orm.get_user_by_username(username)
            if existing_user:
                return {"status": "error", "message": "Username already exists."}

            hashed_password = hash_password(password)
            await self.orm.add_user(username, hashed_password)
            return {"status": "success", "message": "User registered successfully."}
        elif data.get("info") == "logout":
            await self.orm.update_user_login_status(session_id, None, False)
            return {"status": "success", "message": "Logged out successfully."}