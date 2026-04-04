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
import logging
import random
import threading
import time
import unittest
from typing import Callable, Optional

logger = logging.getLogger(__name__)

import coopstorage.storage.loc_load.channel_processors as cps
import coopstorage.storage.loc_load.dcs as dcs
import coopstorage.storage.loc_load.evaluators as evaluators
from coopstorage.storage.loc_load.location import Location
from coopstorage.storage.loc_load.qualifiers import ContainerQualifier, LocationQualifier
from coopstorage.storage.loc_load.storage import Storage
from coopstorage.storage.loc_load.transferRequest import TransferRequestCriteria
from cooptools.qualifiers import PatternMatchQualifier, WhiteBlackListQualifier


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
        return self.locs_per_type * len(cps.ChannelProcessorType)

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


MINI = BenchmarkConfig(
    locs_per_type     = 1,
    location_capacity = 5,
    total_to_add      = 500,
    track_sample_size = 20,
    add_batch_size    = 25,
)

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

_LOC_SPACING = 15   # world units between adjacent locations

def _build_storage(cfg: BenchmarkConfig) -> Storage:
    locations = [
        Location(
            id=f"{cp.name}_{i:04d}",
            location_meta=dcs.LocationMeta(
                dims=(10, 10, 5),
                channel_processor=cp.value,
                capacity=cfg.location_capacity,
            ),
            coords=(type_idx * _LOC_SPACING, i * _LOC_SPACING, 0),
        )
        for type_idx, cp in enumerate(cps.ChannelProcessorType)
        for i in range(cfg.locs_per_type)
    ]
    return Storage(locs=locations)

# ── shared backbone ───────────────────────────────────────────────────────────

def run_benchmark(
    test: unittest.TestCase,
    cfg: BenchmarkConfig,
    delay_provider: Optional[Callable[[], float]] = None,
    storage: Optional[Storage] = None,
) -> None:
    """
    Execute the full fill/drain workload defined by cfg, running invariant
    checks periodically and printing a benchmark report at the end.
    Failures are surfaced as test assertions on the provided TestCase.

    Args:
        delay_provider: Optional callable returning seconds to sleep after each
                        individual transfer request. Use this to slow the benchmark
                        to a pace visible in the visualizer (e.g. ``lambda: 0.02``).
        storage:        Optional pre-built Storage instance. When provided the
                        benchmark operates on it directly (useful for sharing a
                        storage with an API server). If None a fresh storage is
                        built from cfg.
    """
    if storage is None:
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

    start            = time.perf_counter()
    last_status_time = start
    STATUS_INTERVAL  = 5.0   # seconds between heartbeat prints

    def _print_heartbeat(phase: str, running_total: int, running_concurrent: int):
        elapsed = time.perf_counter() - start
        rate    = running_total / elapsed if elapsed > 0 else 0
        pct     = running_total / cfg.total_to_add * 100
        print(f"  [heartbeat/{phase}]  "
              f"{running_total:,}/{cfg.total_to_add:,} ({pct:.0f}%)"
              f"  concurrent={running_concurrent:,}"
              f"  elapsed={elapsed:.1f}s"
              f"  rate={rate:,.0f}/s", flush=True)

    while total_added < cfg.total_to_add:

        # add a batch
        batch = min(cfg.add_batch_size, cfg.total_to_add - total_added)
        t0 = time.perf_counter()
        for batch_idx in range(batch):
            cid = f"C{container_counter:07d}"
            container_counter += 1
            storage.handle_transfer_requests([
                TransferRequestCriteria(
                    new_container=dcs.Container(id=cid),
                    dest_loc_query_args=LocationQualifier(at_least_capacity=1, has_addable_position=True),
                )
            ])
            if delay_provider is not None:
                time.sleep(delay_provider())
            now = time.perf_counter()
            if now - last_status_time >= STATUS_INTERVAL:
                _print_heartbeat('add', total_added + batch_idx + 1,
                                 current_count + batch_idx + 1)
                last_status_time = now
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
                  f"  (concurrent={current_count:,} -> {cfg.drain_target:,})", flush=True)
            for _ in range(to_remove):
                storage.handle_transfer_requests([
                    TransferRequestCriteria(
                        source_loc_query_args=LocationQualifier(is_occupied=True),
                        delete_container_on_transfer=True,
                    )
                ])
                removed_this_drain += 1
                if delay_provider is not None:
                    time.sleep(delay_provider())
                now = time.perf_counter()
                if now - last_status_time >= STATUS_INTERVAL:
                    _print_heartbeat('drain', total_added,
                                     current_count - removed_this_drain)
                    last_status_time = now
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
          f"({len(cps.ChannelProcessorType)} types × {cfg.locs_per_type:,} each)")
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


