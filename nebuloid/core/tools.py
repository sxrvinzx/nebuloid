import asyncio
import inspect

class NebuloidTools:
    def __init__(self):
        pass

    def ensure_sync(self, func):
        """Make async functions safe to use in Flask (WSGI) by running them inside asyncio."""
        if not inspect.iscoroutinefunction(func):
            return func

        def wrapper(*args, **kwargs):
            return asyncio.run(func(*args, **kwargs))

        return wrapper

    async def maybe_await(self, obj):
        if inspect.isawaitable(obj):
            return await obj
        return obj