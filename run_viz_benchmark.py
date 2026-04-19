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
    python run_viz_benchmark.py --mode defaultzone         # StorageConfig(zones=[ZoneConfig()]) + sim
    python run_viz_benchmark.py --mode multizone           # VNA zone + flow rack zone, side by side
    python run_viz_benchmark.py --delay 0.05            # 50ms between ops
    python run_viz_benchmark.py --no-browser            # don't auto-open browser
    python run_viz_benchmark.py --port 1219             # custom port (default 1219)

The visualizer is served at:  http://localhost:<port>/static/index.html
"""

import argparse
import logging
import math
import sys
import threading
import time
import unittest
from pathlib import Path

from cooptools import loggingHelpers as lh

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
    build_flow_rack_zone,
    StorageConfig, ZoneConfig, AisleConfig, BayConfig, ZoneProjection,
)
import coopstorage.storage.loc_load.dcs as dcs
import coopstorage.storage.loc_load.channel_processors as cps
from dataclasses import replace
from coopstorage.viz_helper import start_visualizer
from coopstorage.storage.loc_load.reservation_provider import (
    ApiKeyReservationProvider,
    JwtExchangeReservationProvider,
)
from coopstorage.storage.loc_load.event_bus import StorageEvent

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
    parser.add_argument("--mode",       default="benchmark", choices=["benchmark", "sim", "showcase", "defaultzone", "multizone"],
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
    parser.add_argument("--reservation-url", default=None,
                        help="Base URL of the Locker reservation API (e.g. http://localhost:5001)")
    parser.add_argument("--api-key", default=None,
                        help="API key for the Locker reservation API (required when --reservation-url is set)")
    parser.add_argument("--auth-mode", default="jwt", choices=["jwt", "apikey"],
                        help="Auth mode for the reservation API: jwt (default) or apikey")
    args = parser.parse_args()

    if args.reservation_url and not args.api_key:
        parser.error("--api-key is required when --reservation-url is set")

    if args.reservation_url:
        if args.auth_mode == "jwt":
            reservation_provider = JwtExchangeReservationProvider(args.reservation_url, args.api_key)
        else:
            reservation_provider = ApiKeyReservationProvider(args.reservation_url, args.api_key)
    else:
        reservation_provider = None

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format=lh.BASE_LOG_FORMAT,
    )

    viz_url = f"http://{args.host}:{args.port}/static/index.html"

    if args.mode == "sim":
        storage = build_all_processor_storage(reservation_provider=reservation_provider)
        print(f"\n  CoopStorage Visualizer Simulation (continuous)")
        print(f"  locations={len(storage.Locations):,}  delay={args.delay*1000:.0f}ms/op")
        print(f"  visualizer -> {viz_url}\n")
    elif args.mode == "benchmark":
        cfg = _CONFIGS[args.config]
        storage = build_all_processor_storage(
            locs_per_type=cfg.locs_per_type,
            location_capacity=cfg.location_capacity,
            reservation_provider=reservation_provider,
        )
        print(f"\n  CoopStorage Visualizer Benchmark")
        print(f"  config={args.config}  locations={cfg.num_locations:,}"
              f"  ops={cfg.total_to_add:,}  delay={args.delay*1000:.0f}ms/op")
        print(f"  visualizer -> {viz_url}\n")
    elif args.mode == "showcase":
        storage = build_showcase_storage(reservation_provider=reservation_provider)
        print(f"\n  CoopStorage Visualizer Showcase (lock-step per processor type)")
        print(f"  locations={len(storage.Locations):,}  delay={args.delay*1000:.0f}ms/op")
        print(f"  visualizer -> {viz_url}\n")
    elif args.mode == "defaultzone":
        _bay = BayConfig(
            loc_config=dcs.LocationMeta(
                dims=(10, 10, 5),
                channel_processor=cps.AllAvailableChannelProcessor(),
                capacity=1,
            )
        )
        storage = StorageConfig(
            zones_config={"default": ZoneConfig(
                aisle_config=AisleConfig(
                    left_bay_config=replace(_bay, side_designator="L"),
                    right_bay_config=replace(_bay, side_designator="R"),
                ),
            )}
        ).storage(reservation_provider=reservation_provider)
        print(f"\n  CoopStorage Visualizer — One Aisle (default StorageConfig)")
        print(f"  locations={len(storage.Locations):,}  delay={args.delay*1000:.0f}ms/op")
        print(f"  visualizer -> {viz_url}\n")
    elif args.mode == "multizone":
        _bay = BayConfig(
            loc_config=dcs.LocationMeta(
                dims=(10, 10, 5),
                channel_processor=cps.AllAvailableChannelProcessor(),
                capacity=1,
            ),
            locations_per_bay=1,
            shelves=3,
            bay_height=6.0,
            inter_bay_spacing=2.0,
        )
        storage = StorageConfig(
            zones_config={
                "vna": ZoneConfig(
                    aisles=5,
                    aisle_config=AisleConfig(
                        bays=10,
                        left_bay_config=replace(_bay, side_designator="L"),
                        right_bay_config=replace(_bay, side_designator="R"),
                        aisle_width=20.0,
                    ),
                    inter_aisle_spacing=2.0,
                    origin=(0.0, 0.0, 0.0),
                ),
                "flow_rack": build_flow_rack_zone(
                    bays=8,
                    shelves=4,
                    channel_depth=4,
                    lanes_per_bay=2,
                    lane_width=10.0,
                    loc_depth=20.0,
                    shelf_height=5.0,
                    inter_bay_spacing=1.0,
                    aisle_width=15.0,
                    origin=(200.0, 0.0, 0.0),
                    projection=ZoneProjection(rotation_z=math.pi / 2),
                ),
            }
        ).storage(reservation_provider=reservation_provider)
        print(f"\n  CoopStorage Visualizer — Multizone (VNA + flow rack)")
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

    # Build on_status callback that forwards sim status to the SSE event bus
    def _on_status(d: dict):
        server_thread.event_bus._emit(StorageEvent('sim_status', d))

    # 2. Run workload
    try:
        if args.mode in ("sim", "defaultzone", "multizone"):
            print(f"  Running simulation (delay={args.delay*1000:.0f}ms between ops,"
                  f" Ctrl+C to stop)…\n")
            stop_event = threading.Event()
            run_simulation(
                storage=storage,
                cfg=SIM_DEFAULT,
                delay_provider=lambda: args.delay,
                stop_event=stop_event,
                on_status=_on_status,
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
                on_status=_on_status,
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
