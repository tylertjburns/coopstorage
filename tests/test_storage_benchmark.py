"""
Storage benchmark tests parameterized across small / medium / large scales.

All three sizes exercise the same backbone:
  - N locations spread evenly across all 10 channel processor types
  - Fill-to-80% / drain-to-40% cycle via handle_transfer_requests
  - Periodic invariant validation + tracked-container location accuracy checks
  - Printed benchmark report (requires -s flag to see output)

Typical usage:
    # fast — runs in CI:
    python -m pytest tests/test_storage_benchmark.py -v -s -k Small

    # moderate:
    python -m pytest tests/test_storage_benchmark.py -v -s -k Medium

    # full stress:
    python -m pytest tests/test_storage_benchmark.py -v -s -k Large
"""

from dataclasses import dataclass, field
import random
import time
import unittest

import coopstorage.storage.loc_load.channel_processors as cps
import coopstorage.storage.loc_load.dcs as dcs
from coopstorage.storage.loc_load.location import Location
from coopstorage.storage.loc_load.qualifiers import LocationQualifier
from coopstorage.storage.loc_load.storage import Storage
from coopstorage.storage.loc_load.transferRequest import TransferRequestCriteria

# ── channel processor registry ────────────────────────────────────────────────

CHANNEL_PROCESSOR_TYPES = [
    cps.AllAvailableChannelProcessor,
    cps.AllAvailableFlowChannelProcessor,
    cps.AllAvailableFlowBackwardChannelProcessor,
    cps.FIFOFlowChannelProcessor,
    cps.FIFOFlowBackwardChannelProcessor,
    cps.LIFOFlowChannelProcessor,
    cps.LIFOFlowBackwardChannelProcessor,
    cps.OMNIChannelProcessor,
    cps.OMNIFlowChannelProcessor,
    cps.OMNIFlowBackwardChannelProcessor,
]

# ── config ────────────────────────────────────────────────────────────────────

