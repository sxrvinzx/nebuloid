import json
class NebuloidManifest:
    def __init__(self, storage):
        self._profile = None
        self.data = {}
        self.func_registry = {"portal": {}, "background": {}}
        self.plugin_registry = {}
        self.file_registry = {}  # file_id -> (file_name, file_path)
        self.storage = storage

        self.base_url = None

    def meta(self):
        return {"base_url": self.base_url}

    def get_file(self, file_id):
        if file_id in self.file_registry:
            file_name, file_path = self.file_registry[file_id]
            return file_name, file_path
        return None, None
    
    @property
    def profile(self):
        return self._profile

    @profile.setter
    def profile(self, value):
        self._profile = value
        self._load_profile()
    
    def _load_profile(self):
        print("loaded profile!!:", self._profile)
    
    def from_file(self, filename):
        # todo: verify and validate manifest before and after load
        manifest_file = self.storage.file(filename, 'r')
        with manifest_file as f:
            manifest_data = json.load(f)

        self.data.clear()
        self.data.update(manifest_data)

        self.base_url = self.data.get("server", {}).get("base_url", None)
    
