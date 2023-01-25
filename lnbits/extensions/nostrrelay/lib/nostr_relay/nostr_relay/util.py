import asyncio
import importlib
from contextlib import contextmanager, asynccontextmanager, suppress
from time import perf_counter

if hasattr(asyncio, 'timeout'):
    timeout = asyncio.timeout
else:
    # python < 3.11 does not have asyncio.timeout
    # rather than re-implement it, we'll just do nothing
    @asynccontextmanager
    async def timeout(duration):
        yield


@contextmanager
def catchtime() -> float:
    start = perf_counter()
    yield lambda: (perf_counter() - start) * 1000


def call_from_path(path, *args, **kwargs):
    """
    Call the function/constructor at the given path
    with args and kwargs
    """
    module_name, callable_name = path.rsplit('.', 1)
    module = importlib.import_module(module_name)
    func = getattr(module, callable_name)
    return func(*args, **kwargs)


class Periodic:
    """
    A periodic async task
    """
    def __init__(self, interval):
        self.interval = interval
        self.running = False
        self._task = None

    async def start(self):
        if not self.running:
            self.running = True
            # Start task to call func periodically:
            self._task = asyncio.ensure_future(self._run())

    async def stop(self):
        if self.running:
            self.running = False
            # Stop task and await it stopped:
            self._task.cancel()
            with suppress(asyncio.CancelledError):
                await self._task

    async def wait_function(self):
        await asyncio.sleep(self.interval)

    async def _run(self):
        while self.running:
            await self.wait_function()
            await self.run_once()
