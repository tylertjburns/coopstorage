from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Query

from coopstorage.storage.api.routers.v1.heatmap_tracker import HeatmapTracker


class HeatmapRouter:
    def __init__(self, tracker: HeatmapTracker):
        self._tracker = tracker
        self.router   = self._build()

    def _build(self) -> APIRouter:
        router  = APIRouter()
        tracker = self._tracker

        @router.get("/heatmap")
        def get_heatmap(
            start: Optional[str] = Query(None, description="ISO 8601 UTC datetime, range start (inclusive)"),
            end:   Optional[str] = Query(None, description="ISO 8601 UTC datetime, range end (inclusive)"),
        ) -> dict:
            start_dt = datetime.fromisoformat(start) if start else None
            end_dt   = datetime.fromisoformat(end)   if end   else None
            return tracker.get_counts(start=start_dt, end=end_dt)

        return router
