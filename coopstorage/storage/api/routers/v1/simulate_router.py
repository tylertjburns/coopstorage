import logging
import threading
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from coopstorage.storage.loc_load.storage import Storage
from coopstorage.simulation import (
    SimulationConfig, ShowcaseConfig,
    run_simulation, run_showcase_sim,
)

logger = logging.getLogger(__name__)


class SimulationConfigAPI(BaseModel):
    mode: str = "random"                # "random" or "showcase"
    min_fill_pct: float = 0.15
    max_fill_pct: float = 0.85
    add_weight: float = 0.45
    move_weight: float = 0.40
    remove_weight: float = 0.15
    delay_ms: float = 0.0               # ms to sleep between ops (0 = as fast as possible)


# Module-level simulation state — one simulation at a time per server instance.
_sim_thread: Optional[threading.Thread] = None
_sim_stop:   Optional[threading.Event]  = None
_sim_ops:    list = [0]                 # single-element list used as shared counter


def simulate_router_factory(storage: Storage) -> APIRouter:
    router = APIRouter(prefix="/simulate", tags=["simulate"])

    @router.post("/start")
    def start_simulation(body: SimulationConfigAPI):
        global _sim_thread, _sim_stop, _sim_ops

        if _sim_thread is not None and _sim_thread.is_alive():
            raise HTTPException(status_code=409, detail="Simulation already running. POST /simulate/stop first.")

        _sim_stop = threading.Event()
        _sim_ops  = [0]
        delay     = (body.delay_ms / 1000.0) if body.delay_ms > 0 else None
        delay_fn  = (lambda: delay) if delay else None

        if body.mode == "showcase":
            cfg = ShowcaseConfig(
                min_fill_pct=body.min_fill_pct,
                max_fill_pct=body.max_fill_pct,
            )
            target = run_showcase_sim
            kwargs = dict(storage=storage, cfg=cfg, delay_provider=delay_fn,
                          stop_event=_sim_stop, ops_counter=_sim_ops)
        else:
            cfg = SimulationConfig(
                min_fill_pct=body.min_fill_pct,
                max_fill_pct=body.max_fill_pct,
                add_weight=body.add_weight,
                move_weight=body.move_weight,
                remove_weight=body.remove_weight,
            )
            target = run_simulation
            kwargs = dict(storage=storage, cfg=cfg, delay_provider=delay_fn,
                          stop_event=_sim_stop, ops_counter=_sim_ops)

        _sim_thread = threading.Thread(target=target, kwargs=kwargs, daemon=True)
        _sim_thread.start()
        logger.info("Simulation started  mode=%s  delay_ms=%.1f", body.mode, body.delay_ms)
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
        return {"status": "stopped", "ops": ops}

    @router.get("/status")
    def simulation_status():
        running = _sim_thread is not None and _sim_thread.is_alive()
        count   = len(storage.ContainerLocs)
        locs    = storage.Locations
        cap     = sum(loc.Capacity for loc in locs.values()) if locs else 0
        fill    = count / cap if cap > 0 else 0.0
        return {
            "running":  running,
            "ops":      _sim_ops[0],
            "containers": count,
            "capacity": cap,
            "fill_pct": round(fill * 100, 1),
        }

    return router