# ── simulation ────────────────────────────────────────────────────────────────

@dataclass
class SimulationConfig:
    """Config for the continuous randomized simulation."""
    locs_per_type:     int   = 3
    location_capacity: int   = 5
    min_fill_pct:      float = 0.15   # keep fill above this before adding
    max_fill_pct:      float = 0.85   # bias toward removing above this
    add_weight:        float = 0.45
    move_weight:       float = 0.40
    remove_weight:     float = 0.15

    @property
    def num_locations(self) -> int:
        return self.locs_per_type * len(cps.ChannelProcessorType)

    @property
    def max_concurrent(self) -> int:
        return self.num_locations * self.location_capacity


SIM_SMALL = SimulationConfig()
SIM_LARGE = SimulationConfig(locs_per_type=10)


# ── showcase simulation ────────────────────────────────────────────────────────

@dataclass
class ShowcaseConfig:
    """One location per processor type, all operated in sync each iteration."""
    location_capacity: int   = 5
    min_fill_pct:      float = 0.20
    max_fill_pct:      float = 0.80


SHOWCASE = ShowcaseConfig()


def _build_showcase_storage(cfg: ShowcaseConfig = None):
    """Build a storage with exactly one location per channel processor type,
    arranged in the smallest square grid that fits all types."""
    import math
    if cfg is None:
        cfg = SHOWCASE
    n = len(cps.ChannelProcessorType)
    cols = math.ceil(math.sqrt(n))
    locations = []
    for idx, cp_type in enumerate(cps.ChannelProcessorType):
        row = idx // cols
        col = idx % cols
        locations.append(Location(
            id=cp_type.name,
            location_meta=dcs.LocationMeta(
                dims=(10, 10, 5),
                channel_processor=cp_type.value,
                capacity=cfg.location_capacity,
            ),
            coords=(col * _LOC_SPACING, row * _LOC_SPACING, 0),
        ))
    return Storage(locs=locations)


