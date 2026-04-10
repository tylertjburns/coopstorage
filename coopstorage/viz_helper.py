"""
viz_helper.py
─────────────
Utility for starting the CoopStorage browser visualizer against any Storage object.

Usage
-----
    from coopstorage.viz_helper import start_visualizer

    storage = Storage(locs=[...])
    server = start_visualizer(storage)                # opens browser, blocks until Ctrl+C
    server = start_visualizer(storage, block=False)   # returns thread; caller drives the loop
    ...
    server.stop()
"""

import socket
import threading
import time
import webbrowser

import uvicorn

from coopstorage.storage.api.api_factory import storage_api_factory
from coopstorage.storage.loc_load.storage import Storage
from coopstorage.storage.loc_load.event_bus import StorageEventBus, StorageEvent


class _UvicornThread(threading.Thread):
    """Runs a uvicorn server in a background daemon thread."""

    def __init__(self, app, host: str, port: int, event_bus: StorageEventBus):
        super().__init__(daemon=True, name="uvicorn")
        self._config = uvicorn.Config(app, host=host, port=port, log_level="warning")
        self._server = uvicorn.Server(self._config)
        self.event_bus = event_bus

    def run(self):
        self._server.run()

    def stop(self):
        self._server.should_exit = True


def _wait_for_server(host: str, port: int, timeout: float = 10.0):
    """Block until the HTTP server is accepting connections."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection((host, port), timeout=0.5):
                return
        except OSError:
            time.sleep(0.1)
    raise RuntimeError(f"Server did not start within {timeout}s")


def start_visualizer(
    storage: Storage,
    host: str = "localhost",
    port: int = 1219,
    open_browser: bool = True,
    block: bool = False,
) -> _UvicornThread:
    """Start the CoopStorage visualizer for the given storage object.

    Parameters
    ----------
    storage:      The Storage instance to visualize.
    host:         Host to bind the API server on (default: localhost).
    port:         Port to bind the API server on (default: 1219).
    open_browser: If True, open the visualizer URL in the default browser.
    block:        If True, block until Ctrl+C then shut down automatically.
                  If False, return the server thread immediately so the caller
                  can drive its own loop and call server.stop() when done.

    Returns
    -------
    The running _UvicornThread (useful when block=False).
    """
    viz_url = f"http://{host}:{port}/static/index.html"

    event_bus = StorageEventBus()
    app = storage_api_factory(storage=storage, event_bus=event_bus)
    server_thread = _UvicornThread(app, host, port, event_bus)
    server_thread.start()

    print("  Starting visualizer…", end=" ", flush=True)
    _wait_for_server(host, port)
    print(f"ready.  {viz_url}")

    if open_browser:
        webbrowser.open(viz_url)
        time.sleep(0.5)  # let the browser load before any ops start

    if block:
        print("  Visualizer running. Press Ctrl+C to stop.\n")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("  Shutting down.")
            server_thread.stop()

    return server_thread
