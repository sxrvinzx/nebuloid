import os, yaml
import requests
import importlib.resources as pkg_resources
from jinja2 import Environment, FileSystemLoader, select_autoescape, Template

class NebuloidBuilder:
    def __init__(self, services, base_dir="pages"):
        services.inject_services(self)

        self.base_dir = base_dir

        # Jinja environment (supports extends/includes)
        self.env = Environment(
            loader=FileSystemLoader([self.base_dir,"shared"]),
            autoescape=select_autoescape(["html", "jinja"])
        )

    async def build(self, route_name: str, user_id) -> str:
        recipe_file = os.path.join(self.base_dir, route_name, "recipe.yaml")
        if not os.path.exists(recipe_file):
            raise FileNotFoundError(f"Recipe not found for route '{route_name}'")

        with open(recipe_file, "r") as f:
            recipe_data = yaml.safe_load(f) or {}

        page_data = recipe_data.get("page", {})
        template_name = page_data.get("template")
        meta_data = recipe_data.get("data")
        
        datas = await self.get_data(meta_data['sources'], user_id) if meta_data else {}

        print("data fetched:", datas)

        if not template_name:
            raise ValueError(f"⚠ No template defined in recipe for '{route_name}'")

        # Ensure clean relative path
        template_path = os.path.normpath(os.path.join(route_name, template_name)).replace("\\", "/")

        try:
            template = self.env.get_template(template_path)
        except Exception as e:
            raise FileNotFoundError(
                f"Template not found: {template_path}\n"
                f"Jinja2 error: {e}\n"
                f"Search paths: {self.env.loader.searchpath if hasattr(self.env.loader, 'searchpath') else 'unknown'}"
            ) from e

        # Just render the template (static for now)
        hook_results = await self.plugins.hook("render_page", user_id=user_id, datas=datas, route_name=route_name, template=template)
        for result in hook_results:
            if isinstance(result, dict):
                datas.update(result) 
        return template.render(
            datas=datas,
            utils=lambda x: ('/utils_'+x),
            static=lambda x: (f'/static_{route_name}/'+x)
        )
    
    async def get_data(self, sources, user_id):
        results = {}
        await self.plugins.hook("before_get_data", sources=sources, user_id=user_id)
        for source in sources:
            print("Data source:", source["name"])

            if source.get('type') == 'sql':
                query = source.get('query')
                try:
                    result = await self.orm.execute(query)  # ✅ now valid
                    results[source["name"]] = result
                except Exception as e:
                    results[source["name"]] = {
                        "status": "error",
                        "message": str(e)
                    }
            elif source.get('type') == 'rest':
                endpoint = source.get("endpoint")
                try:
                    resp = requests.get(endpoint, timeout=10)
                    resp.raise_for_status()
                    results[source["name"]] = {
                        "status": "success",
                        "data": resp.json()
                    }
                except Exception as e:
                    results[source["name"]] = {
                        "status": "error",
                        "message": str(e)
                    }
            elif source.get('type') == 'internal':
                print("Source", source)
                req_datas = source.get("datas", [])
                internal_results = {}
                for req in req_datas:
                    if req == "profile":
                        internal_results["profile"] = await self.orm.get_user_profile(user_id)
                    elif req == "settings":
                        internal_results["settings"] = await self.orm.execute("SELECT preferences FROM testdb.users where id= :user_id", {"user_id": user_id})
                results[source["name"]] = internal_results
            elif source.get('type') == 'portal':
                api_data, code = await self.api.handle_raw("data", {"name": source.get("portal_name", ""), "args": source.get("args", {})}, user_id=user_id)
                results[source["name"]] = api_data['result'] if code == 200 else {"status": "error", "message": "Portal API error"}
            else:
                results[source["name"]] = {"status": "error", "message": "Unknown source type"}
        hook_results = await self.plugins.hook("after_get_data", sources=sources, user_id=user_id, results=results)
        for result in hook_results:
            if isinstance(result, dict):
                results.update(result) 
        return results
    async def gen_utils(self, info):
        templates = {
            "portal.js": ("template/portal.js.jinja", {"func_names": info["args"].get("func_names")}),
            "pem.js": ("template/pem.js.jinja", {"key": info["args"].get("key")}),
        }
        await self.plugins.hook("before_gen_util", info=info)

        name = info["name"]
        if name not in templates:
            print(f"Unknown utility: {name}")
            return

        template_file, context = templates[name]
        template_path = pkg_resources.files("nebuloid.utils").joinpath(template_file)
        template_content = template_path.read_text()
        template = Template(template_content)
        output = template.render(**context)

        output_path = os.path.join(self.storage.dir("utils"), name)
        with open(output_path, "w") as f:
            f.write(output)

        await self.plugins.hook("after_gen_util", name=name, output_path=output_path)