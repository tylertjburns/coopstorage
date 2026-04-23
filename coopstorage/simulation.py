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
from coopstorage.storage.loc_load.reservation_provider import ReservationFailedError, RateLimitedError
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
    dest_loc_evaluator: Optional[Callable] = None,
    on_status: Optional[Callable[[dict], None]] = None,
) -> None:
    """Run a continuous randomised add/move/remove loop on *storage* until
    ``stop_event`` is set (or forever if None).

    Args:
        storage:            A pre-built Storage instance to operate on.
        cfg:                SimulationConfig; defaults to SIM_DEFAULT.
        delay_provider:     Optional callable returning seconds to sleep after each op.
        stop_event:         threading.Event that signals the loop to exit cleanly.
        ops_counter:        Optional single-element list [n] incremented each op so
                            callers can read total ops without a lock.
        dest_loc_evaluator: Evaluator for destination location selection in add/move ops.
                            Defaults to evaluators.fewest_containers.
        on_status:          Optional callback invoked periodically with a status dict:
                            {'running': bool, 'ops': int, 'containers': int,
                             'capacity': int, 'fill_pct': float}
    """
    if cfg is None:
        cfg = SIM_DEFAULT
    if stop_event is None:
        stop_event = threading.Event()
    if ops_counter is None:
        ops_counter = [0]
    if dest_loc_evaluator is None:
        dest_loc_evaluator = evaluators.random_score

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
                dest_loc_query_args=LocationQualifier(at_least_capacity=1, 
                                                      has_addable_position=True,
                                                      reserved=False),
            )],
            dest_loc_evaluator=dest_loc_evaluator,
        )

    def _do_remove():
        storage.handle_transfer_requests([
            TransferRequestCriteria(
                container_query_args=ContainerQualifier(
                    reserved=False
                ),
                delete_container_on_transfer=True,
            )
        ])

    def _do_move():
        storage.handle_transfer_requests(
            [TransferRequestCriteria(
                container_query_args=ContainerQualifier(
                    reserved=False
                ),
                dest_loc_query_args=LocationQualifier(at_least_capacity=1, 
                                                      has_addable_position=True,
                                                      reserved=False),
            )],
            dest_loc_evaluator=dest_loc_evaluator,
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

        def _run_op():
            if op == 'add':
                _do_add()
            elif op == 'move':
                _do_move()
            else:
                _do_remove()

        retry_after = None
        try:
            _run_op()
        except ReservationFailedError as e:
            if isinstance(e.__cause__, RateLimitedError):
                retry_after = e.__cause__.retry_after
            else:
                logger.warning("sim  op=%s  ReservationFailed: %s", op, e)
        except Exception as e:
            logger.warning("sim  op=%s  error=%s: %s", op, type(e).__name__, e)

        while retry_after is not None and not stop_event.is_set():
            wait = min(10.0, retry_after)
            logger.warning(
                "sim  op=%s  rate-limited (retryAfter=%.1fs); retrying in %.0fs",
                op, retry_after, wait,
            )
            if stop_event.wait(wait):
                break
            retry_after = None
            try:
                _run_op()
            except ReservationFailedError as e:
                if isinstance(e.__cause__, RateLimitedError):
                    retry_after = e.__cause__.retry_after
                else:
                    logger.warning("sim  op=%s  ReservationFailed on retry: %s", op, e)
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
            if on_status is not None:
                on_status({
                    'running':    True,
                    'ops':        ops_counter[0],
                    'containers': count,
                    'capacity':   max_concurrent,
                    'fill_pct':   round(fill * 100, 1),
                })
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
    on_status: Optional[Callable[[dict], None]] = None,
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

        def _showcase_op_with_retry(label: str, criteria_fn):
            retry_after = None
            try:
                storage.handle_transfer_requests(criteria_fn())
            except ReservationFailedError as e:
                if isinstance(e.__cause__, RateLimitedError):
                    retry_after = e.__cause__.retry_after
                else:
                    logger.warning("showcase  %s  ReservationFailed: %s", label, e)
            except Exception as e:
                logger.warning("showcase  %s  error=%s: %s", label, type(e).__name__, e)

            while retry_after is not None and not stop_event.is_set():
                wait = min(10.0, retry_after)
                logger.warning(
                    "showcase  %s  rate-limited (retryAfter=%.1fs); retrying in %.0fs",
                    label, retry_after, wait,
                )
                if stop_event.wait(wait):
                    break
                retry_after = None
                try:
                    storage.handle_transfer_requests(criteria_fn())
                except ReservationFailedError as e:
                    if isinstance(e.__cause__, RateLimitedError):
                        retry_after = e.__cause__.retry_after
                    else:
                        logger.warning("showcase  %s  ReservationFailed on retry: %s", label, e)
                except Exception as e:
                    logger.warning("showcase  %s  error=%s: %s", label, type(e).__name__, e)

        if op == 'add':
            for loc in storage.Locations.values():
                if not loc.get_addable_positions():
                    continue
                cid = _new_cid()
                _showcase_op_with_retry(
                    label=f"add loc={loc.Id}",
                    criteria_fn=lambda loc=loc, cid=cid: [
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
                    ],
                )
        else:
            for loc in storage.Locations.values():
                removable = loc.get_removable_positions()
                if not removable:
                    continue
                container_id = loc.ContainerPositions.get(random.choice(removable))
                if container_id is None:
                    continue
                _showcase_op_with_retry(
                    label=f"remove loc={loc.Id}",
                    criteria_fn=lambda container_id=container_id: [
                        TransferRequestCriteria(
                            container_query_args=ContainerQualifier(
                                pattern=PatternMatchQualifier(id=container_id)
                            ),
                            delete_container_on_transfer=True,
                        )
                    ],
                )

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
            if on_status is not None:
                on_status({
                    'running':    True,
                    'ops':        ops_counter[0],
                    'containers': count,
                    'capacity':   max_concurrent,
                    'fill_pct':   round(fill * 100, 1),
                })
            last_status = now