def run_showcase_sim(
    storage: Storage,
    cfg: ShowcaseConfig = None,
    delay_provider: Optional[Callable[[], float]] = None,
    stop_event: Optional[threading.Event] = None,
) -> None:
    """Showcase sim: each iteration either adds one container to every location
    that can accept one, or removes one accessible container from every location
    that has one.  All locations operate in lock-step so behaviour differences
    between channel processor types are immediately visible.

    Fill thresholds determine the add/remove decision:
      - below min_fill_pct  → always add
      - above max_fill_pct  → always remove
      - in between          → random choice between add and remove
    """
    if cfg is None:
        cfg = SHOWCASE
    if stop_event is None:
        stop_event = threading.Event()

    container_counter = 0
    total_ops         = 0
    start             = time.perf_counter()
    last_status       = start
    STATUS_INTERVAL   = 5.0

    def _new_cid() -> str:
        nonlocal container_counter
        cid = f"S{container_counter:08d}"
        container_counter += 1
        return cid

    max_concurrent = sum(loc.Capacity for loc in storage.Locations.values())

    while not stop_event.is_set():
        count = len(storage.ContainerLocs)
        fill  = count / max_concurrent if max_concurrent > 0 else 0

        if fill < cfg.min_fill_pct:
            op = 'add'
        elif fill > cfg.max_fill_pct:
            op = 'remove'
        else:
            op = random.choice(['add', 'remove'])

        if op == 'add':
            for loc in storage.Locations.values():
                if not loc.get_addable_positions():
                    continue
                cid = _new_cid()
                try:
                    storage.handle_transfer_requests([
                        TransferRequestCriteria(
                            new_container=dcs.Container(id=cid),
                            dest_loc_query_args=LocationQualifier(
                                id_pattern=PatternMatchQualifier(
                                    white_list_black_list_qualifier=WhiteBlackListQualifier(
                                        white_list=[str(loc.Id)]
                                    )
                                ),
                                has_addable_position=True,
                            ),
                        )
                    ])
                    logger.debug("showcase  add  loc=%s  container=%s", loc.Id, cid)
                except Exception as e:
                    logger.warning("showcase  add  loc=%s  error=%s: %s",
                                   loc.Id, type(e).__name__, e)
        else:
            for loc in storage.Locations.values():
                removable = loc.get_removable_positions()
                if not removable:
                    continue
                container_id = loc.ContainerPositions.get(random.choice(removable))
                if container_id is None:
                    continue
                try:
                    storage.handle_transfer_requests([
                        TransferRequestCriteria(
                            container_query_args=ContainerQualifier(
                                pattern=PatternMatchQualifier(id=container_id)
                            ),
                            delete_container_on_transfer=True,
                        )
                    ])
                    logger.debug("showcase  remove  loc=%s  container=%s", loc.Id, container_id)
                except Exception as e:
                    logger.warning("showcase  remove  loc=%s  container=%s  error=%s: %s",
                                   loc.Id, container_id, type(e).__name__, e)

        total_ops += 1

        if delay_provider is not None:
            time.sleep(delay_provider())

        now = time.perf_counter()
        if now - last_status >= STATUS_INTERVAL:
            elapsed = now - start
            rate    = total_ops / elapsed if elapsed > 0 else 0
            print(
                f"  [showcase]  ops={total_ops:,}  containers={count:,}/{max_concurrent:,}"
                f"  fill={fill:.0%}  elapsed={elapsed:.0f}s  rate={rate:,.0f}/s",
                flush=True,
            )
            last_status = now


