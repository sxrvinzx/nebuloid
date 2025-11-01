import importlib.resources as pkg_resources
import mimetypes, io, os
from pathlib import Path
from nebuloid.api import NebuloidAPI
from .access import NebuloidAccess


from nebuloid.builder import NebuloidBuilder

class NebuloidServer:
    def __init__(self, services, base_dir="pages", shared_dir="shared"):
        services.inject_services(self)

        self.app = None
        self.base_dir = base_dir
        self.shared_dir = shared_dir

        self.api = NebuloidAPI(services)
        services.add(api=self.api)

        self.builder = NebuloidBuilder(services, base_dir)
        self.access = NebuloidAccess(services, base_dir)

    def mount(self):
        if not self.app:
            raise RuntimeError("App not attached to server.")

        self.access.mount()
        self.api.mount()
        
        @self.app.route("/", defaults={"path": ""}, methods=["GET", "POST", "PUT", "DELETE"])
        @self.app.route("/<path:path>", methods=["GET", "POST", "PUT", "DELETE"])
        async def catch_all(path):
            if self.use_flask:
                from flask import request, redirect, send_file
            else:
                from quart import request, redirect, send_file
            url = request.path
            method = request.method
            cookies = request.cookies
            query = request.args
            body = self.tools.ensure_sync(request.get_data())

            await self.plugins.hook("on_request", path=path, method=method, cookies=cookies, query=query, body=body)

            print("Request:", method, url, "Cookies:", cookies, "Query:", query, "Body:", body)

            session_id = cookies.get("session_id")

            if url.startswith("/api"):
                return await self.api.handle(url, body, session_id)
            elif url.startswith("/static_"): # /static_<route_name>/<file>
                route_name, file_name = url[8:].rsplit("/", 1)
                mime_type, _ = mimetypes.guess_type(file_name)
                if not mime_type:
                    mime_type = "application/octet-stream"
                print("joiners", self.base_dir, route_name, 'static', file_name)
                file_path = os.path.normpath(os.path.join(self.base_dir, route_name, 'static', file_name)).replace("\\", "/")
                with open(file_path,'rb') as f:
                    datas = io.BytesIO(f.read())

                return await self.tools.maybe_await(send_file(datas, mimetype=mime_type))
            elif url.startswith("/plugin_"): # /plugin_<method>/<file_id>
                method, file_id = url[8:].split("/", 1)
                file_name, file_path = self.manifest.get_file(file_id)
                if not file_name or not file_path or not os.path.exists(file_path):
                    return {"error": "file_not_found"}, 404
                if method == "download":
                    return await self.tools.maybe_await(send_file(
                        file_path,
                        as_attachment=True,
                        attachment_filename=file_name,
                        conditional=True
                    ))
                elif method == "view":
                    mime_type, _ = mimetypes.guess_type(file_name)
                    if not mime_type:
                        mime_type = "application/octet-stream"

                    return await self.tools.maybe_await(send_file(
                        file_path,
                        mimetype=mime_type,
                        conditional=True
                    ))
                else:
                    return {"error": "invalid_method"}, 400
            elif url.startswith("/utils_"):
                file_name = url[7:]
                mime_type, _ = mimetypes.guess_type(file_name)
                if not mime_type:
                    mime_type = "application/octet-stream"
                file_path_in_pkg = pkg_resources.files('nebuloid.utils').joinpath(file_name)

                if file_path_in_pkg.exists():
                    with file_path_in_pkg.open('rb') as f:
                        datas = io.BytesIO(f.read())
                elif (Path(self.shared_dir) / file_name).exists():
                    with open((Path(self.shared_dir) / file_name), 'rb') as f:
                        datas = io.BytesIO(f.read())
                elif (self.storage.dir('utils') / file_name).exists():
                    with open((self.storage.dir('utils') / file_name), 'rb') as f:
                        datas = io.BytesIO(f.read())
                else:
                    raise FileNotFoundError(f"{file_name} not found in nebuloid.utils or current folder")
                return await self.tools.maybe_await(send_file(datas, mimetype=mime_type))

            user_id, user_access_data = await self.orm.get_user_access_data(session_id)

            # Find matching route
            req_route = None
            routes = self.manifest.data['server']['routes'].get(url)
            if routes:
                if isinstance(routes, str):
                    routes = [routes]

                for route_name in routes:
                    access_bool, res = self.access.can_access(route_name, user_access_data)
                    print(f"reason: {res}")
                    if access_bool:
                        req_route = (url, route_name)
                        break
                    elif res == "login_required":
                        return redirect(self.manifest.data['auth']['login_url'])
                    
            if not req_route:
                html = await self.builder.build("404", user_id)
                return html, 404

            _, route_name = req_route

            try:
                html = await self.builder.build(route_name, user_id)
                return html
            except FileNotFoundError as e:
                return str(e), 500
    async def ready(self):
        await self.plugins.hook("before_gen_utils")

        await self.builder.gen_utils({'name':'portal.js', 'args':{'func_names': list(self.manifest.func_registry['portal'].keys())}})
        print("portl data", self.manifest.func_registry)

        public_key = self.storage.file('public_key.pem', "rb")
        with public_key as f:
            await self.builder.gen_utils({'name':'pem.js', 'args':{'key': f.read().decode().strip("\n")}})

        await self.plugins.hook("after_gen_utils")