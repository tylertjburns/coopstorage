// ─── Builder mode ─────────────────────────────────────────────────────────────
// Entry point: _startModePicker() — called from the final <script> tag.
//
// Flow:
//   Layout picker overlay (on load)  ──→  select or + New
//     └─ _selectLayout(id)
//          └─ loadLayoutLocations()
//               └─ canvas shows layout; HUD shows Simulate / Build toggle
//
// HUD modes (once a layout is active):
//   Simulate — ghost off; read-only view of the layout
//   Build    — ghost follows cursor; click to place; zone list auto-expands

var LAYOUT_ID         = null;
var builderModeActive = false;
var placingZone       = false;   // overrides stub in index.html
var ghostLocs         = [];
var ghostOrigin       = null;
var posPinned         = false;

const btnBuild        = document.getElementById('btn-build');
const btnSimulate     = document.getElementById('btn-mode-simulate');
const layoutHud       = document.getElementById('layout-hud');
const layoutHudName   = document.getElementById('layout-hud-name');
const builderPanel    = document.getElementById('builder-panel');
const zonesPanel      = document.getElementById('zones-panel');
const btnZones        = document.getElementById('btn-zones');

// ── Layout picker ─────────────────────────────────────────────────────────────

function _startModePicker() {
  try {
    const picker = document.getElementById('mode-picker');
    picker.classList.remove('hidden');

    document.getElementById('btn-create-layout').addEventListener('click', async () => {
      const name = document.getElementById('new-layout-name').value.trim();
      if (!name) return;
      await _createNewLayout(name);
    });

    document.getElementById('new-layout-name').addEventListener('keydown', async e => {
      if (e.key !== 'Enter') return;
      const name = e.target.value.trim();
      if (!name) return;
      await _createNewLayout(name);
    });

    document.getElementById('btn-layout-home').addEventListener('click', () => {
      _returnToLayoutPicker();
    });

    _loadLayoutList();
  } catch (err) {
    console.error('[builder-mode] _startModePicker failed:', err);
    const listEl = document.getElementById('layout-list');
    if (listEl) listEl.innerHTML = `<div style="color:#f85149;font-size:11px">JS error: ${err.message}</div>`;
  }
}

window._startModePicker = _startModePicker;

async function _loadLayoutList() {
  const listEl = document.getElementById('layout-list');
  listEl.innerHTML = '<div id="layout-list-empty">Loading…</div>';
  try {
    const res = await fetch('/v2/layouts');
    if (!res.ok) throw new Error(`HTTP ${res.status} — is the server running with a layout manager?`);
    const layouts = await res.json();
    _renderLayoutList(layouts);
  } catch (err) {
    listEl.innerHTML = `<div id="layout-list-empty" style="color:#f85149">${_escHtml(err.message)}</div>`;
  }
}

function _renderLayoutList(layouts) {
  const listEl = document.getElementById('layout-list');
  if (layouts.length === 0) {
    listEl.innerHTML = '<div id="layout-list-empty">No layouts yet — create one below.</div>';
    return;
  }
  listEl.innerHTML = '';
  for (const layout of layouts) {
    const div = document.createElement('div');
    div.className = 'layout-item';
    div.innerHTML = `
      <div>${_escHtml(layout.name || layout.id)}</div>
      <div class="layout-item-meta">${_escHtml(layout.id)}${layout.description ? ' \xb7 ' + _escHtml(layout.description) : ''}</div>
    `;
    div.addEventListener('click', () => _selectLayout(layout.id, layout.name || layout.id));
    listEl.appendChild(div);
  }
}

