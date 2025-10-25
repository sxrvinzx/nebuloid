import asyncio
from pathlib import Path

class NebuloidContext:
    def __init__(self, services, args=None, kwargs=None):
        services.inject_services(self)
        self.args = args
        self.kwargs = kwargs
        self.user = None  # To be set later if needed

        self.plugin_name = None

    @property
    def meta(self):
        return {"plugin": self.plugin_name or "Unknown"}
    
    def register_hook(self, name, func):
        registry = self.manifest.plugin_registry.setdefault(name, [])
        if func not in registry:
            registry.append(func)
        else:
            raise ValueError(f"Function {func} already registered for hook {name}")
    
    async def sleep(self, seconds):
        await asyncio.sleep(seconds)

    def get_path(self, relative_path=None):
        base_path = Path(self.plugins.plugins[self.plugin_name]['location'])
        if relative_path is None:
            return base_path
        return base_path / relative_path

    def host_file(self, file_id, rename=None, link_type="view"):
        file_path = self.storage.get_file_path(file_id)
        if rename is None:
            rename = Path(file_path).name

        self.manifest.file_registry[file_id] = (rename, file_path)
        base = self.manifest.base_url.rstrip('/')
        view_link = f"{base}/plugin_view/{file_id}"
        download_link = f"{base}/plugin_download/{file_id}"

        if link_type == "view":
            return view_link
        elif link_type == "download":
            return download_link
        elif link_type == "both":
            return view_link, download_link
        else:
            raise ValueError(f"Invalid link_type '{link_type}'. Use 'view', 'download', or 'both'.")
    
    def assets_path(self, relative_path=None):
        base_path = Path('shared/plugins')
        if relative_path is None:
            return base_path
        return base_path / relative_path