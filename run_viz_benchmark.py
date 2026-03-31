"""
run_viz_benchmark.py
────────────────────
Starts the CoopStorage API server and runs the storage benchmark in one process,
so you can watch the benchmark execute live in the browser visualizer.

Usage
-----
    python run_viz_benchmark.py                  # SMALL config, 20ms delay
    python run_viz_benchmark.py --config medium  # MEDIUM config
    python run_viz_benchmark.py --delay 0.05     # 50ms between ops
    python run_viz_benchmark.py --no-browser     # don't auto-open browser
    python run_viz_benchmark.py --port 1219      # custom port (default 1219)

The visualizer is served at:  http://localhost:<port>/static/index.html
"""

import argparse
import sys
import threading
import time
import unittest
import webbrowser
from pathlib import Path

# ── make sure the package is importable when run from the project root ────────
sys.path.insert(0, str(Path(__file__).parent))

import uvicorn

from tests.test_storage_benchmark import (
    BenchmarkConfig,
    SMALL,
    MEDIUM,
    LARGE,
    _build_storage,
    run_benchmark,
)
from coopstorage.storage.api.api_factory import storage_api_factory

# ── config map ────────────────────────────────────────────────────────────────
_CONFIGS: dict[str, BenchmarkConfig] = {
    "small":  SMALL,
    "medium": MEDIUM,
    "large":  LARGE,
}

# ── server thread ─────────────────────────────────────────────────────────────

class _UvicornThread(threading.Thread):
    """Runs uvicorn in a background daemon thread."""

    def __init__(self, app, host: str, port: int):
        super().__init__(daemon=True, name="uvicorn")
        self._config = uvicorn.Config(app, host=host, port=port, log_level="warning")
        self._server = uvicorn.Server(self._config)

    def run(self):
        self._server.run()

    def stop(self):
        self._server.should_exit = True


def _wait_for_server(host: str, port: int, timeout: float = 10.0):
    """Block until the HTTP server is accepting connections."""
    import socket
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection((host, port), timeout=0.5):
                return
        except OSError:
            time.sleep(0.1)
    raise RuntimeError(f"Server did not start within {timeout}s")


# ── main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Run storage benchmark with live visualizer")
    parser.add_argument("--config",     default="small",
                        choices=list(_CONFIGS), help="Benchmark size (default: small)")
    parser.add_argument("--delay",      type=float, default=0.02,
                        help="Seconds to sleep between transfer ops (default: 0.02)")
    parser.add_argument("--host",       default="localhost")
    parser.add_argument("--port",       type=int, default=1219)
    parser.add_argument("--no-browser", action="store_true",
                        help="Don't auto-open the browser")
    args = parser.parse_args()

    cfg = _CONFIGS[args.config]
    viz_url = f"http://{args.host}:{args.port}/static/index.html"

    print(f"\n  CoopStorage Visualizer Benchmark")
    print(f"  config={args.config}  locations={cfg.num_locations:,}"
          f"  ops={cfg.total_to_add:,}  delay={args.delay*1000:.0f}ms/op")
    print(f"  visualizer → {viz_url}\n")

    # 1. Build a shared storage so the API snapshot serves benchmark state
    storage = _build_storage(cfg)

    # 2. Create and start the API server
    app = storage_api_factory(storage=storage)
    server_thread = _UvicornThread(app, args.host, args.port)
    server_thread.start()

    print("  Starting API server…", end=" ", flush=True)
    _wait_for_server(args.host, args.port)
    print("ready.")

    # 3. Open browser
    if not args.no_browser:
        webbrowser.open(viz_url)
        time.sleep(0.5)   # brief pause so the browser can load before ops start

    # 4. Run benchmark — delay_provider slows ops to a visible pace
    print(f"  Running benchmark (delay={args.delay*1000:.0f}ms between ops)…\n")
    test_case = unittest.TestCase()
    test_case.maxDiff = None

    try:
        run_benchmark(
            test=test_case,
            cfg=cfg,
            storage=storage,
            delay_provider=lambda: args.delay,
        )
    except KeyboardInterrupt:
        print("\n  Interrupted.")

    print(f"\n  Benchmark complete. Visualizer still running at {viz_url}")
    print("  Press Ctrl+C to exit.\n")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("  Shutting down.")
        server_thread.stop()


if __name__ == "__main__":
    main()
