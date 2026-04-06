"""
Continuous storage simulation utilities.

SimulationConfig / run_simulation  — randomised add/move/remove loop
ShowcaseConfig  / run_showcase_sim — lock-step per-processor demo

Storage builders live in storage_generators.py.
"""

import logging
import random
import threading
import time
from dataclasses import dataclass
from typing import Callable, Optional

import coopstorage.storage.loc_load.dcs as dcs
import coopstorage.storage.loc_load.evaluators as evaluators
from coopstorage.storage.loc_load.qualifiers import ContainerQualifier, LocationQualifier
from coopstorage.storage.loc_load.storage import Storage
from coopstorage.storage.loc_load.transferRequest import TransferRequestCriteria
from cooptools.qualifiers import PatternMatchQualifier, WhiteBlackListQualifier

logger = logging.getLogger(__name__)


# ── SimulationConfig ──────────────────────────────────────────────────────────

@dataclass
class SimulationConfig:
    """Config for the continuous randomised add/move/remove simulation."""
    min_fill_pct:  float = 0.15
    max_fill_pct:  float = 0.85
    add_weight:    float = 0.45
    move_weight:   float = 0.40
    remove_weight: float = 0.15


SIM_DEFAULT = SimulationConfig()


def run_simulation(
    storage: Storage,
    cfg: SimulationConfig = None,
    delay_provider: Optional[Callable[[], float]] = None,
    stop_event: Optional[threading.Event] = None,
    ops_counter: Optional[list] = None,
) -> None:
    """Run a continuous randomised add/move/remove loop on *storage* until
    ``stop_event`` is set (or forever if None).

    Args:
        storage:        A pre-built Storage instance to operate on.
        cfg:            SimulationConfig; defaults to SIM_DEFAULT.
        delay_provider: Optional callable returning seconds to sleep after each op.
        stop_event:     threading.Event that signals the loop to exit cleanly.
        ops_counter:    Optional single-element list [n] incremented each op so
                        callers can read total ops without a lock.
    """
    if cfg is None:
        cfg = SIM_DEFAULT
    if stop_event is None:
        stop_event = threading.Event()
    if ops_counter is None:
        ops_counter = [0]

    container_counter = 0
    max_concurrent    = sum(loc.Capacity for loc in storage.Locations.values())
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
        storage.handle_transfer_requests(
            [TransferRequestCriteria(
                new_container=dcs.Container(id=cid),
                dest_loc_query_args=LocationQualifier(at_least_capacity=1, has_addable_position=True),
            )],
            dest_loc_evaluator=evaluators.fewest_containers,
        )

    def _unblock(target_container) -> bool:
        container_locs = storage.ContainerLocs
        target_loc = next(
            (loc for c, loc in container_locs.items() if c.id == target_container.id),
            None,
        )
        if target_loc is None:
            return False
        state    = [target_loc.ContainerPositions.get(i) for i in range(target_loc.Capacity)]
        cp       = target_loc.Meta.channel_processor
        blockers = cp.get_blocking_loads(target_container.id, state)
        for blocker_id in blockers:
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
        if not _unblock(c):
            return
        storage.handle_transfer_requests([
            TransferRequestCriteria(
                container_query_args=ContainerQualifier(
                    pattern=PatternMatchQualifier(id=c.id)
                ),
                delete_container_on_transfer=True,
            )
        ])

    def _do_move():
        containers = list(storage.get_containers().values())
        if not containers:
            return
        c = random.choice(containers)
        if not _unblock(c):
            return
        storage.handle_transfer_requests(
            [TransferRequestCriteria(
                container_query_args=ContainerQualifier(
                    pattern=PatternMatchQualifier(id=c.id)
                ),
                dest_loc_query_args=LocationQualifier(at_least_capacity=1, has_addable_position=True),
            )],
            dest_loc_evaluator=evaluators.fewest_containers,
        )

    while not stop_event.is_set():
        count = _current_count()
        fill  = count / max_concurrent if max_concurrent > 0 else 0

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

        ops_counter[0] += 1

        if delay_provider is not None:
            time.sleep(delay_provider())

        now = time.perf_counter()
        if now - last_status >= STATUS_INTERVAL:
            elapsed = now - start
            rate    = ops_counter[0] / elapsed if elapsed > 0 else 0
            logger.info(
                "sim  ops=%d  concurrent=%d/%d  fill=%.0f%%  elapsed=%.0fs  rate=%.0f/s",
                ops_counter[0], count, max_concurrent, fill * 100, elapsed, rate,
            )
            last_status = now


# ── ShowcaseConfig ────────────────────────────────────────────────────────────

@dataclass
class ShowcaseConfig:
    """One location per processor type, all operated in lock-step each iteration."""
    min_fill_pct: float = 0.20
    max_fill_pct: float = 0.80


SHOWCASE = ShowcaseConfig()


def run_showcase_sim(
    storage: Storage,
    cfg: ShowcaseConfig = None,
    delay_provider: Optional[Callable[[], float]] = None,
    stop_event: Optional[threading.Event] = None,
    ops_counter: Optional[list] = None,
) -> None:
    """Showcase sim: each iteration adds or removes one container at every
    location in lock-step so channel processor behaviour differences are visible.
    """
    if cfg is None:
        cfg = SHOWCASE
    if stop_event is None:
        stop_event = threading.Event()
    if ops_counter is None:
        ops_counter = [0]

    container_counter = 0
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
                except Exception as e:
                    logger.warning("showcase  add  loc=%s  error=%s: %s", loc.Id, type(e).__name__, e)
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
                except Exception as e:
                    logger.warning("showcase  remove  loc=%s  error=%s: %s", loc.Id, type(e).__name__, e)

        ops_counter[0] += 1

        if delay_provider is not None:
            time.sleep(delay_provider())

        now = time.perf_counter()
        if now - last_status >= STATUS_INTERVAL:
            elapsed = now - start
            rate    = ops_counter[0] / elapsed if elapsed > 0 else 0
            logger.info(
                "showcase  ops=%d  containers=%d/%d  fill=%.0f%%  elapsed=%.0fs  rate=%.0f/s",
                ops_counter[0], count, max_concurrent, fill * 100, elapsed, rate,
            )
            last_status = now
