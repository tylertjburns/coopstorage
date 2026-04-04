# coopstorage

A Python library for embedded storage tracking — models physical storage locations, containers, and the channel-processor rules that govern how items flow in and out of each slot.

---

## Overview

`coopstorage` provides:

- **Locations** — physical storage slots with configurable capacity, dimensions, and channel-processor type
- **Containers** — items stored at locations, each with a UoM, optional contents, and resource qualifiers
- **Channel processors** — pluggable rules that control which slots are addable/removable (FIFO, LIFO, OMNI, NoFlow, push variants, etc.)
- **Transfer requests** — declarative add/move/remove operations resolved against qualifier criteria
- **Location qualifiers** — filter locations by capacity, dimensions, UoM, resource type, occupied state, channel accessibility, and more
- **Live visualizer** — browser-based isometric/top-down view with real-time SSE updates, slot overlays, UOM icons, and a legend

---

## Channel Processor Types

| Type | Add | Remove | Flow |
| --- | --- | --- | --- |
| `AllAvailableChannelProcessor` | any empty slot | any occupied slot | none |
| `AllAvailableFlowChannelProcessor` | any empty slot | any occupied slot | forward |
| `AllAvailableFlowBackwardChannelProcessor` | any empty slot | any occupied slot | backward |
| `FIFOFlowChannelProcessor` | back of queue | front (oldest) | forward |
| `FIFOFlowBackwardChannelProcessor` | front (push) | front (oldest) | backward |
| `FIFONoFlowChannelProcessor` | deepest open slot | deepest occupied (oldest) | none |
| `FIFONoFlowPushChannelProcessor` | slot 0 (push) | deepest occupied (oldest) | none |
| `LIFOFlowChannelProcessor` | back of queue | front (newest) | forward |
| `LIFOFlowBackwardChannelProcessor` | front (push) | front (newest) | backward |
| `LIFONoFlowChannelProcessor` | deepest open slot | shallowest occupied (newest) | none |
| `LIFONoFlowPushChannelProcessor` | slot 0 (push) | shallowest occupied (newest) | none |
| `OMNIChannelProcessor` | adjacent to pack (either end) | either end | none |
| `OMNIFlowChannelProcessor` | adjacent to pack (either end) | either end | forward |
| `OMNIFlowBackwardChannelProcessor` | adjacent to pack (either end) | either end | backward |

---

## Quick Start

```python
from coopstorage.storage.loc_load.storage import Storage
from coopstorage.storage.loc_load.location import Location
import coopstorage.storage.loc_load.dcs as dcs
import coopstorage.storage.loc_load.channel_processors as cps
from coopstorage.storage.loc_load.qualifiers import LocationQualifier
from coopstorage.storage.loc_load.transferRequest import TransferRequestCriteria

# Build storage with two locations
loc_a = Location(
    id='A',
    location_meta=dcs.LocationMeta(
        dims=(10, 10, 5),
        channel_processor=cps.FIFOFlowChannelProcessor(),
        capacity=5,
    ),
    coords=(0, 0, 0),
)
loc_b = Location(
    id='B',
    location_meta=dcs.LocationMeta(
        dims=(10, 10, 5),
        channel_processor=cps.LIFOFlowBackwardChannelProcessor(),
        capacity=5,
    ),
    coords=(15, 0, 0),
)

storage = Storage(locs=[loc_a, loc_b])

# Add a container to the first available location
storage.handle_transfer_requests([
    TransferRequestCriteria(
        new_container=dcs.Container(id='C001'),
        dest_loc_query_args=LocationQualifier(at_least_capacity=1, has_addable_position=True),
    )
])
```

---

## Location Qualifiers

`LocationQualifier` filters candidate locations during transfer resolution:

```python
from coopstorage.storage.loc_load.qualifiers import LocationQualifier, ContainerQualifier
from cooptools.qualifiers import PatternMatchQualifier, WhiteBlackListQualifier

# Destination: must have capacity, an accessible drop slot, and accept the container's UoM
LocationQualifier(
    at_least_capacity=1,
    has_addable_position=True,
)

# Source: must contain a container matching a pattern
LocationQualifier(
    has_all_containers=[ContainerQualifier(pattern=PatternMatchQualifier(regex='^C00'))]
)
```

Key parameters:

| Parameter | Description |
| --- | --- |
| `at_least_capacity` | Minimum number of free slots |
| `has_addable_position` | Channel processor has an accessible drop position |
| `is_occupied` | True/False filter on whether any container is present |
| `has_any_containers` | At least one container satisfies any of the given qualifiers |
| `has_all_containers` | For each qualifier, at least one container satisfies it |
| `has_content` | Total qty of a resource/UoM across all containers meets a minimum |
| `uom_qualifier` / `ignore_uom_qualifier` | Container UoM must be allowed by location's whitelist |
| `resource_type_qualifier` / `ignore_resource_type_qualifier` | Container resource types must be allowed |
| `min_slot_dims` | All slot dimensions must be >= this |
| `reserved` | Filter on reservation state |

---

## Visualizer

Start a live browser visualizer alongside a benchmark or simulation:

```bash
# Showcase: one of each channel processor type, lock-step add/remove
python run_viz_benchmark.py --mode showcase

# Continuous randomized simulation
python run_viz_benchmark.py --mode sim --config small

# Fixed benchmark workload
python run_viz_benchmark.py --mode benchmark --config medium

# Options
python run_viz_benchmark.py --delay 0.05 --log-level DEBUG --port 1219
```

The visualizer is served at `http://localhost:1219/static/index.html`.

**Slot overlays:**

| Color | Meaning |
| --- | --- |
| Green fill | Occupied |
| Grey fill | Available |
| Blue outline | Droppable (addable position) |
| Purple outline | Retrievable (removable position) |

Each container label shows a unique icon per UoM type with a live legend.

---

## Running Tests

```bash
python -m pytest tests/ -v
```

---

## License

MIT
