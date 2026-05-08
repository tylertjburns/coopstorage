// App-specific tooltip content producers for coopstorage.
// Reads from `locations` and `containers` Maps maintained by the main app.
// All ctx._* fields are internal and are stripped before any server calls.

(function () {

  // ── HTML helpers ──────────────────────────────────────────────────────────

  function kv(pairs) {
    return `<div class="ts-kv">${
      pairs.filter(([, v]) => v != null && v !== '')
           .map(([k, v]) => `<span class="ts-kv-key">${k}</span><span class="ts-kv-val">${v}</span>`)
           .join('')
    }</div>`;
  }

  function section(title, content) {
    return `<div class="ts-section"><div class="ts-section-title">${title}</div>${content}</div>`;
  }

  function badge(text, color = '') {
    return `<span class="ts-badge ${color}">${text}</span>`;
  }

  function capacityBar(used, total) {
    const pct = total > 0 ? Math.round((used / total) * 100) : 0;
    const col  = pct >= 90 ? '#f85149' : pct >= 60 ? '#e3b341' : '#3fb950';
    return `<div style="display:flex;align-items:center;gap:8px;font-size:12px;">
      <div style="flex:1;height:6px;background:#21262d;border-radius:3px;overflow:hidden;">
        <div style="width:${pct}%;height:100%;background:${col};"></div>
      </div>
      <span style="color:#8b949e;white-space:nowrap">${used} / ${total}</span>
    </div>`;
  }


  // ── Channel processor definitions ─────────────────────────────────────────

  const PROCESSOR_DEFS = {
    FIFOChannelProcessor:         { label: 'FIFO',           access: 'First-in first-out', flow: false, push: false },
    LIFOChannelProcessor:         { label: 'LIFO',           access: 'Last-in first-out',  flow: false, push: false },
    OMNIChannelProcessor:         { label: 'OMNI',           access: 'Unrestricted',        flow: false, push: false },
    FIFOFlowChannelProcessor:     { label: 'FIFO Flow',      access: 'First-in first-out', flow: true,  push: false },
    LIFOFlowChannelProcessor:     { label: 'LIFO Flow',      access: 'Last-in first-out',  flow: true,  push: false },
    OMNIFlowChannelProcessor:     { label: 'OMNI Flow',      access: 'Unrestricted',        flow: true,  push: false },
    FIFOPushChannelProcessor:     { label: 'FIFO Push',      access: 'First-in first-out', flow: false, push: true  },
    LIFOPushChannelProcessor:     { label: 'LIFO Push',      access: 'Last-in first-out',  flow: false, push: true  },
    OMNIPushChannelProcessor:     { label: 'OMNI Push',      access: 'Unrestricted',        flow: false, push: true  },
    FIFOFlowPushChannelProcessor: { label: 'FIFO Flow Push', access: 'First-in first-out', flow: true,  push: true  },
    LIFOFlowPushChannelProcessor: { label: 'LIFO Flow Push', access: 'Last-in first-out',  flow: true,  push: true  },
    OMNIFlowPushChannelProcessor: { label: 'OMNI Flow Push', access: 'Unrestricted',        flow: true,  push: true  },
  };

  TooltipRegistry.register('channel-processor', (ctx) => {
    const def = PROCESSOR_DEFS[ctx.type];
    if (!def) return `<span class="ts-empty">Unknown processor: ${ctx.type}</span>`;
    return kv([
      ['Label',  badge(def.label, 'blue')],
      ['Access', def.access],
      ['Flow',   def.flow ? badge('Enforced', 'green')  : badge('None', '')],
      ['Push',   def.push ? badge('Enabled',  'yellow') : badge('Disabled', '')],
    ]);
  });


  // ── Zone origin ───────────────────────────────────────────────────────────

  TooltipRegistry.register('zone-origin', (ctx) => {
    const h = ctx._zoneHit;
    if (!h) return null;
    return kv([
      ['Zone',   h.key],
      ['Origin', `${h.wx.toFixed(3)}, ${h.wy.toFixed(3)}, ${h.wz.toFixed(3)}`],
    ]);
  });


  // ── Location ──────────────────────────────────────────────────────────────

  TooltipRegistry.register('location', (ctx) => {
    const loc = ctx._loc;
    if (!loc) return null;

    const meta  = loc.meta ?? {};
    const slots = loc.slots ?? [];
    const used  = slots.filter(s => s !== null).length;
    const tree  = loc.tree_path ?? {};
    const crumb = [tree.zone, tree.aisle, tree.row, tree.bay, tree.shelf].filter(Boolean).join(' › ');

    const procType = meta.channel_processor ?? '';
    const procLink = procType
      ? `<a data-tip="channel-processor" data-tip-ctx='${JSON.stringify({ type: procType, _title: procType })}'>${procType}</a>`
      : '—';

    const containerEntries = Object.values(loc.containers ?? {});
    const containersHtml = containerEntries.length === 0 ? '' : section('Containers', `
      <table>
        <thead><tr><th>ID</th><th>UoM</th><th>Contents</th></tr></thead>
        <tbody>${containerEntries.map(c => {
          const contents = (c.contents ?? []).map(x => `${x.qty}× ${x.resource}`).join(', ') || '—';
          return `<tr>
            <td style="font-family:monospace;font-size:11px">${c.id.slice(-8)}</td>
            <td>${badge(c.uom, 'blue')}</td>
            <td style="color:#8b949e">${contents}</td>
          </tr>`;
        }).join('')}</tbody>
      </table>
    `);

    return `
      ${crumb ? `<div style="font-size:11px;color:#8b949e;margin-bottom:8px">${crumb}</div>` : ''}
      ${kv([
        ['ID',        `<span style="font-family:monospace">${loc.id}</span>`],
        ['Coords',    (loc.coords ?? []).map(v => v.toFixed(1)).join(', ')],
        ['Processor', procLink],
        ['Axis',      meta.channel_axis ?? '—'],
      ])}
      ${section('Capacity', capacityBar(used, slots.length))}
      ${containersHtml}
    `;
  });


  // ── Container ─────────────────────────────────────────────────────────────

  TooltipRegistry.register('container', (ctx) => {
    const c = ctx._container;
    if (!c) return null;
    const contents = c.contents ?? [];
    const rows = contents.length
      ? `<table>
           <thead><tr><th>Resource</th><th>Qty</th><th>UoM</th></tr></thead>
           <tbody>${contents.map(x => `<tr>
             <td>${x.resource}</td>
             <td style="text-align:right;padding-right:12px">${x.qty}</td>
             <td>${badge(x.uom, 'blue')}</td>
           </tr>`).join('')}</tbody>
         </table>`
      : '<span class="ts-empty">Empty</span>';

    return `
      ${kv([['ID', `<span style="font-family:monospace">${c.id}</span>`], ['UoM', badge(c.uom, 'blue')]])}
      ${section('Contents', rows)}
    `;
  });

})();
