from quart import Quart
from nebuloid.manifest import NebuloidManifest
import asyncio

from .server import NebuloidServer
from .services import NebuloidServices
from .storage import NebuloidStorage
from nebuloid.orm import NebuloidORM
from nebuloid.api.expose_api import NebuloidExposeAPI
from nebuloid.api.context import NebuloidContext
from nebuloid.plugins import NebuloidPluginManager

class Nebuloid:
    def __init__(self, profile=None):
        self.storage = NebuloidStorage()
        self.manifest = NebuloidManifest(self.storage)
        self.orm = NebuloidORM(self.manifest)
        self.expose_api = NebuloidExposeAPI(self.manifest)

        self.services = NebuloidServices(
            orm=self.orm,
            manifest=self.manifest,
            expose_api=self.expose_api,
            storage=self.storage,
        )

        self.plugins = NebuloidPluginManager(self.services)
        self.services.add(plugins=self.plugins)

        self.server = NebuloidServer(self.services)
        self.expose_api.inject_decorators(self)

        if profile:
            self.manifest.profile = profile

        self.manifest.from_file("manifest.neb")
        self.init()

    @property
    def profile(self):
        return self.manifest.profile

    @profile.setter
    def profile(self, value):
        self.manifest.profile = value

    def init(self, manifest_file=None):
        if manifest_file:
            self.manifest.from_file(manifest_file)

        self.app = Quart(__name__, template_folder=None, static_folder=None)
        self.server.app = self.app

        self.storage.mount()
        self.server.mount()
        self.orm.mount()
        self.plugins.mount()

        # setup startup hook for ASGI
        @self.app.before_serving
        async def startup_tasks():
            await self.plugins.hook("before_server_start")
            await self.expose_api.ready()
            await self.server.ready()
            # start background maintenance tasks
            asyncio.create_task(self.orm.maintenance_task())
            asyncio.create_task(self.storage.maintenance_task())
            # run background hooks if any
            await self._start_background_hooks()

    @property
    def wsgi(self):
        return self.app.wsgi_app

    @property
    def asgi(self):
        return self.app

    def run_hook_sync(self, hook_name, *args, **kwargs):
        """
        run an async plugin hook safely from sync code
        """
        async def _runner():
            return await self.plugins.hook(hook_name, *args, **kwargs)

        try:
            loop = asyncio.get_running_loop()
            return asyncio.create_task(_runner())
        except RuntimeError:
            return asyncio.run(_runner())

    async def _start_background_hooks(self):
        sources = [
            self.plugins.manifest.plugin_registry.get("run", []),
            self.manifest.func_registry.get("background", {}).values()
        ]
        tasks = []
        for func_list in sources:
            for func in func_list:
                result = func(NebuloidContext(self.services))
                if asyncio.iscoroutine(result):
                    tasks.append(result)

        if tasks:
            # wrap gather in a coroutine for create_task
            async def run_all():
                await asyncio.gather(*tasks, return_exceptions=True)

            asyncio.create_task(run_all())
            
    def run(self, host="127.0.0.1", port=5000, debug=True):
        from hypercorn.asyncio import serve
        from hypercorn.config import Config as HyperConfig

        # determine scheme
        scheme = "https" if getattr(self, "ssl_enabled", False) else "http"
        self.manifest.base_url = f"{scheme}://{host}:{port}"
        print(f"Server running at {self.manifest.base_url}")

        config = HyperConfig()
        config.bind = [f"{host}:{port}"]
        config.use_reloader = debug
        self.app.debug = debug

        # dev mode: run all async tasks including server concurrently
        async def main():
            await serve(self.app, config)

        asyncio.run(main())
