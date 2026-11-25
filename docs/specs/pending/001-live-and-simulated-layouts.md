# Spec 001 — Live and simulated layouts

> **Status:** PENDING
> **Criticality:** P1 for the hosted service. Today a redeploy wipes every container, and the simulator writes into the same storage that real callers would use.
> **Effort:** L (phases 1–6, each its own PR)
> **Prerequisites:** none. Rollout Phase 4 (tenant scoping) builds on this spec's layout-scoped routes and migration tooling.

**Goal:** Every layout runs **live** or as a **simulation**, never both. Live layouts keep their containers and pending transfer requests in Postgres across restarts. A simulation is an in-memory copy of a live layout, so generating containers and running the simulator can never change real data.

---

## Current state

| Concern | Today |
| --- | --- |
| Layouts and locations | Saved in Postgres through `LayoutManager` (`coopstorage/storage/layout_manager.py`) and `/v2/layouts/*` |
| Containers and transfer requests | Always in memory. `LayoutManager._create_storage` passes only a location store to `StorageDataStore`, so containers and transfer requests fall back to `InMemoryDataStore` |
| Visualizer, simulator, generator | Every v1 router (`routers/v1/`) is bound to one global `Storage` that belongs to no layout |
| Events | `Storage` publishes to global PyPubSub topics with no layout ID in the payload. `StorageEventBus` and `HeatmapTracker` subscribe to all of them, so once there is one `Storage` per layout, events from different layouts arrive mixed together |
| Schema | `containers` has a primary key of `id` alone, so two layouts can't reuse a container ID, and `transfers.container_id` has a foreign key to that single-column key. There is no migration tool: `init_db()` runs `metadata.create_all`, which never alters existing tables |
| Reservations | Pending `TransferRequest`s hold reservation tokens issued by `Storage`'s `ReservationProvider` (in memory by default). Saving the requests without the reservations would leave stale tokens after a restart |

## Design

### Two modes

- **Live** is the layout saved in Postgres. Containers and pending transfer requests are saved too. Real callers (and later, API-key clients from rollout Phase 3) write here. Simulation endpoints return `409 {"code": "layout_is_live"}` for a live layout.
- **Simulation** is created from a live layout with `POST /v2/layouts/{id}/simulations`. It copies the source layout's locations, and by default its current containers, into a `Storage` that lives only in memory, registered under a new ID. It's never written to Postgres, which:
  - **guarantees isolation:** no code path from a simulation reaches the live tables;
  - **keeps the simulator fast:** the simulator writes on every move, and none of those writes go to the database;
  - **costs persistence:** a simulation is lost on restart. That's acceptable, since anyone can create another one from the live layout.

  Request body: `{"include_containers": true}` (the default). Pass `false` to start from empty locations.

### Identity and events

- `Storage` gains a `layout_id`, and every published payload carries it.
- `StorageEventBus` subscriptions and `HeatmapTracker` filter by `layout_id`. One process-wide bus stays; a subscriber picks a layout when it subscribes.

### Routes

The v1 routers become layout-scoped under `/v2/layouts/{layout_id}/…`, and each one resolves its `Storage` through `LayoutManager`:

| Area | Live | Simulation |
| --- | --- | --- |
| containers, transfer-requests, snapshot, events, heatmap, tree | yes | yes |
| locations (already in v2) | yes | read-only (a copy's structure is fixed) |
| generate, simulate start/stop/status | `409 layout_is_live` | yes |
| `DELETE` | deletes the layout and everything in it | discards the simulation |

`GET /v2/layouts` keeps listing live layouts only. `GET /v2/layouts/{id}/simulations` lists the active copies of one layout. The v1 global-storage routes stay unchanged until the UI no longer uses them, and are then removed in their own PR.

### Persistence (live only)

- **`SqlContainerDataStore`** follows `SqlLocationDataStore`'s design: scoped to one layout, with an in-process cache that loads lazily. A `Container` is stored as JSON (`uom`, `contents`, `uom_capacities`, `resource_qualifier`, `uom_qualifier`) using explicit serialize and parse functions, not pickle, so a renamed class can't make saved rows unreadable. Lookups by ID normalize to `str`, because location slots store container IDs as strings once saved.
- **`SqlTransferRequestDataStore`** stores only *pending* requests in `transfers` (`status='pending'`). `criteria` is JSON (nested `ContainerQualifier`/`LocationQualifier`). Serializing it is the hardest part of this spec; see Open questions.
- **On startup**, a live layout reloads its pending requests and acquires their reservations again. A request that can't be re-reserved is marked `failed` and logged. It is never silently dropped.

### Schema and migrations

- Add **Alembic**. The first migration records the schema as it is today, and the second:
  - makes `containers`'s primary key `(id, layout_id)`, with `ON DELETE CASCADE` from `layouts`;
  - replaces `transfers.container_id`'s foreign key with a composite `(container_id, source_layout_id)` key, or drops it (decide when implementing);
  - leaves `layouts` unchanged. The live/simulation mode needs no column, because simulations are never saved.
- `init_db()` runs `alembic upgrade head` instead of `create_all`, on SQLite and Postgres alike.
- The production tables are empty today, so this migration needs no data backfill.

## Phases (one PR each)

1. **Migrations:** Alembic, a baseline migration, and the container/transfer key fix.
2. **Persistence:** both SQL stores, connected in `LayoutManager` for live layouts, plus re-reservation on startup.
3. **Per-layout events:** `Storage.layout_id`, the ID in every payload, and filtering in the bus and heatmap tracker.
4. **Layout-scoped routes:** port the v1 routers under `/v2/layouts/{id}/…`.
5. **Simulations:** the copy endpoint, an in-memory registry in `LayoutManager`, the mode guard, and simulate and generate routes that work only on a copy.
6. **UI:** the layout picker offers **Open live** and **Simulate**, and the visualizer runs on whichever layout is selected.

## Out of scope

- Tenant scoping of layouts (rollout Phase 4). The route shape here is chosen so a later `tenant_id` filter only changes `LayoutManager`'s lookups.
- Saving simulations, or turning a simulation into a live layout.
- Deleting the v1 global-storage routes (a follow-up once phase 6 ships).

## Open questions

- **Transfer criteria serialization:** `TransferRequestCriteria` nests qualifiers, a `Container`, and `PatternMatchQualifier`s from `cooptools`. If clean JSON round-tripping needs changes to those classes, make them in cooptools (an owned repo) rather than in a coopstorage-side copy.
- **Simulation limits:** cap the number of simulations per layout, and set an idle TTL, so a single-replica service can't run out of memory.

## Test cases

- A live layout's containers and pending transfer requests survive a `LayoutManager` restart against the same database.
- After a restart, a pending request whose reservation can't be acquired again ends up `failed`, not lost.
- A simulation copied with containers starts with the same container placement as its source. Starting the simulator and generating containers leaves the source's rows unchanged (checked by comparing the database before and after).
- `generate` and `simulate/start` against a live layout return `409 layout_is_live`.
- Two layouts reusing the same container ID don't collide.
- An SSE subscriber on layout A gets no events from layout B.
- Deleting a live layout cascades to its containers and transfers.
- Alembic upgrades an empty database, and a database created by the old `create_all`, to the same schema.

## Acceptance

- [ ] Phases 1–6 merged; each phase's tests pass on SQLite in CI.
- [ ] Hosted: containers registered on a live layout survive a redeploy.
- [ ] Hosted: running a simulation leaves its source layout's container count and placement unchanged.
