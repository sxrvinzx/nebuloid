import sys
import asyncio
import importlib.util
from pathlib import Path
from inspect import isawaitable
import importlib.resources as pkg_resources

from nebuloid.api.context import NebuloidContext

class NebuloidPluginManager:
    def __init__(self, services):
        services.inject_services(self)

        self.plugins = {}

    def mount(self):
        self.plugins_dir = self.storage.dir("plugins")
        for plugin, value in self.manifest.data['plugins'].items():
            if plugin.startswith('_'):
                # For underscore-prefixed plugins, load as normal module
                module_name = plugin[1:]
                module = __import__(module_name, fromlist=['mount'])
                location = pkg_resources.files('nebuloid.utils')
            else:
                pkg_file = self.plugins_dir / plugin / "__init__.py"
                single_file = self.plugins_dir / f"{plugin}.py"

                if pkg_file.exists():
                    target_file = pkg_file
                    location = self.plugins_dir / plugin
                elif single_file.exists():
                    target_file = single_file
                    location = self.plugins_dir
                else:
                    print(f"Plugin {plugin} not found at {pkg_file} or {single_file}")
                    continue

                module_name = f"{str(self.plugins_dir).replace('/', '_')}_{plugin}"
                spec = importlib.util.spec_from_file_location(module_name, target_file)
                module = importlib.util.module_from_spec(spec)
                sys.modules[module_name] = module
                spec.loader.exec_module(module)

            if hasattr(module, 'mount'):
                context = NebuloidContext(self.services, value)
                context.plugin_name = plugin
                self.plugins[plugin] = {"instance": module, "location": location}
                module.mount(context)
            else:
                print(f"Plugin {plugin} does not have a mount function.")
                
    async def hook(self, hook_name, user_id=None,*args, **kwargs):
        context = NebuloidContext(self.services, args=args, kwargs=kwargs)
        results = []
        if user_id is not None:
            resp = await self.orm.get_user_profile(user_id=user_id)
            context.user = resp.get("data", [{}])[0]

        for func in self.manifest.plugin_registry.get(hook_name, []):
            result = func(context)
            if isawaitable(result):
                try:
                    loop = asyncio.get_running_loop()
                    # if a loop is running, schedule it as a task and wait for it
                    result = await asyncio.create_task(result)
                except RuntimeError:
                    # no running loop, safe to use await directly
                    result = await result
            results.append(result)
        return results
    