@dataclass
class BenchmarkConfig:
    locs_per_type:      int
    location_capacity:  int
    total_to_add:       int
    fill_threshold_pct: float = 0.80
    drain_to_pct:       float = 0.40
    validate_every:     int   = None    # None → total_to_add // 10
    progress_every:     int   = None    # None → same as add_batch_size
    track_sample_size:  int   = 50
    add_batch_size:     int   = 100

    @property
    def num_locations(self) -> int:
        return self.locs_per_type * len(CHANNEL_PROCESSOR_TYPES)

    @property
    def max_concurrent(self) -> int:
        return self.num_locations * self.location_capacity

    @property
    def fill_threshold(self) -> int:
        return int(self.max_concurrent * self.fill_threshold_pct)

    @property
    def drain_target(self) -> int:
        return int(self.max_concurrent * self.drain_to_pct)

    @property
    def effective_validate_every(self) -> int:
        return self.validate_every or max(1, self.total_to_add // 10)

    @property
    def effective_progress_every(self) -> int:
        return self.progress_every or self.add_batch_size


SMALL = BenchmarkConfig(
    locs_per_type     = 10,
    location_capacity = 5,
    total_to_add      = 500,
    track_sample_size = 20,
    add_batch_size    = 50,
)

MEDIUM = BenchmarkConfig(
    locs_per_type     = 100,
    location_capacity = 5,
    total_to_add      = 5_000,
    track_sample_size = 100,
    add_batch_size    = 500,
)

LARGE = BenchmarkConfig(
    locs_per_type     = 1_000,
    location_capacity = 5,
    total_to_add      = 100_000,
    track_sample_size = 500,
    add_batch_size    = 1_000,
    validate_every    = 10_000,
)

# ── helpers ───────────────────────────────────────────────────────────────────

def _build_storage(cfg: BenchmarkConfig) -> Storage:
    locations = [
        Location(
            id=f"{cp.__name__}_{i:04d}",
            location_meta=dcs.LocationMeta(
                dims=(10, 10, 10),
                channel_processor=cp(),
                capacity=cfg.location_capacity,
            ),
            coords=(0, 0, 0),
        )
        for cp in CHANNEL_PROCESSOR_TYPES
        for i in range(cfg.locs_per_type)
    ]
    return Storage(locs=locations)

# ── shared backbone ───────────────────────────────────────────────────────────

def run_benchmark(test: unittest.TestCase, cfg: BenchmarkConfig) -> None:
    """
    Execute the full fill/drain workload defined by cfg, running invariant
    checks periodically and printing a benchmark report at the end.
    Failures are surfaced as test assertions on the provided TestCase.
    """
    storage = _build_storage(cfg)

    container_counter = 0
    total_added       = 0
    current_count     = 0
    tracked_snapshot: dict[str, str] = {}

    metrics = {
        'total_added':        0,
        'total_removed':      0,
        'peak_concurrent':    0,
        'validations_passed': 0,
        'drain_events':       0,
        'add_times':          [],
        'remove_times':       [],
        'validate_times':     [],
    }

    # ── validation ────────────────────────────────────────────────────────────

    def _validate(label: str):
        t0 = time.perf_counter()

        container_locs = storage.ContainerLocs
        id_to_loc      = {c.id: loc.Id for c, loc in container_locs.items()}

        # 1. No container at more than one location
        seen: set = set()
        for cid in id_to_loc:
            test.assertNotIn(cid, seen,
                f"Container {cid} found at multiple locations")
            seen.add(cid)

        # 2. ContainerLocs count == sum of each location's ContainerIds
        loc_map   = storage.get_locs()
        loc_total = sum(len(loc.ContainerIds) for loc in loc_map.values())
        test.assertEqual(len(container_locs), loc_total,
            f"ContainerLocs ({len(container_locs)}) != "
            f"sum of loc.ContainerIds ({loc_total})")

        # 3. OccupiedLocs + EmptyLocs == total location count
        test.assertEqual(
            len(storage.OccupiedLocs) + len(storage.EmptyLocs),
            cfg.num_locations,
            "OccupiedLocs + EmptyLocs != num_locations",
        )

        # 4. Tracked containers from previous cycle are still at the same location
        #    (containers don't move in this benchmark — only added or removed)
        for cid, expected_loc_id in tracked_snapshot.items():
            if cid in id_to_loc:
                test.assertEqual(
                    id_to_loc[cid], expected_loc_id,
                    f"Container {cid} moved unexpectedly: "
                    f"expected {expected_loc_id}, found {id_to_loc[cid]}",
                )

        # 5. Refresh tracked snapshot for next cycle
        tracked_snapshot.clear()
        items = list(container_locs.items())
        for container, loc in random.sample(items, min(cfg.track_sample_size, len(items))):
            tracked_snapshot[container.id] = loc.Id

        elapsed    = time.perf_counter() - t0
        concurrent = len(container_locs)
        metrics['validate_times'].append(elapsed)
        metrics['validations_passed'] += 1
        metrics['peak_concurrent'] = max(metrics['peak_concurrent'], concurrent)

        print(f"\n  [{label}]  concurrent={concurrent:,}  "
              f"validate={elapsed:.3f}s  tracked={len(tracked_snapshot)}")

    # ── main loop ─────────────────────────────────────────────────────────────

    start = time.perf_counter()

    while total_added < cfg.total_to_add:

        # add a batch
        batch = min(cfg.add_batch_size, cfg.total_to_add - total_added)
        t0 = time.perf_counter()
        for _ in range(batch):
            cid = f"C{container_counter:07d}"
            container_counter += 1
            storage.handle_transfer_requests([
                TransferRequestCriteria(
                    new_container=dcs.Container(id=cid),
                    dest_loc_query_args=LocationQualifier(at_least_capacity=1),
                )
            ])
        current_count += batch
        total_added   += batch
        metrics['total_added'] += batch
        metrics['add_times'].append(time.perf_counter() - t0)

        # periodic progress update (cheap — no invariant checks)
        if total_added % cfg.effective_progress_every == 0:
            elapsed   = time.perf_counter() - start
            rate      = total_added / elapsed if elapsed > 0 else 0
            remaining = (cfg.total_to_add - total_added) / rate if rate > 0 else float('inf')
            pct       = total_added / cfg.total_to_add * 100
            print(f"  [progress]  {total_added:,}/{cfg.total_to_add:,} ({pct:.0f}%)"
                  f"  concurrent={current_count:,}"
                  f"  elapsed={elapsed:.1f}s"
                  f"  rate={rate:,.0f}/s"
                  f"  eta={remaining:.0f}s", flush=True)

        # drain when over fill threshold
        if current_count >= cfg.fill_threshold:
            to_remove = current_count - cfg.drain_target
            t0 = time.perf_counter()
            removed_this_drain = 0
            print(f"  [drain start]  removing {to_remove:,} containers"
                  f"  (concurrent={current_count:,} → {cfg.drain_target:,})", flush=True)
            for _ in range(to_remove):
                storage.handle_transfer_requests([
                    TransferRequestCriteria(
                        source_loc_query_args=LocationQualifier(is_occupied=True),
                    )
                ])
                removed_this_drain += 1
                if removed_this_drain % cfg.effective_progress_every == 0:
                    elapsed      = time.perf_counter() - start
                    drain_rate   = removed_this_drain / (time.perf_counter() - t0)
                    remaining_drain = to_remove - removed_this_drain
                    print(f"  [draining]  -{removed_this_drain:,}/{to_remove:,}"
                          f"  concurrent={current_count - removed_this_drain:,}"
                          f"  elapsed={elapsed:.1f}s"
                          f"  rate={drain_rate:,.0f}/s", flush=True)
            current_count            -= to_remove
            metrics['total_removed'] += to_remove
            metrics['drain_events']  += 1
            metrics['remove_times'].append(time.perf_counter() - t0)
            print(f"  [drain done]  removed {to_remove:,}  elapsed={time.perf_counter() - t0:.1f}s", flush=True)

        # periodic validation
        if total_added % cfg.effective_validate_every == 0:
            _validate(f"added={total_added:,}")

    total_time = time.perf_counter() - start

    # final validation
    _validate(f"FINAL  added={total_added:,}")

    # ── report ────────────────────────────────────────────────────────────────

    throughput   = metrics['total_added'] / total_time
    avg_add_ms   = (sum(metrics['add_times']) / len(metrics['add_times'])) / cfg.add_batch_size * 1_000
    avg_valid_ms = (sum(metrics['validate_times']) / len(metrics['validate_times'])) * 1_000

    print(f"\n{'='*62}")
    print(f"  STORAGE BENCHMARK  [{type(test).__name__}]")
    print(f"{'='*62}")
    print(f"  Locations:            {cfg.num_locations:,}  "
          f"({len(CHANNEL_PROCESSOR_TYPES)} types × {cfg.locs_per_type:,} each)")
    print(f"  Max concurrent cap:   {cfg.max_concurrent:,}  "
          f"(fill={cfg.fill_threshold_pct:.0%}, drain={cfg.drain_to_pct:.0%})")
    print(f"  Total time:           {total_time:.2f}s")
    print(f"  Total added:          {metrics['total_added']:,}")
    print(f"  Total removed:        {metrics['total_removed']:,}")
    print(f"  Drain events:         {metrics['drain_events']}")
    print(f"  Peak concurrent:      {metrics['peak_concurrent']:,}")
    print(f"  Throughput:           {throughput:,.0f} containers/sec")
    print(f"  Avg add latency:      {avg_add_ms:.3f} ms/container")
    print(f"  Avg validation time:  {avg_valid_ms:.0f} ms")
    print(f"  Validations passed:   {metrics['validations_passed']}")
    print(f"{'='*62}")


# ── parameterized test classes ────────────────────────────────────────────────

class TestStorageBenchmarkSmall(unittest.TestCase):
    """100 locations, 500 container ops — fast, runs in CI."""
    def test_benchmark(self):
        run_benchmark(self, SMALL)


class TestStorageBenchmarkMedium(unittest.TestCase):
    """1,000 locations, 5,000 container ops — moderate run."""
    def test_benchmark(self):
        run_benchmark(self, MEDIUM)


class TestStorageBenchmarkLarge(unittest.TestCase):
    """10,000 locations, 100,000 container ops — full stress test.

    Run with: python -m pytest tests/test_storage_benchmark.py -v -s -k Large
    """
    def test_benchmark(self):
        run_benchmark(self, LARGE)


if __name__ == "__main__":
    unittest.main()
