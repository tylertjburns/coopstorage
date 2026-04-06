"""
location_map_tree.py
────────────────────
A dynamic hierarchy registry for storage locations. Levels are discovered as
locations are registered — no upfront schema required. Locations may have
different label sets; a location that skips an intermediate level is simply
absent from that level's index.

Usage
-----
    tree = LocationMapTree()

    tree.register('Zone0_Aisle1_Bay2_Shelf3_Loc0', zone=0, aisle=1, bay=2, shelf=3)
    tree.register('Zone0_Bay5_Loc0', zone=0, bay=5)   # skips aisle — fine

    tree.get_loc_ids(zone=0, bay=2)
    tree.get_children(zone=0, aisle=1)
    tree.get_siblings('Zone0_Aisle1_Bay2_Shelf3_Loc0')
    tree.get_path('Zone0_Aisle1_Bay2_Shelf3_Loc0')
    tree.get_all_at_level('bay')
    tree.occupancy(storage, zone=0)
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, List, Optional, Set, TYPE_CHECKING

from cooptools.protocols import UniqueIdentifier

if TYPE_CHECKING:
    from coopstorage.storage.loc_load.storage import Storage


class LocationMapTree:
    """Dynamic hierarchy registry for storage locations."""

    def __init__(self):
        # Global ordered list of level names in first-seen order
        self._levels_order: List[str] = []
        # loc_id → {level_name: value, ...}
        self._labels: Dict[UniqueIdentifier, Dict[str, Any]] = {}
        # (level_name, value) → set of loc_ids
        self._inverted: Dict[tuple, Set[UniqueIdentifier]] = defaultdict(set)

    # ── Registration ──────────────────────────────────────────────────────────

    def register(self, loc_id: UniqueIdentifier, **labels) -> None:
        """Register a location with its hierarchy labels.

        Level names are added to the global order on first-seen.
        A location need not supply every known level.
        """
        for level in labels:
            if level not in self._levels_order:
                self._levels_order.append(level)

        self._labels[loc_id] = dict(labels)

        for level, value in labels.items():
            self._inverted[(level, value)].add(loc_id)

    # ── Queries ───────────────────────────────────────────────────────────────

    def get_loc_ids(self, **labels) -> List[UniqueIdentifier]:
        """Return all loc_ids matching every supplied label (partial match).

        Passing no labels returns every registered location.
        """
        if not labels:
            return list(self._labels.keys())

        sets = [self._inverted.get((level, value), set()) for level, value in labels.items()]
        result = sets[0].copy()
        for s in sets[1:]:
            result &= s
        return list(result)

    def get_path(self, loc_id: UniqueIdentifier) -> Dict[str, Any]:
        """Return the full label dict for a location (its path from root)."""
        if loc_id not in self._labels:
            raise KeyError(f"Location '{loc_id}' is not registered in this tree")
        return dict(self._labels[loc_id])

    def get_children(self, **labels) -> List[Dict[str, Any]]:
        """Return distinct child-level label dicts one level deeper than supplied.

        'One level deeper' means the next level in global order that each
        matching location actually has. Locations that skip intermediate levels
        appear at their own natural next level.

        Example: get_children(zone=0) returns all distinct aisle-level dicts
        (or bay-level dicts for locs that skipped aisle).
        """
        candidates = self.get_loc_ids(**labels)
        if not candidates:
            return []

        # Depth of the deepest supplied label in global order
        supplied_depths = [
            self._levels_order.index(lv)
            for lv in labels
            if lv in self._levels_order
        ]
        current_depth = max(supplied_depths) if supplied_depths else -1

        seen: set = set()
        result = []

        for loc_id in candidates:
            loc_labels = self._labels[loc_id]
            # Find the next level this loc has after current_depth
            for depth, level in enumerate(self._levels_order):
                if depth <= current_depth:
                    continue
                if level not in loc_labels:
                    continue
                # Build child node dict: all labels this loc has up to this level
                child_dict = {
                    lv: loc_labels[lv]
                    for lv in self._levels_order[:depth + 1]
                    if lv in loc_labels
                }
                key = tuple(sorted(child_dict.items()))
                if key not in seen:
                    seen.add(key)
                    result.append(child_dict)
                break  # only one child level per loc

        return result

    def get_siblings(self, loc_id: UniqueIdentifier) -> List[UniqueIdentifier]:
        """Return all loc_ids that share the same parent-level labels.

        Parent = all labels except the last one in global order that this
        location has.
        """
        path = self.get_path(loc_id)
        loc_levels = [lv for lv in self._levels_order if lv in path]
        if len(loc_levels) <= 1:
            # No parent — siblings are all locs at the same single level value
            parent_labels = {}
        else:
            parent_levels = loc_levels[:-1]
            parent_labels = {lv: path[lv] for lv in parent_levels}

        return [lid for lid in self.get_loc_ids(**parent_labels) if lid != loc_id]

    def get_all_at_level(self, level: str) -> Dict[tuple, List[UniqueIdentifier]]:
        """Return a mapping of node_key → [loc_ids] for every distinct node
        at the given level name.

        Node keys are tuples of (level, value) pairs for all labels the loc
        has up to and including ``level``, in global order.
        Only locations that have the given level label are included.
        """
        if level not in self._levels_order:
            raise ValueError(
                f"'{level}' has not been seen; known levels: {self._levels_order}"
            )
        depth = self._levels_order.index(level)
        levels_up_to = self._levels_order[:depth + 1]

        result: Dict[tuple, List[UniqueIdentifier]] = defaultdict(list)
        for loc_id, loc_labels in self._labels.items():
            if level not in loc_labels:
                continue
            node_key = tuple(
                (lv, loc_labels[lv])
                for lv in levels_up_to
                if lv in loc_labels
            )
            result[node_key].append(loc_id)

        return dict(result)

    def occupancy(self, storage: Storage, **labels) -> Dict[str, Any]:
        """Rolled-up occupancy stats for the subtree matching labels.

        Returns
        -------
        dict with keys:
            used       — occupied slots
            capacity   — total slot capacity
            pct        — used / capacity (0.0 if capacity == 0)
            loc_count  — number of locations in the subtree
        """
        loc_ids = self.get_loc_ids(**labels)
        all_locs = storage.Locations

        used = 0
        capacity = 0
        for loc_id in loc_ids:
            loc = all_locs.get(loc_id)
            if loc is None:
                continue
            capacity += loc.Capacity
            used += len(loc.ContainerIds)

        return {
            'used': used,
            'capacity': capacity,
            'pct': used / capacity if capacity > 0 else 0.0,
            'loc_count': len(loc_ids),
        }

    # ── Inspection ────────────────────────────────────────────────────────────

    @property
    def levels(self) -> List[str]:
        """Global level order in first-seen order."""
        return list(self._levels_order)

    def __len__(self) -> int:
        return len(self._labels)

    def __repr__(self) -> str:
        return (
            f"LocationMapTree(levels={self._levels_order}, "
            f"registered={len(self._labels)})"
        )