def run_simulation(
    storage: 'Storage',
    cfg: SimulationConfig = None,
    delay_provider: Optional[Callable[[], float]] = None,
    stop_event: Optional[threading.Event] = None,
) -> None:
    """
    Run a continuous randomized add/move/remove loop on *storage* until
    ``stop_event`` is set (or forever if None).

    Operation weights are biased by current fill level:
      - below min_fill_pct  → only add
      - above max_fill_pct  → only remove
      - in between          → weighted random among add / move / remove

    Args:
        storage:        A pre-built Storage instance to operate on.
        cfg:            SimulationConfig; defaults to SIM_SMALL.
        delay_provider: Optional callable returning seconds to sleep after each op.
        stop_event:     threading.Event that signals the loop to exit cleanly.
    """
    if cfg is None:
        cfg = SIM_SMALL
    if stop_event is None:
        stop_event = threading.Event()

    container_counter = 0
    total_ops         = 0
    start             = time.perf_counter()
    last_status       = start
    STATUS_INTERVAL   = 5.0

    def _new_cid() -> str:
        nonlocal container_counter
        cid = f"S{container_counter:08d}"
        container_counter += 1
        return cid

    def _current_count() -> int:
        return len(storage.ContainerLocs)

    def _do_add():
        cid = _new_cid()
        logger.debug("add  container=%s", cid)
        storage.handle_transfer_requests(
            [TransferRequestCriteria(
                new_container=dcs.Container(id=cid),
                dest_loc_query_args=LocationQualifier(at_least_capacity=1, has_addable_position=True),
            )],
            dest_loc_evaluator=evaluators.fewest_containers,
        )

    def _unblock(target_container) -> bool:
        """Move all containers blocking target_container in its current location.

        Returns False if the target can't be found in storage (already gone),
        True otherwise (blockers moved, target is now accessible).
        """
        container_locs = storage.ContainerLocs
        target_loc = next(
            (loc for c, loc in container_locs.items() if c.id == target_container.id),
            None,
        )
        if target_loc is None:
            logger.debug("unblock  container=%s  not_found_in_storage", target_container.id)
            return False

        state = [target_loc.ContainerPositions.get(i) for i in range(target_loc.Capacity)]
        cp    = target_loc.Meta.channel_processor
        blockers = cp.get_blocking_loads(target_container.id, state)

        if blockers:
            logger.debug(
                "unblock  container=%s  loc=%s  blockers=%s",
                target_container.id, target_loc.Id, list(blockers.keys()),
            )

        for blocker_id in blockers:
            logger.debug("unblock  moving blocker=%s", blocker_id)
            storage.handle_transfer_requests(
                [TransferRequestCriteria(
                    container_query_args=ContainerQualifier(
                        pattern=PatternMatchQualifier(id=blocker_id)
                    ),
                    dest_loc_query_args=LocationQualifier(
                        at_least_capacity=1,
                        has_addable_position=True,
                        id_pattern=PatternMatchQualifier(
                            white_list_black_list_qualifier=WhiteBlackListQualifier(
                                black_list=[str(target_loc.Id)]
                            )
                        ),
                    ),
                )],
                dest_loc_evaluator=evaluators.fewest_containers,
            )
        return True

    def _do_remove():
        containers = list(storage.get_containers().values())
        if not containers:
            return
        c = random.choice(containers)
        try:
            if not _unblock(c):
                return
            logger.debug("remove  container=%s", c.id)
            storage.handle_transfer_requests([
                TransferRequestCriteria(
                    container_query_args=ContainerQualifier(
                        pattern=PatternMatchQualifier(id=c.id)
                    ),
                    delete_container_on_transfer=True,
                )
            ])
        except Exception as e:
            logger.warning("remove  container=%s  error=%s: %s",
                           c.id, type(e).__name__, e)

    def _do_move():
        containers = list(storage.get_containers().values())
        if not containers:
            return
        c = random.choice(containers)
        try:
            if not _unblock(c):
                return
            logger.debug("move  container=%s", c.id)
            storage.handle_transfer_requests(
                [TransferRequestCriteria(
                    container_query_args=ContainerQualifier(
                        pattern=PatternMatchQualifier(id=c.id)
                    ),
                    dest_loc_query_args=LocationQualifier(at_least_capacity=1, has_addable_position=True),
                )],
                dest_loc_evaluator=evaluators.fewest_containers,
            )
        except Exception as e:
            logger.warning("move  container=%s  error=%s: %s",
                           c.id, type(e).__name__, e)

    while not stop_event.is_set():
        count   = _current_count()
        fill    = count / cfg.max_concurrent if cfg.max_concurrent > 0 else 0

        if fill < cfg.min_fill_pct:
            op = 'add'
        elif fill > cfg.max_fill_pct:
            op = 'remove'
        else:
            op = random.choices(
                ['add', 'move', 'remove'],
                weights=[cfg.add_weight, cfg.move_weight, cfg.remove_weight],
            )[0]

        try:
            if op == 'add':
                _do_add()
            elif op == 'move':
                _do_move()
            else:
                _do_remove()
        except Exception as e:
            logger.warning("sim  op=%s  error=%s: %s", op, type(e).__name__, e)

        total_ops += 1

        if delay_provider is not None:
            time.sleep(delay_provider())

        now = time.perf_counter()
        if now - last_status >= STATUS_INTERVAL:
            elapsed = now - start
            rate    = total_ops / elapsed if elapsed > 0 else 0
            print(
                f"  [sim]  ops={total_ops:,}  concurrent={count:,}/{cfg.max_concurrent:,}"
                f"  fill={fill:.0%}  elapsed={elapsed:.0f}s  rate={rate:,.0f}/s",
                flush=True,
            )
            last_status = now


if __name__ == "__main__":
    unittest.main()
