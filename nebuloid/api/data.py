import json
import inspect

from .context import NebuloidContext
class NebuloidDataAPI:
    def __init__(self, services):
        services.inject_services(self)
    
    async def handle(self, data, session_id=None, user_id=None) -> dict:
        if isinstance(data, str):
            data = json.loads(data)
        print("Data API called with data:", data, "Session ID:", session_id)

        # Example: simple "add" operation
        print("Available functions:", self.manifest.func_registry['portal'].keys())
        if data.get("name") in self.manifest.func_registry['portal'].keys():
            print("data", data.get("args", {}))
            context = NebuloidContext(self.services, data.get("args", {}))
            if session_id:
                resp = await self.orm.get_user_profile(session_id=session_id)
            elif user_id:
                resp = await self.orm.get_user_profile(user_id=user_id)
            else:
                resp = {"status": "error", "message": "No session_id or user_id provided"}
            print("User profile response:", resp)
            context.user = resp.get("data", [{}])[0]
            try:
                result = self.manifest.func_registry['portal'][data.get("name")](context)
                if inspect.isawaitable(result):
                    result = await result
            except Exception as e:
                print("Error executing function:", e)
                return {"status": "error", "message": str(e)}
            print("Function result:", result)
            return {"status": "success", "result": result}
        return {"status": "error", "message": "Data API not implemented yet."}