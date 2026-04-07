import logging
import threading
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from coopstorage.storage.loc_load.storage import Storage
from coopstorage.storage.loc_load.event_bus import StorageEventBus, StorageEvent
from coopstorage.simulation import (
    SimulationConfig, ShowcaseConfig,
    run_simulation, run_showcase_sim,
)
import coopstorage.storage.loc_load.evaluators as evaluators

logger = logging.getLogger(__name__)


_EVALUATORS = {
    "fewest_containers":            evaluators.fewest_containers,
    "random_score":                 evaluators.random_score,
    "max_available_capacity_pct":   evaluators.max_available_capacity_percentage,
    "least_available_capacity_pct": evaluators.least_available_capacity_percentage,
}


class SimulationConfigAPI(BaseModel):
    mode: str = "random"                # "random" or "showcase"
    min_fill_pct: float = 0.15
    max_fill_pct: float = 0.85
    add_weight: float = 0.45
    move_weight: float = 0.40
    remove_weight: float = 0.15
    delay_ms: float = 0.0               # ms to sleep between ops (0 = as fast as possible)
    dest_loc_evaluator: str = "fewest_containers"  # key into _EVALUATORS


# Module-level simulation state — one simulation at a time per server instance.
_sim_thread: Optional[threading.Thread] = None
_sim_stop:   Optional[threading.Event]  = None
_sim_ops:    list = [0]                 # single-element list used as shared counter

_STATUS_INTERVAL = 2.0  # seconds between periodic sim_status SSE pushes


def simulate_router_factory(storage: Storage, event_bus: StorageEventBus = None) -> APIRouter:
    router = APIRouter(prefix="/simulate", tags=["simulate"])

    def _current_status(running: bool, ops_counter: list) -> dict:
        locs  = storage.Locations
        cap   = sum(loc.Capacity for loc in locs.values()) if locs else 0
        count = len(storage.ContainerLocs)
        fill  = count / cap if cap > 0 else 0.0
        return {
            "running":    running,
            "ops":        ops_counter[0],
            "containers": count,
            "capacity":   cap,
            "fill_pct":   round(fill * 100, 1),
        }

    def _emit_status(running: bool, ops_counter: list):
        if event_bus is not None:
            event_bus._emit(StorageEvent('sim_status', _current_status(running, ops_counter)))

    def _status_emitter(stop_event: threading.Event, ops_counter: list):
        """Emit sim_status every _STATUS_INTERVAL seconds while the sim runs."""
        while not stop_event.wait(_STATUS_INTERVAL):
            _emit_status(running=True, ops_counter=ops_counter)

    @router.post("/start")
    def start_simulation(body: SimulationConfigAPI):
        global _sim_thread, _sim_stop, _sim_ops

        if _sim_thread is not None and _sim_thread.is_alive():
            raise HTTPException(status_code=409, detail="Simulation already running. POST /simulate/stop first.")

        _sim_stop = threading.Event()
        _sim_ops  = [0]
        delay_s  = body.delay_ms / 1000.0
        delay_fn = (lambda d=delay_s: d) if delay_s > 0 else None

        if body.mode == "showcase":
            cfg = ShowcaseConfig(
                min_fill_pct=body.min_fill_pct,
                max_fill_pct=body.max_fill_pct,
            )
            target = run_showcase_sim
            kwargs = dict(storage=storage, cfg=cfg, delay_provider=delay_fn,
                          stop_event=_sim_stop, ops_counter=_sim_ops)
        else:
            if body.dest_loc_evaluator not in _EVALUATORS:
                raise HTTPException(
                    status_code=422,
                    detail=f"Unknown dest_loc_evaluator '{body.dest_loc_evaluator}'. "
                           f"Valid options: {list(_EVALUATORS)}"
                )
            cfg = SimulationConfig(
                min_fill_pct=body.min_fill_pct,
                max_fill_pct=body.max_fill_pct,
                add_weight=body.add_weight,
                move_weight=body.move_weight,
                remove_weight=body.remove_weight,
            )
            target = run_simulation
            kwargs = dict(storage=storage, cfg=cfg, delay_provider=delay_fn,
                          stop_event=_sim_stop, ops_counter=_sim_ops,
                          dest_loc_evaluator=_EVALUATORS[body.dest_loc_evaluator])

        # Capture the ops list for this run so emitters share the same object
        current_ops = _sim_ops

        _sim_thread = threading.Thread(target=target, kwargs=kwargs, daemon=True)
        _sim_thread.start()

        # Periodic status emitter (shares stop event and ops list for this run)
        threading.Thread(target=_status_emitter, args=(_sim_stop, current_ops), daemon=True).start()

        logger.info("Simulation started  mode=%s  delay_ms=%.1f", body.mode, body.delay_ms)
        _emit_status(running=True, ops_counter=current_ops)
        return {"status": "started", "mode": body.mode}

    @router.post("/stop")
    def stop_simulation():
        global _sim_thread, _sim_stop

        if _sim_thread is None or not _sim_thread.is_alive():
            raise HTTPException(status_code=409, detail="No simulation is currently running.")

        _sim_stop.set()
        _sim_thread.join(timeout=5.0)
        ops = _sim_ops[0]
        _sim_thread = None
        logger.info("Simulation stopped  ops=%d", ops)
        _emit_status(running=False, ops_counter=_sim_ops)
        return {"status": "stopped", "ops": ops}

    @router.get("/status")
    def simulation_status():
        running = _sim_thread is not None and _sim_thread.is_alive()
        return _current_status(running, ops_counter=_sim_ops)

    return router
