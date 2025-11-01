import inspect

class NebuloidExposeAPI:
    def __init__(self, manifest):
        self.manifest = manifest
        self._registries = {
            "portal": {},
            "background": {},
            "task": {},
        }
    
    def inject_decorators(self, obj):
        for name in self._registries.keys():
            if not hasattr(obj, name):
                setattr(obj, name, getattr(self, name))
        
    def _register_decorator(self, registry_name, func=None):
        registry = self._registries.setdefault(registry_name, {})
        if func and inspect.isfunction(func):
            registry[func.__name__] = func
            self.ready() # re-ready to update manifest
            return func

        def decorator(f):
            registry[f.__name__] = f
            self.ready() # re-ready to update manifest
            return f
        return decorator

    def __getattr__(self, name):
        if name not in self._registries:
            self._registries[name] = {}
        return lambda func=None: self._register_decorator(name, func)

    def ready(self):
        for name, registry in self._registries.items():
            self.manifest.func_registry[name] = registry
