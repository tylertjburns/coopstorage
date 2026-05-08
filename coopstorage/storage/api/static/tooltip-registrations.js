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
      <span style="color:#8b949e;white-space:nowrap">${used} / ${total} ${def('slot', 'slots')}</span>
    </div>`;
  }

  function def(term, display) {
    return `<a data-tip="glossary" data-tip-ctx='${JSON.stringify({ term, _title: term })}'>${display ?? term}</a>`;
  }

  function instanceLink(type, id, display) {
    return `<a data-tip="${type}" data-tip-ctx='${JSON.stringify({ id, _title: display ?? id })}'>${display ?? id}</a>`;
  }


  // ── Glossary ──────────────────────────────────────────────────────────────

  const GLOSSARY = {
    location:
      `A named storage position with world coordinates, a ${def('channel')} governing ${def('slot')} access, and a fixed slot count.`,
    container:
      `A unit load occupying one ${def('slot')} in a ${def('location')}. Holds zero or more items of a single ${def('uom', 'unit of measure')}.`,
    channel:
      `The ordered sequence of ${def('slot', 'slots')} within a ${def('location')}. A ${def('processor')} determines which slot is accessible at any time.`,
    slot:
      `A single position within a ${def('channel')}. Holds at most one ${def('container')}.`,
    content:
      `An item line inside a ${def('container')}: resource name, quantity, and ${def('uom', 'unit of measure')}.`,
    uom:
      `Unit of Measure — the unit in which a ${def('container')} tracks its ${def('content', 'contents')} (e.g. EA, CASE, PALLET). Location and container UoMs must be compatible.`,
    processor:
      `The algorithm governing ${def('slot')} access in a ${def('channel')}. Variants: ${def('fifo', 'FIFO')}, ${def('lifo', 'LIFO')}, ${def('omni', 'OMNI')}, optionally combined with ${def('flow')} and/or ${def('push')}.`,
    zone:
      `A named spatial region grouping ${def('location', 'locations')}. Top level of the ${def('tree-path', 'location hierarchy')}.`,
    'tree-path':
      `Hierarchical address of a ${def('location')}: Zone › Aisle › Row › Bay › Shelf.`,
    fifo:
      `First-In First-Out — the earliest-placed ${def('container')} in the ${def('channel')} is retrieved first.`,
    lifo:
      `Last-In First-Out — the most recently placed ${def('container')} is retrieved first.`,
    omni:
      `Unrestricted access — any ${def('slot')} in the ${def('channel')} is reachable at any time.`,
    flow:
      `When enabled, the ${def('channel')} is directional: ${def('container', 'containers')} enter one end and exit the other. Prevents arbitrary insertion/removal.`,
    push:
      `When enabled, adding a ${def('container')} shifts existing ones along the ${def('channel')} to make room, rather than requiring a pre-empty ${def('slot')}.`,
  };

  TooltipRegistry.register('glossary', (ctx) => {
    const html = GLOSSARY[ctx.term];
    return html ?? `<span class="ts-empty">No definition for "${ctx.term}"</span>`;
  });


  // ── Channel processor definitions ─────────────────────────────────────────

  const PROCESSOR_DEFS = {
    FIFOChannelProcessor:         { label: 'FIFO',           accessTerm: 'fifo', access: 'First-in first-out', flow: false, push: false },
    LIFOChannelProcessor:         { label: 'LIFO',           accessTerm: 'lifo', access: 'Last-in first-out',  flow: false, push: false },
    OMNIChannelProcessor:         { label: 'OMNI',           accessTerm: 'omni', access: 'Unrestricted',        flow: false, push: false },
    FIFOFlowChannelProcessor:     { label: 'FIFO Flow',      accessTerm: 'fifo', access: 'First-in first-out', flow: true,  push: false },
    LIFOFlowChannelProcessor:     { label: 'LIFO Flow',      accessTerm: 'lifo', access: 'Last-in first-out',  flow: true,  push: false },
    OMNIFlowChannelProcessor:     { label: 'OMNI Flow',      accessTerm: 'omni', access: 'Unrestricted',        flow: true,  push: false },
    FIFOPushChannelProcessor:     { label: 'FIFO Push',      accessTerm: 'fifo', access: 'First-in first-out', flow: false, push: true  },
    LIFOPushChannelProcessor:     { label: 'LIFO Push',      accessTerm: 'lifo', access: 'Last-in first-out',  flow: false, push: true  },
    OMNIPushChannelProcessor:     { label: 'OMNI Push',      accessTerm: 'omni', access: 'Unrestricted',        flow: false, push: true  },
    FIFOFlowPushChannelProcessor: { label: 'FIFO Flow Push', accessTerm: 'fifo', access: 'First-in first-out', flow: true,  push: true  },
    LIFOFlowPushChannelProcessor: { label: 'LIFO Flow Push', accessTerm: 'lifo', access: 'Last-in first-out',  flow: true,  push: true  },
    OMNIFlowPushChannelProcessor: { label: 'OMNI Flow Push', accessTerm: 'omni', access: 'Unrestricted',        flow: true,  push: true  },
  };

  TooltipRegistry.register('channel-processor', (ctx) => {
    const d = PROCESSOR_DEFS[ctx.type];
    if (!d) return `<span class="ts-empty">Unknown processor: ${ctx.type}</span>`;
    return kv([
      ['Label',              badge(d.label, 'blue')],
      [def('fifo', 'Access'), def(d.accessTerm, d.access)],
      [def('flow', 'Flow'),   d.flow ? badge('Enforced', 'green')  : badge('None', '')],
      [def('push', 'Push'),   d.push ? badge('Enabled',  'yellow') : badge('Disabled', '')],
    ]);
  });


  // ── Zone origin ───────────────────────────────────────────────────────────

  TooltipRegistry.register('zone-origin', (ctx) => {
    const h = ctx._zoneHit;
    if (!h) return null;
    return kv([
      [def('zone', 'Zone'), h.key],
      ['Origin',            `${h.wx.toFixed(3)}, ${h.wy.toFixed(3)}, ${h.wz.toFixed(3)}`],
    ]);
  });


  // ── Location ──────────────────────────────────────────────────────────────

  TooltipRegistry.register('location', (ctx) => {
    const loc = ctx._loc ?? window.TooltipDataStore?.locations.get(ctx.id);
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
    const containersHtml = containerEntries.length === 0 ? '' : section(def('container', 'Containers'), `
      <table>
        <thead><tr><th>ID</th><th>${def('uom', 'UoM')}</th><th>${def('content', 'Contents')}</th></tr></thead>
        <tbody>${containerEntries.map(c => {
          const contents = (c.contents ?? []).map(x => `${x.qty}× ${x.resource}`).join(', ') || '—';
          return `<tr>
            <td style="font-family:monospace;font-size:11px">${instanceLink('container', c.id, c.id.slice(-8))}</td>
            <td>${badge(c.uom, 'blue')}</td>
            <td style="color:#8b949e">${contents}</td>
          </tr>`;
        }).join('')}</tbody>
      </table>
    `);

    return `
      ${crumb ? `<div style="font-size:11px;color:#8b949e;margin-bottom:8px">${def('tree-path', crumb)}</div>` : ''}
      ${kv([
        ['ID',                        `<span style="font-family:monospace">${loc.id}</span>`],
        ['Coords',                    (loc.coords ?? []).map(v => v.toFixed(1)).join(', ')],
        [def('processor', 'Processor'), procLink],
        ['Axis',                      meta.channel_axis ?? '—'],
      ])}
      ${section(def('slot', 'Capacity'), capacityBar(used, slots.length))}
      ${containersHtml}
    `;
  });


  // ── Container ─────────────────────────────────────────────────────────────

  TooltipRegistry.register('container', (ctx) => {
    const c = ctx._container ?? window.TooltipDataStore?.containers.get(ctx.id);
    if (!c) return null;
    const contents = c.contents ?? [];
    const rows = contents.length
      ? `<table>
           <thead><tr><th>Resource</th><th>Qty</th><th>${def('uom', 'UoM')}</th></tr></thead>
           <tbody>${contents.map(x => `<tr>
             <td>${x.resource}</td>
             <td style="text-align:right;padding-right:12px">${x.qty}</td>
             <td>${badge(x.uom, 'blue')}</td>
           </tr>`).join('')}</tbody>
         </table>`
      : '<span class="ts-empty">Empty</span>';

    return `
      ${kv([['ID', `<span style="font-family:monospace">${c.id}</span>`], [def('uom', 'UoM'), badge(c.uom, 'blue')]])}
      ${section(def('content', 'Contents'), rows)}
    `;
  });

})();
