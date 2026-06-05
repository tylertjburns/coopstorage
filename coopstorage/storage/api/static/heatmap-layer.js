/**
 * HeatmapLayer — generic canvas heatmap overlay for the CoopStorage visualizer.
 *
 * Each instance represents one toggleable layer.  Counts are keyed by location
 * ID.  On enable the layer fetches current counts from the server; incremental
 * SSE updates are applied via `incrCount()`.
 *
 * Usage:
 *   const layer = new HeatmapLayer({
 *     name:     'Location Reservations',
 *     fetchUrl: '/v1/heatmap',
 *     countKey: 'location',   // key in the JSON response object
 *     r: 52, g: 152, b: 219,
 *   });
 *
 *   layer.enabled = true;
 *   await layer.fetchCounts();
 *   layer.draw({ ctx, locations, project, W, H, scale });
 */
class HeatmapLayer {
  /**
   * @param {Object} opts
   * @param {string}  opts.name       Display name shown in the layers panel
   * @param {string}  opts.fetchUrl   Endpoint that returns {[countKey]: {locId: count}}
   * @param {string}  opts.countKey   Key inside the response to use for this layer
   * @param {number}  opts.r          Base color red channel   (0–255)
   * @param {number}  opts.g          Base color green channel (0–255)
   * @param {number}  opts.b          Base color blue channel  (0–255)
   */
  constructor({ name, fetchUrl, countKey, r, g, b }) {
    this.name     = name;
    this.fetchUrl = fetchUrl;
    this.countKey = countKey;
    this.r = r;
    this.g = g;
    this.b = b;
    this.enabled  = false;
    /** @type {Map<string, number>} locId → reservation count */
    this.counts   = new Map();
  }

  /** Sum of all counts across all locations. */
  get totalCount() {
    let t = 0;
    for (const n of this.counts.values()) t += n;
    return t;
  }

  /**
   * Fetch current counts from the server, replacing in-memory state.
   * Accepts optional ISO 8601 UTC datetime strings to constrain the window.
   *
   * @param {Object} [opts]
   * @param {string} [opts.start]  Range start (inclusive)
   * @param {string} [opts.end]    Range end   (inclusive)
   */
  async fetchCounts({ start, end } = {}) {
    try {
      const url = new URL(this.fetchUrl, location.origin);
      if (start) url.searchParams.set('start', start);
      if (end)   url.searchParams.set('end',   end);
      const data = await (await fetch(url)).json();
      this.counts.clear();
      for (const [id, n] of Object.entries(data[this.countKey] || {})) {
        this.counts.set(String(id), n);
      }
    } catch (_) {}
  }

  /**
   * Increment the count for a single location (used for real-time SSE updates).
   * @param {string|number} locId
   */
  incrCount(locId) {
    const key = String(locId);
    this.counts.set(key, (this.counts.get(key) || 0) + 1);
  }

  /** Reset all accumulated counts (e.g., when locations are cleared). */
  clearCounts() {
    this.counts.clear();
  }

  /**
   * Render the heatmap onto the given canvas context.
   *
   * The rendering uses two-pass compositing: intensity blobs are first drawn
   * onto a temporary OffscreenCanvas, then the result is blitted onto `ctx`
   * with a CSS blur filter.  This causes adjacent blobs to bleed together into
   * a continuous cloud shape rather than discrete per-location circles.
   *
   * `ctx` should already be redirected to the background offscreen canvas when
   * this is called (i.e. called from inside _paintBackground).
   *
   * @param {Object}                  opts
   * @param {CanvasRenderingContext2D} opts.ctx        Target 2D context
   * @param {Map}                     opts.locations  Map locId → location object with `.coords`
   * @param {Function}                opts.project    project(wx,wy,wz) → [sx,sy]
   * @param {number}                  opts.W          Canvas width
   * @param {number}                  opts.H          Canvas height
   * @param {number}                  opts.scale      Current viewport scale
   * @returns {boolean} true if anything was drawn
   */
  draw({ ctx, locations, project, W, H, scale }) {
    if (!this.enabled || this.counts.size === 0) return false;

    let maxCount = 0;
    for (const c of this.counts.values()) if (c > maxCount) maxCount = c;
    if (maxCount === 0) return false;

    const { r, g, b } = this;

    // Blob radius is kept large so that nearby locations overlap on the temp
    // canvas; the subsequent blur then merges them into a single cloud shape.
    const baseRadius = Math.max(60, scale * 5);

    const tmp = new OffscreenCanvas(W, H);
    const tc  = tmp.getContext('2d');

    for (const loc of locations.values()) {
      const count = this.counts.get(String(loc.id)) || 0;
      if (count === 0) continue;

      const [sx, sy] = project(...loc.coords);
      // Keep a margin equal to the blob radius so edge blobs still contribute
      // to the blur without being fully clipped before the filter runs.
      if (sx < -baseRadius || sx > W + baseRadius || sy < -baseRadius || sy > H + baseRadius) continue;

      const t      = count / maxCount;
      const radius = baseRadius * (0.5 + t * 0.5);

      const grad = tc.createRadialGradient(sx, sy, 0, sx, sy, radius);
      grad.addColorStop(0,   `rgba(${r},${g},${b},${(t * 0.7).toFixed(3)})`);
      grad.addColorStop(0.5, `rgba(${r},${g},${b},${(t * 0.2).toFixed(3)})`);
      grad.addColorStop(1,   `rgba(${r},${g},${b},0)`);

      tc.beginPath();
      tc.arc(sx, sy, radius, 0, Math.PI * 2);
      tc.fillStyle = grad;
      tc.fill();
    }

    // Blur when compositing: softens blob boundaries so the layer reads as an
    // atmospheric cloud rather than a collection of individual highlights.
    ctx.save();
    ctx.filter      = 'blur(16px)';
    ctx.globalAlpha = 0.88;
    ctx.drawImage(tmp, 0, 0);
    ctx.restore();
    return true;
  }
}
