(function () {
  'use strict';

  // ── Registry ───────────────────────────────────────────────────────────────
  // Resolution order:
  //   1. serverFirst wrapper → try server, fallback to local fn on error
  //   2. Local producer registered → use it, no server call
  //   3. Not registered → try server (if serverUrl configured)

  const TooltipRegistry = {
    _producers: new Map(),
    _serverUrl: null,

    configure({ serverUrl = null } = {}) {
      this._serverUrl = serverUrl;
    },

    register(id, producer) {
      this._producers.set(id, producer);
    },

    serverFirst(localFallback) {
      const fn = typeof localFallback === 'function' ? localFallback : () => localFallback;
      fn._serverFirst = true;
      return fn;
    },

    async resolve(id, ctx = {}) {
      const producer = this._producers.get(id);

      if (producer?._serverFirst && this._serverUrl) {
        const html = await this._fetch(id, ctx);
        if (html !== null) return html;
        return typeof producer === 'function' ? await producer(ctx) : producer;
      }

      if (producer !== undefined) {
        return typeof producer === 'function' ? await producer(ctx) : producer;
      }

      if (this._serverUrl) return await this._fetch(id, ctx);
      return null;
    },

    async _fetch(id, ctx) {
      try {
        const params = new URLSearchParams(
          Object.entries(ctx)
            .filter(([k, v]) => v != null && !k.startsWith('_'))
            .map(([k, v]) => [k, typeof v === 'object' ? JSON.stringify(v) : String(v)])
        );
        const res = await fetch(`${this._serverUrl}/${encodeURIComponent(id)}?${params}`);
        if (!res.ok) return null;
        const ct = res.headers.get('content-type') || '';
        if (ct.includes('application/json')) {
          const data = await res.json();
          return data.html ?? null;
        }
        return await res.text();
      } catch {
        return null;
      }
    }
  };


  // ── Manager ────────────────────────────────────────────────────────────────

  const TooltipManager = {
    _locked: new Set(),
    _rootEl: null,

    getRootEl() {
      if (!this._rootEl) {
        this._rootEl = document.createElement('div');
        this._rootEl.id = 'ts-root';
        document.body.appendChild(this._rootEl);
      }
      return this._rootEl;
    },

    addLocked(tooltip)    { this._locked.add(tooltip); },
    removeLocked(tooltip) { this._locked.delete(tooltip); },

    collapseAll() {
      RootContainer.dismissChild();
      for (const t of [...this._locked]) t.close();
    }
  };

  document.addEventListener('click',   (e) => { if (!e.target.closest('.ts-tooltip')) TooltipManager.collapseAll(); });
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape') TooltipManager.collapseAll(); });


  // ── Tooltip ────────────────────────────────────────────────────────────────
  // Also acts as a TooltipContainer so child tooltips can nest inside it.

  class Tooltip {
    constructor({ id, ctx, anchorRect, parentContainer }) {
      this.id = id;
      this.ctx = ctx;
      this.anchorRect = anchorRect;
      this.parentContainer = parentContainer;
      this.locked = false;
      this._activeChild = null;
      this._childTriggers = [];
      this._el = null;
      this._lockBtn = null;
      this._progressEl = null;
      this._progressFill = null;
      this._dismissTimer = null;
    }

    async mount() {
      const content = await TooltipRegistry.resolve(this.id, this.ctx);

      this._el = document.createElement('div');
      this._el.className = 'ts-tooltip';

      const header = document.createElement('div');
      header.className = 'ts-header';

      const title = document.createElement('span');
      title.className = 'ts-title';
      title.textContent = this.ctx._title ?? this.id;

      const btns = document.createElement('div');
      btns.className = 'ts-header-btns';

      // Progress ring — shown while a child tooltip is being cued
      const progress = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
      progress.setAttribute('viewBox', '0 0 16 16');
      progress.classList.add('ts-progress');
      const track = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
      track.setAttribute('cx', '8'); track.setAttribute('cy', '8'); track.setAttribute('r', '6');
      track.classList.add('ts-progress-track');
      const fill = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
      fill.setAttribute('cx', '8'); fill.setAttribute('cy', '8'); fill.setAttribute('r', '6');
      fill.classList.add('ts-progress-fill');
      progress.append(track, fill);
      this._progressEl   = progress;
      this._progressFill = fill;

      this._lockBtn = document.createElement('button');
      this._lockBtn.className = 'ts-btn ts-lock-btn';
      this._lockBtn.setAttribute('aria-label', 'Lock tooltip');
      this._lockBtn.innerHTML = '🔓';
      this._lockBtn.addEventListener('click', (e) => { e.stopPropagation(); this.toggleLock(); });

      btns.append(this._progressEl, this._lockBtn);
      header.append(title, btns);

      const body = document.createElement('div');
      body.className = 'ts-body';
      if (content === null)                body.innerHTML = '<span class="ts-empty">No content available.</span>';
      else if (typeof content === 'string') body.innerHTML = content;
      else                                 body.appendChild(content);

      this._el.append(header, body);

      // On enter: propagate cancelDismiss up the full ancestor chain so moving
      // mouse from any ancestor tooltip to this one keeps the whole stack alive.
      this._el.addEventListener('mouseenter', () => {
        let c = this.parentContainer;
        while (c) { c.cancelDismiss?.(); c = c.parentContainer; }
        this._clearDismiss();
      });
      // On leave: schedule (don't immediately execute) so mouse transit to a
      // child tooltip can cancel before the timer fires.
      this._el.addEventListener('mouseleave', () => {
        this.scheduleDismiss();
        if (!this.locked) this.parentContainer.scheduleDismiss?.();
      });

      TooltipManager.getRootEl().appendChild(this._el);
      this._position();
      this._attachTextTriggers();
      // Stop any countdown on the parent that was waiting for this child to appear.
      if (typeof this.parentContainer.stopProgress === 'function') this.parentContainer.stopProgress();
    }

    _position() {
      const el = this._el;
      const margin = 8, gap = 6;
      el.style.visibility = 'hidden';
      el.style.left = '0';
      el.style.top = '0';
      const { width, height } = el.getBoundingClientRect();
      const vw = window.innerWidth, vh = window.innerHeight;

      let left = this.anchorRect.right + gap;
      let top  = this.anchorRect.top;

      if (left + width  > vw - margin) left = this.anchorRect.left - width - gap;
      if (top  + height > vh - margin) top  = vh - height - margin;
      left = Math.max(margin, left);
      top  = Math.max(margin, top);

      el.style.left = `${left}px`;
      el.style.top  = `${top}px`;
      el.style.visibility = 'visible';
    }

    _attachTextTriggers() {
      this._el.querySelectorAll('[data-tip]').forEach((link) => {
        link.classList.add('ts-link');
        const t = new TextTrigger(link, this);
        t.attach();
        this._childTriggers.push(t);
      });
    }

    // ── TooltipContainer interface ──

    scheduleDismiss() {
      this._clearDismiss();
      this._dismissTimer = setTimeout(() => this.dismissChild(), 100);
    }

    cancelDismiss() { this._clearDismiss(); }

    startProgress(duration) {
      const fill = this._progressFill;
      if (!fill) return;
      this._progressEl.style.opacity = '1';
      fill.style.transition = 'none';
      fill.style.strokeDashoffset = '37.7';
      void fill.getBoundingClientRect(); // force reflow so transition restarts cleanly
      fill.style.transition = `stroke-dashoffset ${duration}ms linear`;
      fill.style.strokeDashoffset = '0';
    }

    stopProgress() {
      if (!this._progressFill) return;
      this._progressFill.style.transition = 'none';
      this._progressFill.style.strokeDashoffset = '37.7';
      this._progressEl.style.opacity = '0';
    }

    _clearDismiss() {
      if (this._dismissTimer) { clearTimeout(this._dismissTimer); this._dismissTimer = null; }
    }

    requestTooltip(id, ctx, anchorRect) {
      if (this._activeChild?.id === id) return;
      this.dismissChild();
      const child = new Tooltip({ id, ctx, anchorRect, parentContainer: this });
      this._activeChild = child;
      child.mount();
    }

    dismissChild() {
      if (this._activeChild && !this._activeChild.locked) {
        this._activeChild.close();
        this._activeChild = null;
      }
    }

    // ── Lock ──

    toggleLock() { this.locked ? this.unlock() : this.lock(); }

    lock() {
      this.locked = true;
      this._lockBtn.innerHTML = '🔒';
      this._lockBtn.classList.add('locked');
      TooltipManager.addLocked(this);
      if (RootContainer._activeChild === this) RootContainer._activeChild = null;
    }

    unlock() {
      this.locked = false;
      this._lockBtn.innerHTML = '🔓';
      this._lockBtn.classList.remove('locked');
      TooltipManager.removeLocked(this);
    }

    // ── Lifecycle ──

    close() {
      this._clearDismiss();
      this.dismissChild();
      this._childTriggers.forEach(t => t.detach());
      if (this.locked) TooltipManager.removeLocked(this);
      this._el?.remove();
      this._el = null;
      if (this.parentContainer._activeChild === this) this.parentContainer._activeChild = null;
    }
  }


  // ── Triggers ───────────────────────────────────────────────────────────────

  class TooltipTrigger {
    constructor(hoverDelay) {
      this.hoverDelay = hoverDelay;
      this._hoverTimer = null;
    }
    _schedule(fn) { clearTimeout(this._hoverTimer); this._hoverTimer = setTimeout(fn, this.hoverDelay); }
    _cancel()     { clearTimeout(this._hoverTimer); this._hoverTimer = null; }
  }


  class AreaTrigger extends TooltipTrigger {
    constructor(element, tooltipId, ctx = {}, container, hoverDelay = 400) {
      super(hoverDelay);
      this.element    = element;
      this.tooltipId  = tooltipId;
      this.ctx        = ctx;
      this._container = container;  // resolved lazily via getter to allow RootContainer forward-ref
      this._touchMoved = false;
      this._lpTimer    = null;

      this._h = {
        enter:      this._enter.bind(this),
        leave:      this._leave.bind(this),
        touchstart: this._touchstart.bind(this),
        touchend:   () => clearTimeout(this._lpTimer),
        touchmove:  () => { this._touchMoved = true; clearTimeout(this._lpTimer); },
      };
    }

    get container() { return this._container ?? RootContainer; }

    attach() {
      this.element.addEventListener('mouseenter', this._h.enter);
      this.element.addEventListener('mouseleave', this._h.leave);
      this.element.addEventListener('touchstart', this._h.touchstart, { passive: true });
      this.element.addEventListener('touchend',   this._h.touchend);
      this.element.addEventListener('touchmove',  this._h.touchmove, { passive: true });
    }

    detach() {
      this.element.removeEventListener('mouseenter', this._h.enter);
      this.element.removeEventListener('mouseleave', this._h.leave);
      this.element.removeEventListener('touchstart', this._h.touchstart);
      this.element.removeEventListener('touchend',   this._h.touchend);
      this.element.removeEventListener('touchmove',  this._h.touchmove);
    }

    _enter() {
      this.container.cancelDismiss?.();
      this._schedule(() =>
        this.container.requestTooltip(this.tooltipId, this.ctx, this.element.getBoundingClientRect())
      );
    }

    _leave() {
      this._cancel();
      this.container.scheduleDismiss?.();
    }

    _touchstart(e) {
      this._touchMoved = false;
      const { clientX, clientY } = e.touches[0];
      this._lpTimer = setTimeout(() => {
        if (!this._touchMoved)
          this.container.requestTooltip(this.tooltipId, this.ctx, new DOMRect(clientX, clientY, 0, 0));
      }, 600);
    }
  }


  class TextTrigger extends TooltipTrigger {
    constructor(link, parentTooltip) {
      super(600);
      this.link          = link;
      this.parentTooltip = parentTooltip;
      this._touchMoved   = false;
      this._lpTimer      = null;

      this._h = {
        enter:      this._enter.bind(this),
        leave:      this._leave.bind(this),
        touchstart: this._touchstart.bind(this),
        touchend:   () => clearTimeout(this._lpTimer),
        touchmove:  () => { this._touchMoved = true; clearTimeout(this._lpTimer); },
      };
    }

    attach() {
      this.link.addEventListener('mouseenter', this._h.enter);
      this.link.addEventListener('mouseleave', this._h.leave);
      this.link.addEventListener('touchstart', this._h.touchstart, { passive: true });
      this.link.addEventListener('touchend',   this._h.touchend);
      this.link.addEventListener('touchmove',  this._h.touchmove, { passive: true });
    }

    detach() {
      this.link.removeEventListener('mouseenter', this._h.enter);
      this.link.removeEventListener('mouseleave', this._h.leave);
      this.link.removeEventListener('touchstart', this._h.touchstart);
      this.link.removeEventListener('touchend',   this._h.touchend);
      this.link.removeEventListener('touchmove',  this._h.touchmove);
    }

    _ctx() {
      try { return JSON.parse(this.link.dataset.tipCtx || '{}'); } catch { return {}; }
    }

    _enter() {
      this.parentTooltip.cancelDismiss();
      this.parentTooltip.parentContainer.cancelDismiss?.();
      this.parentTooltip.startProgress(this.hoverDelay);
      this._schedule(() =>
        this.parentTooltip.requestTooltip(this.link.dataset.tip, this._ctx(), this.link.getBoundingClientRect())
      );
    }

    _leave() {
      this._cancel();
      this.parentTooltip.stopProgress();
      this.parentTooltip.scheduleDismiss();
    }

    _touchstart(e) {
      this._touchMoved = false;
      const { clientX, clientY } = e.touches[0];
      this._lpTimer = setTimeout(() => {
        if (!this._touchMoved)
          this.parentTooltip.requestTooltip(this.link.dataset.tip, this._ctx(), new DOMRect(clientX, clientY, 0, 0));
      }, 600);
    }
  }


  // ── Root Container ─────────────────────────────────────────────────────────
  // Top-level TooltipContainer. AreaTriggers on the page or canvas use this.

  const RootContainer = {
    _activeChild:  null,
    _dismissTimer: null,

    requestTooltip(id, ctx, anchorRect) {
      if (this._activeChild && !this._activeChild.locked) {
        const sameEntity = this._activeChild.id === id &&
          this._activeChild.ctx?._entityId === ctx?._entityId;
        if (sameEntity) { this.cancelDismiss(); return; }
        this._activeChild.close();
      }
      const t = new Tooltip({ id, ctx, anchorRect, parentContainer: this });
      this._activeChild = t;
      t.mount();
    },

    dismissChild() {
      this._clearDismiss();
      if (this._activeChild && !this._activeChild.locked) {
        this._activeChild.close();
        this._activeChild = null;
      }
    },

    scheduleDismiss() {
      this._clearDismiss();
      this._dismissTimer = setTimeout(() => this.dismissChild(), 100);
    },

    cancelDismiss() { this._clearDismiss(); },
    _clearDismiss() { if (this._dismissTimer) { clearTimeout(this._dismissTimer); this._dismissTimer = null; } }
  };


  // ── Canvas Adapter ─────────────────────────────────────────────────────────
  // Bridges an existing canvas hit-test function to the tooltip system.
  // hitTest(clientX, clientY) => { id: string, ctx: object } | null

  class CanvasTooltipAdapter {
    constructor(canvas, hitTest, hoverDelay = 400) {
      this.canvas     = canvas;
      this.hitTest    = hitTest;
      this.hoverDelay = hoverDelay;
      this._hoverTimer = null;
      this._lpTimer    = null;
      this._lastKey    = null;
      this._touchMoved = false;

      this._h = {
        mousemove:  this._mousemove.bind(this),
        mouseleave: this._mouseleave.bind(this),
        touchstart: this._touchstart.bind(this),
        touchend:   () => clearTimeout(this._lpTimer),
        touchmove:  () => { this._touchMoved = true; clearTimeout(this._lpTimer); },
      };
    }

    attach() {
      this.canvas.addEventListener('mousemove',  this._h.mousemove);
      this.canvas.addEventListener('mouseleave', this._h.mouseleave);
      this.canvas.addEventListener('touchstart', this._h.touchstart, { passive: true });
      this.canvas.addEventListener('touchend',   this._h.touchend);
      this.canvas.addEventListener('touchmove',  this._h.touchmove, { passive: true });
    }

    detach() {
      this.canvas.removeEventListener('mousemove',  this._h.mousemove);
      this.canvas.removeEventListener('mouseleave', this._h.mouseleave);
      this.canvas.removeEventListener('touchstart', this._h.touchstart);
      this.canvas.removeEventListener('touchend',   this._h.touchend);
      this.canvas.removeEventListener('touchmove',  this._h.touchmove);
    }

    _mousemove(e) {
      const hit = this.hitTest(e.clientX, e.clientY);
      const key = hit ? `${hit.id}::${hit.ctx?._entityId ?? ''}` : null;
      if (key === this._lastKey) return;
      this._lastKey = key;
      clearTimeout(this._hoverTimer);

      if (!hit) { RootContainer.scheduleDismiss(); return; }
      // Only prevent dismiss immediately if the mouse is back over the same entity.
      // For a different entity let the current tooltip dismiss naturally; requestTooltip replaces it.
      const activeEntityId = RootContainer._activeChild?.ctx?._entityId;
      if (activeEntityId && hit.ctx?._entityId === activeEntityId) RootContainer.cancelDismiss();
      this._hoverTimer = setTimeout(() => {
        RootContainer.requestTooltip(hit.id, hit.ctx, new DOMRect(e.clientX, e.clientY, 0, 0));
      }, this.hoverDelay);
    }

    _mouseleave() {
      clearTimeout(this._hoverTimer);
      this._lastKey = null;
      RootContainer.scheduleDismiss();
    }

    _touchstart(e) {
      this._touchMoved = false;
      const { clientX, clientY } = e.touches[0];
      this._lpTimer = setTimeout(() => {
        if (!this._touchMoved) {
          const hit = this.hitTest(clientX, clientY);
          if (hit) RootContainer.requestTooltip(hit.id, hit.ctx, new DOMRect(clientX, clientY, 0, 0));
        }
      }, 600);
    }
  }


  // ── Exports ────────────────────────────────────────────────────────────────

  window.TooltipRegistry      = TooltipRegistry;
  window.TooltipManager       = TooltipManager;
  window.AreaTrigger          = AreaTrigger;
  window.TextTrigger          = TextTrigger;
  window.CanvasTooltipAdapter = CanvasTooltipAdapter;

})();
