"""
run_viz_benchmark.py
────────────────────
Starts the CoopStorage API server and runs the storage benchmark in one process,
so you can watch the benchmark execute live in the browser visualizer.

Usage
-----
    python run_viz_benchmark.py                         # SMALL benchmark, 20ms delay
    python run_viz_benchmark.py --config medium         # MEDIUM benchmark
    python run_viz_benchmark.py --mode sim              # continuous randomized simulation
    python run_viz_benchmark.py --mode showcase         # one of each processor type, lock-step
    python run_viz_benchmark.py --delay 0.05            # 50ms between ops
    python run_viz_benchmark.py --no-browser            # don't auto-open browser
    python run_viz_benchmark.py --port 1219             # custom port (default 1219)

The visualizer is served at:  http://localhost:<port>/static/index.html
"""

import argparse
import logging
import sys
import threading
import time
import unittest
from pathlib import Path

# ── make sure the package is importable when run from the project root ────────
sys.path.insert(0, str(Path(__file__).parent))

from tests.test_storage_benchmark import (
    BenchmarkConfig,
    MINI, SMALL, MEDIUM, LARGE,
    run_benchmark,
)
from coopstorage.simulation import (
    SIM_DEFAULT, SHOWCASE,
    run_simulation, run_showcase_sim,
)
from coopstorage.storage_generators import (
    build_all_processor_storage,
    build_showcase_storage,
)
from coopstorage.viz_helper import start_visualizer

# ── config maps ───────────────────────────────────────────────────────────────
_CONFIGS: dict[str, BenchmarkConfig] = {
    "mini":   MINI,
    "small":  SMALL,
    "medium": MEDIUM,
    "large":  LARGE,
}


# ── main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Run storage benchmark/sim with live visualizer")
    parser.add_argument("--config",     default="small",
                        choices=list(_CONFIGS), help="Config size (default: small)")
    parser.add_argument("--mode",       default="benchmark", choices=["benchmark", "sim", "showcase"],
                        help="'benchmark' runs a fixed workload; 'sim' runs continuously (default: benchmark)")
    parser.add_argument("--delay",      type=float, default=0.02,
                        help="Seconds to sleep between transfer ops (default: 0.02)")
    parser.add_argument("--host",       default="localhost")
    parser.add_argument("--port",       type=int, default=1219)
    parser.add_argument("--no-browser", action="store_true",
                        help="Don't auto-open the browser")
    parser.add_argument("--log-level",  default="WARNING",
                        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
                        help="Logging level (default: WARNING)")
    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(levelname)s  %(name)s  %(message)s",
    )

    viz_url = f"http://{args.host}:{args.port}/static/index.html"

    if args.mode == "sim":
        storage = build_all_processor_storage()
        print(f"\n  CoopStorage Visualizer Simulation (continuous)")
        print(f"  locations={len(storage.Locations):,}  delay={args.delay*1000:.0f}ms/op")
        print(f"  visualizer -> {viz_url}\n")
    elif args.mode == "benchmark":
        cfg = _CONFIGS[args.config]
        storage = build_all_processor_storage(
            locs_per_type=cfg.locs_per_type,
            location_capacity=cfg.location_capacity,
        )
        print(f"\n  CoopStorage Visualizer Benchmark")
        print(f"  config={args.config}  locations={cfg.num_locations:,}"
              f"  ops={cfg.total_to_add:,}  delay={args.delay*1000:.0f}ms/op")
        print(f"  visualizer -> {viz_url}\n")
    elif args.mode == "showcase":
        storage = build_showcase_storage()
        print(f"\n  CoopStorage Visualizer Showcase (lock-step per processor type)")
        print(f"  locations={len(storage.Locations):,}  delay={args.delay*1000:.0f}ms/op")
        print(f"  visualizer -> {viz_url}\n")

    # 1. Start the API server and (optionally) open the browser
    server_thread = start_visualizer(
        storage=storage,
        host=args.host,
        port=args.port,
        open_browser=not args.no_browser,
        block=False,
    )

    # 2. Run workload
    try:
        if args.mode == "sim":
            print(f"  Running simulation (delay={args.delay*1000:.0f}ms between ops,"
                  f" Ctrl+C to stop)…\n")
            stop_event = threading.Event()
            run_simulation(
                storage=storage,
                cfg=SIM_DEFAULT,
                delay_provider=lambda: args.delay,
                stop_event=stop_event,
            )
        elif args.mode == "benchmark":
            print(f"  Running benchmark (delay={args.delay*1000:.0f}ms between ops)…\n")
            test_case = unittest.TestCase()
            test_case.maxDiff = None
            run_benchmark(
                test=test_case,
                cfg=cfg,
                storage=storage,
                delay_provider=lambda: args.delay,
            )
        elif args.mode == "showcase":
            print(f"  Running showcase simulation (delay={args.delay*1000:.0f}ms between ops,"
                  f" Ctrl+C to stop)…\n")
            stop_event = threading.Event()
            run_showcase_sim(
                storage=storage,
                cfg=SHOWCASE,
                delay_provider=lambda: args.delay,
                stop_event=stop_event,
            )

    except KeyboardInterrupt:
        print("\n  Interrupted.")

    suffix = "Benchmark complete." if args.mode == "benchmark" else "Simulation stopped."
    print(f"\n  {suffix} Visualizer still running at {viz_url}")
    print("  Press Ctrl+C to exit.\n")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("  Shutting down.")
        server_thread.stop()


if __name__ == "__main__":
    main()
