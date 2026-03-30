"""
Performance / benchmarking tests for Storage.

Simulates a real-world warehouse workload:
  - 10,000 locations spread evenly across all 10 channel processor types
  - 100,000 container add operations via the full query/resolver path (Option A)
  - Fill-to-80%-then-drain-to-40% cycle to keep the system continuously busy
  - Periodic invariant validation + tracked-container location accuracy checks

Run with:
    python -m pytest tests/test_performance.py -v -s

The -s flag is required to see the printed benchmark report.
Results are reported only — no throughput threshold is asserted.
"""

import random
import time
import unittest

import coopstorage.storage.loc_load.channel_processors as cps
import coopstorage.storage.loc_load.dcs as dcs
from coopstorage.storage.loc_load.location import Location
from coopstorage.storage.loc_load.qualifiers import LocationQualifier
from coopstorage.storage.loc_load.storage import Storage
from coopstorage.storage.loc_load.transferRequest import TransferRequestCriteria

# ── benchmark parameters ──────────────────────────────────────────────────────

NUM_LOCATIONS      = 10_000
LOCATION_CAPACITY  = 5           # containers per location → 50,000 max concurrent
TOTAL_TO_ADD       = 100_000     # total container add operations
FILL_THRESHOLD_PCT = 0.80        # begin draining when storage is this % full
DRAIN_TO_PCT       = 0.40        # drain down to this % full
VALIDATE_EVERY     = 10_000      # run invariant checks every N adds
TRACK_SAMPLE_SIZE  = 500         # containers to track between validation cycles
ADD_BATCH_SIZE     = 1_000       # container adds per loop iteration

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

MAX_CONCURRENT   = NUM_LOCATIONS * LOCATION_CAPACITY
FILL_THRESHOLD   = int(MAX_CONCURRENT * FILL_THRESHOLD_PCT)
DRAIN_TARGET     = int(MAX_CONCURRENT * DRAIN_TO_PCT)
LOCS_PER_TYPE    = NUM_LOCATIONS // len(CHANNEL_PROCESSOR_TYPES)

# ── helpers ───────────────────────────────────────────────────────────────────

def _build_storage() -> Storage:
    locations = [
        Location(
            id=f"{cp.__name__}_{i:04d}",
            location_meta=dcs.LocationMeta(
                dims=(10, 10, 10),
                channel_processor=cp(),
                capacity=LOCATION_CAPACITY,
            ),
            coords=(0, 0, 0),
        )
        for cp in CHANNEL_PROCESSOR_TYPES
        for i in range(LOCS_PER_TYPE)
    ]
    return Storage(locs=locations)


# ── benchmark test ────────────────────────────────────────────────────────────

class TestStoragePerformance(unittest.TestCase):

    def test_benchmark_10k_locations_100k_containers(self):
        storage = _build_storage()

        container_counter = 0   # monotonically increasing ID source
        total_added       = 0
        current_count     = 0   # local counter avoids querying storage in hot loop

        # tracked_snapshot: container_id → expected loc id, refreshed each validation
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

        # ── validation ────────────────────────────────────────────────────────

        def _validate(label: str):
            t0 = time.perf_counter()

            container_locs = storage.ContainerLocs      # Dict[Container, Location]
            id_to_loc      = {c.id: loc.Id for c, loc in container_locs.items()}

            # 1. No container appears at more than one location
            seen: set = set()
            for cid in id_to_loc:
                self.assertNotIn(cid, seen,
                    f"Container {cid} found at multiple locations")
                seen.add(cid)

            # 2. ContainerLocs count == sum of each location's ContainerIds
            loc_map = storage.get_locs()
            loc_total = sum(len(loc.ContainerIds) for loc in loc_map.values())
            self.assertEqual(len(container_locs), loc_total,
                f"ContainerLocs ({len(container_locs)}) != "
                f"sum of loc.ContainerIds ({loc_total})")

            # 3. OccupiedLocs + EmptyLocs == total location count
            self.assertEqual(
                len(storage.OccupiedLocs) + len(storage.EmptyLocs),
                NUM_LOCATIONS,
                "OccupiedLocs + EmptyLocs != NUM_LOCATIONS",
            )

            # 4. Tracked containers from previous cycle are at the expected locations
            #    (containers do not move in this benchmark — only added or removed)
            for cid, expected_loc_id in tracked_snapshot.items():
                if cid in id_to_loc:
                    self.assertEqual(
                        id_to_loc[cid], expected_loc_id,
                        f"Container {cid} moved unexpectedly: "
                        f"expected {expected_loc_id}, found {id_to_loc[cid]}",
                    )
                # container was removed during a drain → acceptable, no assertion

            # 5. Refresh tracked snapshot for next cycle
            tracked_snapshot.clear()
            items = list(container_locs.items())
            for container, loc in random.sample(items, min(TRACK_SAMPLE_SIZE, len(items))):
                tracked_snapshot[container.id] = loc.Id

            elapsed    = time.perf_counter() - t0
            concurrent = len(container_locs)
            metrics['validate_times'].append(elapsed)
            metrics['validations_passed'] += 1
            metrics['peak_concurrent'] = max(metrics['peak_concurrent'], concurrent)

            print(f"\n  [{label}]  concurrent={concurrent:,}  "
                  f"validate={elapsed:.3f}s  tracked={len(tracked_snapshot)}")

        # ── main loop ─────────────────────────────────────────────────────────

        start = time.perf_counter()

        while total_added < TOTAL_TO_ADD:

            # add a batch
            batch = min(ADD_BATCH_SIZE, TOTAL_TO_ADD - total_added)
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

            # drain when over fill threshold
            if current_count >= FILL_THRESHOLD:
                to_remove = current_count - DRAIN_TARGET
                t0 = time.perf_counter()
                for _ in range(to_remove):
                    storage.handle_transfer_requests([
                        TransferRequestCriteria(
                            source_loc_query_args=LocationQualifier(is_occupied=True),
                        )
                    ])
                current_count          -= to_remove
                metrics['total_removed'] += to_remove
                metrics['drain_events']  += 1
                metrics['remove_times'].append(time.perf_counter() - t0)

            # periodic validation
            if total_added % VALIDATE_EVERY == 0:
                _validate(f"added={total_added:,}")

        total_time = time.perf_counter() - start

        # final validation
        _validate(f"FINAL  added={total_added:,}")

        # ── report ────────────────────────────────────────────────────────────

        throughput   = metrics['total_added'] / total_time
        avg_add_ms   = (sum(metrics['add_times'])    / len(metrics['add_times']))    / ADD_BATCH_SIZE * 1_000
        avg_valid_ms = (sum(metrics['validate_times']) / len(metrics['validate_times'])) * 1_000

        print(f"\n{'='*62}")
        print(f"  STORAGE BENCHMARK RESULTS")
        print(f"{'='*62}")
        print(f"  Locations:            {NUM_LOCATIONS:,}  "
              f"({len(CHANNEL_PROCESSOR_TYPES)} types × {LOCS_PER_TYPE:,} each)")
        print(f"  Max concurrent cap:   {MAX_CONCURRENT:,}  "
              f"(fill={FILL_THRESHOLD_PCT:.0%}, drain={DRAIN_TO_PCT:.0%})")
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


if __name__ == "__main__":
    unittest.main()