async function _createNewLayout(name) {
  const btn = document.getElementById('btn-create-layout');
  btn.disabled = true;
  try {
    const res = await fetch('/v2/layouts', {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify({ name }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      alert(`Failed to create layout:\n${err.detail || res.statusText}`);
      return;
    }
    const layout = await res.json();
    await _selectLayout(layout.id, layout.name || layout.id);
  } catch (err) {
    alert(`Failed to create layout: ${err}`);
  } finally {
    btn.disabled = false;
  }
}

async function _selectLayout(id, name) {
  LAYOUT_ID = id;
  document.getElementById('mode-picker').classList.add('hidden');

  layoutHudName.textContent = name || id;
  layoutHud.classList.add('visible');

  document.getElementById('btn-sim-start').style.display = 'none';
  document.getElementById('btn-sim-stop').style.display  = 'none';
  document.getElementById('sim-status').style.display    = 'none';

  history.pushState({ layoutId: id }, '', '?layout=' + encodeURIComponent(id));

  _setLayoutMode('simulate');

  try {
    statusEl.textContent = 'Loading layout…';
    await loadLayoutLocations();
  } catch (err) {
    statusEl.textContent = `Failed to load layout: ${err.message}`;
  }
}

function _returnToLayoutPicker() {
  if (placingZone) _exitGhost();
  builderModeActive = false;
  LAYOUT_ID = null;
  locations.clear();
  _rebuildIndices();
  _markBgDirty();
  forceRender();

  document.getElementById('btn-sim-start').style.display = '';
  document.getElementById('btn-sim-stop').style.display  = '';
  document.getElementById('sim-status').style.display    = '';

  history.pushState({}, '', location.pathname);

  layoutHud.classList.remove('visible');
  layoutHudName.textContent = '';
  builderPanel.classList.remove('visible');
  canvas.classList.remove('builder-mode', 'placing-mode');
  zonesPanel.classList.remove('visible');
  btnZones.classList.remove('active');

  _buildZoneList();

  const picker = document.getElementById('mode-picker');
  picker.classList.remove('hidden');
  document.getElementById('new-layout-name').value = '';
  _loadLayoutList();
}

// ── Layout mode toggle (Simulate / Build) ─────────────────────────────────────

function _setLayoutMode(mode) {
  if (mode === 'build') {
    builderModeActive = true;
    btnBuild.classList.add('active');
    btnSimulate.classList.remove('active');
    builderPanel.classList.add('visible');
    canvas.classList.add('builder-mode');
    zonesPanel.classList.add('visible');
    btnZones.classList.add('active');
    _enterGhost();
  } else {
    builderModeActive = false;
    _exitGhost();
    btnSimulate.classList.add('active');
    btnBuild.classList.remove('active');
    builderPanel.classList.remove('visible');
    canvas.classList.remove('builder-mode');
    forceRender();
  }
}

btnBuild.addEventListener('click', () => _setLayoutMode('build'));
btnSimulate.addEventListener('click', () => _setLayoutMode('simulate'));
document.getElementById('btn-builder-close').addEventListener('click', () => _setLayoutMode('simulate'));

btnZones.addEventListener('click', () => {
  const visible = zonesPanel.classList.toggle('visible');
  btnZones.classList.toggle('active', visible);
});

function _escHtml(s) {
  return String(s)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;')
    .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

// ── Ghost enter / exit ────────────────────────────────────────────────────────

function _enterGhost() {
  placingZone = true;
  canvas.classList.add('placing-mode');
}

function _exitGhost() {
  placingZone  = false;
  ghostLocs    = [];
  ghostOrigin  = null;
  posPinned    = false;
  const pinBtn = document.getElementById('btn-pin-pos');
  if (pinBtn) {
    pinBtn.classList.remove('pinned');
    pinBtn.title = 'Pin position — ghost stays at typed coords';
  }
  canvas.classList.remove('placing-mode');
}

// ── Load layout locations ─────────────────────────────────────────────────────

async function loadLayoutLocations() {
  const res = await fetch(`/v2/layouts/${LAYOUT_ID}/locations`);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  const data = await res.json();
  locations.clear();
  for (const [id, loc] of Object.entries(data)) {
    locations.set(id, loc);
    _indexLoc(loc);
  }
  _rebuildIndices();
  _markBgDirty();
  statusEl.textContent = `Layout — ${locations.size} location${locations.size !== 1 ? 's' : ''}`;
  _buildZoneList();
  fitView();
}

// ── Builder params from form ──────────────────────────────────────────────────

function _builderParams() {
  const deg = parseFloat(document.getElementById('bld-rotation').value) || 0;
  return {
    zone:       document.getElementById('bld-zone').value.trim() || 'Z1',
    aisleCount: Math.max(1, parseInt(document.getElementById('bld-aisle-count').value, 10) || 1),
    bayCount:   Math.max(1, parseInt(document.getElementById('bld-bay-count').value,   10) || 4),
    shelfCount: Math.max(1, parseInt(document.getElementById('bld-shelf-count').value, 10) || 3),
    dimX:       parseFloat(document.getElementById('bld-dim-x').value)    || 1000,
    dimY:       parseFloat(document.getElementById('bld-dim-y').value)    || 1000,
    dimZ:       parseFloat(document.getElementById('bld-dim-z').value)    || 1000,
    strideX:    parseFloat(document.getElementById('bld-stride-x').value) || 1000,
    strideY:    parseFloat(document.getElementById('bld-stride-y').value) || 1000,
    strideZ:    parseFloat(document.getElementById('bld-stride-z').value) || 1000,
    zOrigin:    parseFloat(document.getElementById('bld-z-origin').value) || 0,
    capacity:   Math.max(1, parseInt(document.getElementById('bld-capacity').value, 10) || 1),
    processor:  document.getElementById('bld-processor').value,
    rotation:   deg * Math.PI / 180,
    aisleStyle: document.getElementById('bld-aisle-style').value,
    aisleWidth: parseFloat(document.getElementById('bld-aisle-width').value) || 2000,
  };
}

// Auto-sync stride ↔ dim when dim changes (only if stride still equals the old dim)
for (const axis of ['x', 'y', 'z']) {
  const dimEl    = document.getElementById(`bld-dim-${axis}`);
  const strideEl = document.getElementById(`bld-stride-${axis}`);
  dimEl._prevVal  = dimEl.value;
  dimEl.addEventListener('input', () => {
    if (parseFloat(strideEl.value) === parseFloat(dimEl._prevVal)) {
      strideEl.value = dimEl.value;
    }
    dimEl._prevVal = dimEl.value;
    if (placingZone && ghostOrigin) {
      ghostLocs = _computeZoneLocs(ghostOrigin[0], ghostOrigin[1], _builderParams());
      forceRender();
    }
  });
}

// Show/hide VNA aisle-width row; refresh ghost
document.getElementById('bld-aisle-style').addEventListener('change', () => {
  const isVna = document.getElementById('bld-aisle-style').value === 'vna';
  document.getElementById('bld-vna-row').style.display = isVna ? 'flex' : 'none';
  if (placingZone && ghostOrigin) {
    ghostLocs = _computeZoneLocs(ghostOrigin[0], ghostOrigin[1], _builderParams());
    forceRender();
  }
});

// ── Zone location computation ─────────────────────────────────────────────────

function _computeZoneLocs(originX, originY, params) {
  return params.aisleStyle === 'vna'
    ? _computeVnaLocs(originX, originY, params)
    : _computeLinearLocs(originX, originY, params);
}

function _computeLinearLocs(originX, originY, params) {
  const { zone, aisleCount, bayCount, shelfCount,
          dimX, dimY, dimZ, strideX, strideY, strideZ,
          zOrigin, capacity, processor, rotation } = params;
  const cosR = Math.cos(rotation), sinR = Math.sin(rotation);
  const locs = [];
  for (let a = 0; a < aisleCount; a++) {
    for (let b = 0; b < bayCount; b++) {
      for (let s = 0; s < shelfCount; s++) {
        // Bay direction: (cosR, sinR); aisle direction: (-sinR, cosR)
        const wx = originX + b * strideX * cosR - a * strideY * sinR;
        const wy = originY + b * strideX * sinR + a * strideY * cosR;
        locs.push({
          id:          `${zone}-a${a}-b${b}-s${s}`,
          coords:      [wx, wy, zOrigin + s * strideZ],
          meta:        { dims: [dimX, dimY, dimZ], channel_processor: processor, capacity,
                         channel_axis: 0, delete_on_receive: false },
          slots:       Array(capacity).fill(null),
          containers:  {},
          tree_path:   { zone, aisle: a, bay: b, shelf: s },
          tree_labels: { zone, aisle: a, bay: b, shelf: s },
        });
      }
    }
  }
  return locs;
}

function _computeVnaLocs(originX, originY, params) {
  const { zone, aisleCount, bayCount, shelfCount,
          dimX, dimY, dimZ, strideX, strideY, strideZ,
          zOrigin, capacity, processor, aisleWidth, rotation } = params;
  const cosR = Math.cos(rotation), sinR = Math.sin(rotation);
  const locs = [];
  for (let a = 0; a < aisleCount; a++) {
    for (const side of ['L', 'R']) {
      // L row at aisle-pair origin; R row offset by (dimY + aisleWidth) along the aisle axis
      const sideOff = side === 'L' ? 0 : dimY + aisleWidth;
      for (let b = 0; b < bayCount; b++) {
        for (let s = 0; s < shelfCount; s++) {
          const bx = b * strideX;
          const ay = a * strideY + sideOff;
          const wx = originX + bx * cosR - ay * sinR;
          const wy = originY + bx * sinR + ay * cosR;
          locs.push({
            id:          `${zone}-a${a}${side}-b${b}-s${s}`,
            coords:      [wx, wy, zOrigin + s * strideZ],
            meta:        { dims: [dimX, dimY, dimZ], channel_processor: processor, capacity,
                           channel_axis: 0, delete_on_receive: false },
            slots:       Array(capacity).fill(null),
            containers:  {},
            tree_path:   { zone, aisle: `${a}${side}`, bay: b, shelf: s },
            tree_labels: { zone, aisle: `${a}${side}`, bay: b, shelf: s },
          });
        }
      }
    }
  }
  return locs;
}

// ── Snap world coord to stride-aligned grid ───────────────────────────────────

function _snapToGrid(wx, wy) {
  const snap = 500;
  return [Math.round(wx / snap) * snap, Math.round(wy / snap) * snap];
}

// ── Ghost overlay ─────────────────────────────────────────────────────────────
// Overrides the stub declared in index.html; called from render().

function _drawBuilderOverlay() {
  if (!builderModeActive) return;

  if (placingZone && ghostLocs.length > 0) {
    ctx.save();
    ctx.globalAlpha = 0.5;
    for (const loc of ghostLocs) {
      const [wx, wy, wz] = loc.coords;
      const [dx, dy, dz] = loc.meta.dims;
      if (isIso) {
        drawIsoCube(wx, wy, wz, dx, dy, dz, '#1b3a5c', '#122a45', '#122a45', '#58a6ff');
      } else {
        drawTopBox(wx, wy, dx, dy, '#1b3a5c', '#58a6ff');
      }
    }
    ctx.restore();
  }

  // Delete badge — only when locs are rendered as tiles (LOD guard)
  const tc = _activeTierConfig();
  if (!placingZone && hoveredLocId && locations.has(hoveredLocId) &&
      ['grey', 'grey-slots', 'tiles'].includes(tc.locsDisplay)) {
    const loc = locations.get(hoveredLocId);
    const [sx, sy] = _projectLocCentre(loc);
    ctx.save();
    ctx.beginPath();
    ctx.arc(sx, sy, 11, 0, Math.PI * 2);
    ctx.fillStyle   = '#3d1a1a';
    ctx.strokeStyle = '#f85149';
    ctx.lineWidth   = 1.5;
    ctx.fill();
    ctx.stroke();
    ctx.fillStyle    = '#f85149';
    ctx.font         = 'bold 14px monospace';
    ctx.textAlign    = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText('\xd7', sx, sy);
    ctx.restore();
  }
}

window._drawBuilderOverlay = _drawBuilderOverlay;

// ── Ghost tracking (canvas mousemove in placing mode) ─────────────────────────

canvas.addEventListener('mousemove', e => {
  if (!placingZone || posPinned) return;
  const [wx, wy]             = _screenToWorld(e.clientX, e.clientY);
  const [snappedX, snappedY] = _snapToGrid(wx, wy);
  document.getElementById('bld-pos-x').value = Math.round(snappedX);
  document.getElementById('bld-pos-y').value = Math.round(snappedY);
  if (!ghostOrigin || ghostOrigin[0] !== snappedX || ghostOrigin[1] !== snappedY) {
    ghostOrigin = [snappedX, snappedY];
    ghostLocs   = _computeZoneLocs(snappedX, snappedY, _builderParams());
    forceRender();
  }
});

// ── Place zone (shared logic) ─────────────────────────────────────────────────

async function _placeZone(locs) {
  const payload = {
    locations: locs.map(loc => ({
      id:     loc.id,
      coords: { x: loc.coords[0], y: loc.coords[1], z: loc.coords[2] },
      meta: {
        dims:                   { x: loc.meta.dims[0], y: loc.meta.dims[1], z: loc.meta.dims[2] },
        channel_processor_type: loc.meta.channel_processor,
        capacity:               loc.meta.capacity,
      },
      tree_labels: loc.tree_labels,
    })),
  };
  const res = await fetch(`/v2/layouts/${LAYOUT_ID}/locations`, {
    method:  'PUT',
    headers: { 'Content-Type': 'application/json' },
    body:    JSON.stringify(payload),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || res.statusText);
  }
  await _patchNewLocations();
}

// ── Click to place zone ───────────────────────────────────────────────────────

canvas.addEventListener('click', async e => {
  if (!placingZone || !ghostOrigin) return;

  const locs = ghostLocs.slice();
  // Reset ghost position but stay in ghost/placing mode for next placement
  ghostLocs   = [];
  ghostOrigin = null;
  if (!posPinned) {
    document.getElementById('bld-pos-x').value = '';
    document.getElementById('bld-pos-y').value = '';
  }
  forceRender();

  try {
    await _placeZone(locs);
  } catch (err) {
    alert(`Failed to place zone:\n${err.message}`);
  }
});

// ── "Place here" button ───────────────────────────────────────────────────────

document.getElementById('btn-place-here').addEventListener('click', async () => {
  if (!placingZone || ghostLocs.length === 0) return;
  const locs = ghostLocs.slice();
  try {
    await _placeZone(locs);
  } catch (err) {
    alert(`Failed to place zone:\n${err.message}`);
  }
});

// ── Click to delete (builder mode, not placing) ───────────────────────────────

canvas.addEventListener('click', async e => {
  if (!builderModeActive || placingZone || !hoveredLocId) return;

  // LOD guard: only allow delete when individual locations are visually distinguishable
  const tc = _activeTierConfig();
  if (!['grey', 'grey-slots', 'tiles'].includes(tc.locsDisplay)) return;

  const locId = hoveredLocId;
  const ok = await _showConfirm(
    'Delete location',
    `Delete <strong>${locId}</strong>?<br>Type <strong>confirm</strong> to proceed.`
  );
  if (!ok) return;

  try {
    const res = await fetch(`/v2/layouts/${LAYOUT_ID}/locations/${encodeURIComponent(locId)}`, {
      method: 'DELETE',
    });
    if (!res.ok && res.status !== 204) {
      const err = await res.json().catch(() => ({}));
      alert(`Failed to delete:\n${err.detail || res.statusText}`);
      return;
    }
    locations.delete(locId);
    tileCache.delete(locId);
    hoveredLocId    = null;
    hoveredAisleKey = null;
    _rebuildIndices();
    _markBgDirty();
    _buildZoneList();
    statusEl.textContent = `Layout — ${locations.size} location${locations.size !== 1 ? 's' : ''}`;
    forceRender();
  } catch (err) {
    alert(`Failed to delete: ${err}`);
  }
});

// ── Escape resets ghost (stays in build mode) ─────────────────────────────────

window.addEventListener('keydown', e => {
  if (e.key === 'Escape' && placingZone && builderModeActive) {
    ghostLocs   = [];
    ghostOrigin = null;
    forceRender();
  }
});

// ── Patch new locations into the in-memory Map after a PUT ───────────────────

async function _patchNewLocations() {
  const res = await fetch(`/v2/layouts/${LAYOUT_ID}/locations`);
  if (!res.ok) return;
  const data = await res.json();
  let added = 0;
  for (const [id, loc] of Object.entries(data)) {
    if (!locations.has(id)) {
      locations.set(id, loc);
      _indexLoc(loc);
      added++;
    }
  }
  if (added > 0) {
    _rebuildIndices();
    _markBgDirty();
    statusEl.textContent = `Layout — ${locations.size} location${locations.size !== 1 ? 's' : ''}`;
    forceRender();
  }
  _buildZoneList();
}

// ── Position pin ──────────────────────────────────────────────────────────────

document.getElementById('btn-pin-pos').addEventListener('click', () => {
  posPinned = !posPinned;
  const btn = document.getElementById('btn-pin-pos');
  if (posPinned) {
    btn.classList.add('pinned');
    btn.title = 'Unpin — follow cursor';
    const x = parseFloat(document.getElementById('bld-pos-x').value) || 0;
    const y = parseFloat(document.getElementById('bld-pos-y').value) || 0;
    ghostOrigin = [x, y];
    ghostLocs   = _computeZoneLocs(x, y, _builderParams());
    forceRender();
  } else {
    btn.classList.remove('pinned');
    btn.title = 'Pin position — ghost stays at typed coords';
  }
});

['bld-pos-x', 'bld-pos-y'].forEach(id => {
  document.getElementById(id).addEventListener('input', () => {
    if (!posPinned || !placingZone) return;
    const x = parseFloat(document.getElementById('bld-pos-x').value) || 0;
    const y = parseFloat(document.getElementById('bld-pos-y').value) || 0;
    ghostOrigin = [x, y];
    ghostLocs   = _computeZoneLocs(x, y, _builderParams());
    forceRender();
  });
});

// ── Rotation presets ──────────────────────────────────────────────────────────

document.querySelectorAll('.bld-rot-preset').forEach(btn => {
  btn.addEventListener('click', () => {
    document.getElementById('bld-rotation').value = btn.dataset.deg;
    if (placingZone && ghostOrigin) {
      ghostLocs = _computeZoneLocs(ghostOrigin[0], ghostOrigin[1], _builderParams());
      forceRender();
    }
  });
});

// ── Zone list ─────────────────────────────────────────────────────────────────

function _buildZoneList() {
  const listEl = document.getElementById('zones-list');
  if (!listEl) return;
  const zoneMap = new Map(); // zone name → { ids: [] }
  for (const [id, loc] of locations) {
    const zoneName = (loc.tree_path   && loc.tree_path.zone)   ||
                     (loc.tree_labels && loc.tree_labels.zone) || '?';
    if (!zoneMap.has(zoneName)) zoneMap.set(zoneName, { ids: [] });
    zoneMap.get(zoneName).ids.push(id);
  }
  if (zoneMap.size === 0) {
    listEl.innerHTML = '<div style="color:#484f58;font-size:11px;text-align:center;padding:8px 0">No zones placed</div>';
    return;
  }
  listEl.innerHTML = '';
  for (const [zoneName, info] of zoneMap) {
    const div = document.createElement('div');
    div.className = 'zone-entry';
    div.innerHTML =
      `<span class="zone-entry-name">${_escHtml(zoneName)}</span>` +
      `<span class="zone-entry-count">${info.ids.length}&nbsp;locs</span>` +
      `<button class="btn zone-entry-edit"   data-zone="${_escHtml(zoneName)}" title="Load into form">✎</button>` +
      `<button class="btn zone-entry-delete" data-zone="${_escHtml(zoneName)}" title="Delete all">✕</button>`;
    listEl.appendChild(div);
  }
  listEl.querySelectorAll('.zone-entry-edit').forEach(btn => {
    btn.addEventListener('click', () => _editZone(btn.dataset.zone));
  });
  listEl.querySelectorAll('.zone-entry-delete').forEach(btn => {
    btn.addEventListener('click', () => _deleteZone(btn.dataset.zone));
  });
}

function _editZone(zoneName) {
  for (const [, loc] of locations) {
    const zn = (loc.tree_path   && loc.tree_path.zone)   ||
               (loc.tree_labels && loc.tree_labels.zone);
    if (zn !== zoneName) continue;
    document.getElementById('bld-zone').value = zoneName;
    if (loc.meta) {
      if (loc.meta.dims) {
        document.getElementById('bld-dim-x').value    = loc.meta.dims[0];
        document.getElementById('bld-dim-y').value    = loc.meta.dims[1];
        document.getElementById('bld-dim-z').value    = loc.meta.dims[2];
        document.getElementById('bld-stride-x').value = loc.meta.dims[0];
        document.getElementById('bld-stride-y').value = loc.meta.dims[1];
        document.getElementById('bld-stride-z').value = loc.meta.dims[2];
      }
      if (loc.meta.capacity != null) document.getElementById('bld-capacity').value = loc.meta.capacity;
      if (loc.meta.channel_processor) document.getElementById('bld-processor').value = loc.meta.channel_processor;
    }
    if (!builderModeActive) _setLayoutMode('build');
    break;
  }
}

async function _deleteZone(zoneName) {
  const ids = [];
  for (const [id, loc] of locations) {
    const zn = (loc.tree_path   && loc.tree_path.zone)   ||
               (loc.tree_labels && loc.tree_labels.zone);
    if (zn === zoneName) ids.push(id);
  }
  if (!ids.length) return;

  const ok = await _showConfirm(
    'Delete zone',
    `Delete zone <strong>${_escHtml(zoneName)}</strong> and all <strong>${ids.length}</strong> location(s)?<br>Type <strong>confirm</strong> to proceed.`
  );
  if (!ok) return;

  let anyFailed = false;
  for (const locId of ids) {
    try {
      const res = await fetch(
        `/v2/layouts/${LAYOUT_ID}/locations/${encodeURIComponent(locId)}`,
        { method: 'DELETE' }
      );
      if (res.ok || res.status === 204) {
        locations.delete(locId);
        tileCache.delete(locId);
      } else {
        anyFailed = true;
      }
    } catch {
      anyFailed = true;
    }
  }
  if (hoveredLocId && ids.includes(hoveredLocId)) {
    hoveredLocId    = null;
    hoveredAisleKey = null;
  }
  _rebuildIndices();
  _markBgDirty();
  _buildZoneList();
  statusEl.textContent = `Layout — ${locations.size} location${locations.size !== 1 ? 's' : ''}`;
  forceRender();
  if (anyFailed) alert('Some locations could not be deleted — check the server.');
}
