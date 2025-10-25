class NebuloidServices:
    def __init__(self, **services):
        self._services = {}

        # set each service dynamically
        for name, instance in services.items():
            setattr(self, name, instance)
            self._services[name] = instance

    def inject_services(self, obj):
        setattr(obj, "services", self)
        for name, instance in self._services.items():
            if not name.startswith("_"):  # skip internal attrs
                setattr(obj, name, instance)

    def add(self, **services):
        for name, instance in services.items():
            if name in self._services:
                raise ValueError(f"Service {name} already exists.")
            setattr(self, name, instance)
            self._services[name] = instance