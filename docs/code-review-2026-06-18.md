# WiFrost Coverage Tool — Architecture & Physics Code Review
**Date:** 2026-06-18 · **Reviewer:** Claude (Opus 4.8) · **Scope:** full-stack (FastAPI + Next.js), physics engine focus

> Deliverable per request: findings only, no fixes applied. Severity tiers: **🔴 Critical**, **🟠 Warning**, **🔵 Optimization**.

---

## 0. Headline finding (read this first)

**🔴 The committed `HEAD` does not import. The backend cannot boot from this code.**

Commit `64384ce` ("replace Okumura-Hata with deterministic Longley-Rice ITM") deleted `okumura_hata()` from `propagation.py`, but four callers still import/call it:

- `heatmap.py:9` — `from propagation import (terrain_aware_loss, okumura_hata, ...)`
- `api.py:20` — same import
- `api.py:622` — `loss_db = okumura_hata(...)` in the `flat` model branch of `/api/cpe-analysis`
- `app.py:24` and `test_propagation_model.py:9` — same import

Verified directly:
```
$ python -c "import api"     → ImportError: cannot import name 'okumura_hata' from 'propagation'
$ python -c "import heatmap"  → ImportError: cannot import name 'okumura_hata' from 'propagation'
```

**Implications:**
1. The Render backend that responded "healthy" last session is serving a **stale build** from before `64384ce`. The new code (Longley-Rice + ESA WorldCover clutter + auto-environment + MDT) has **never successfully deployed** — every deploy since `64384ce` would have crash-looped on import, and Render keeps the last good container alive.
2. Therefore the **Longley-Rice model the product claims to run is not actually live.** The deployed engine is still the old Okumura-Hata build. This is the direct answer to "ensure the Longley-Rice calculations… are being picked up correctly": right now they are not picked up at all.
3. The cold-start retry fix shipped last session is treating a symptom; the real reason a fresh deploy can fail is the import error, not (only) free-tier sleep.

**This must be fixed before any physics tuning is meaningful** — you cannot validate a model that the server can't load.

---

## 1. Propagation Physics Engine

### 🔴 1.1 The heatmap and the per-CPE dots use *two different propagation models*
The code repeatedly asserts they are unified ("identical physics", "agree by construction", "a green heatmap cell can never host a red CPE dot" — `heatmap.py:73-78`). That claim is **false** in the current code:

- **Heatmap grid** (`compute_coverage_grid`, `heatmap.py:312-368`): Okumura-Hata base loss (`69.55 + 26.16·log10(f) − 13.82·log10(hb)…`) **plus** a custom recursive Deygout knife-edge diffraction (`deygout_loss_np`).
- **Per-CPE link budget** (`/api/cpe-analysis` → `terrain_aware_loss`, `propagation.py:295-306`): **ITM Longley-Rice** via `itmlogic` (`qlrps`/`qlrpfl`/`avar`).

So the map is painted with Hata+Deygout while the dots are computed with Longley-Rice. These can and will disagree (different distance laws, different diffraction treatment, different clutter handling). The "they agree" comments are aspirational, not enforced. **Pick one model and use it everywhere**, or explicitly document the two-model design and stop claiming consistency.

### 🟠 1.2 `okumura_hata` deleted but its replacement was never wired into the grid
The grid still hand-rolls Okumura-Hata inline (`heatmap.py:314-322`) rather than calling the new ITM path. The "replace Okumura-Hata with Longley-Rice" change only touched the per-CPE path (`terrain_aware_loss`); the heatmap was left on Hata. The refactor is half-done.

### 🟠 1.3 ITM failures silently degrade to free-space loss (over-optimistic)
`terrain_aware_loss` (`propagation.py:301-306`) and `itm_longley_rice` (`propagation.py:169-173`) both fall back to plain FSPL on `ImportError`/any exception. A terrain or matrix-math failure therefore produces an *optimistic* coverage estimate with no surfaced warning. For a planning tool this is the dangerous failure direction. At minimum, count/log fallbacks and flag them in the API response.

### 🟠 1.4 Auto-clutter / environment selection — correctness notes
The "auto" path is wired (`api.py:328-331`, `569-572` → `landcover.recommend_environment`) and per-pixel WorldCover clutter is applied in the grid (`heatmap.py:330-334`) and at CPE locations (`api.py:608-620`). Good. But:
- **Double-penalty risk on built-up:** WorldCover class 50 maps to **both** `urban` environment (`landcover.py:53`) **and** +8 dB clutter (`landcover.py:32`). Okumura-Hata "urban" is already the un-corrected base case, so urban cells get the full Hata loss *plus* 8 dB clutter. The code comment acknowledges reducing 18→8 to compensate, but this is a hand-tuned fudge, not a derived value — document the calibration basis or it will drift.
- **Nearest-neighbour clutter sampling** (`landcover.py:100-105`) with `.astype(int)` truncation toward zero can bias the row/col by one cell at the south/east edge; minor but real on small bboxes.

### 🟠 1.5 MDT (downtilt) vertical angle ignores terrain in the live CPE path
`api.py:635`: `pt_elevation = atan2(cpe_height − bts_height, dist_m)` uses **raw antenna heights**, not above-sea-level positions. The heatmap (`heatmap.py:166`, `get_sector_gain_for_point_np`) correctly uses `ground + height` ASL. So the vertical sector pattern (and thus sector gain) is computed on different geometry for the map vs. the dots — another source of map/dot disagreement, and it makes downtilt wrong wherever BTS and CPE ground elevations differ.

### 🔵 1.6 Bearing / divide-by-zero edge cases — mostly handled, one gap
- `bearing()` and `sector_gain()` guard `dist_m > 0` (`propagation.py:108`, `120`) and the vectorized version uses a `safe_dist` mask (`heatmap.py:165-166`) — good.
- `deygout_loss_np` guards `denom > 0` (`heatmap.py:196-197`) — good.
- Gap: `sector_gain` divides by `hpbw`/`vpbw` (`propagation.py:93,96`). If a caller passes `hpbw=0` or `vpbw=0` (e.g. a malformed request), this is a divide-by-zero / NaN that propagates into RSSI. No validation on `hpbw_deg`/`vpbw_deg` in the Pydantic models. Add `gt=0` constraints.

### 🔵 1.7 `meshgrid`/NaN propagation — clean
`get_elevation_np` (`terrain.py:233-243`) scrubs `nodata` and NaN with `np.where` before interpolation, and out-of-bounds cells are zeroed. No NaN leak found in the grid path.

### 🔴 1.8 Performance: the grid diffraction loop is the real bottleneck
`heatmap.py:356-367` is a **pure-Python double loop** over every grid cell (`for r in range(nrows): for c in range(ncols):`) calling the recursive `deygout_loss_np` per cell. For a 100×100 grid that's 10,000 Python-level recursive calls, each doing small NumPy ops on 100-point arrays — this dominates runtime and is exactly why simulate is slow (compounding the cold-start problem). The elevation *extraction* is vectorized (`heatmap.py:346-351`) but the diffraction math is not.
- **Optimization path:** vectorize the dominant-edge Deygout across all cells at once (the v-parameter and argmax over the 100-sample axis can be done with `np.max`/`np.argmax` on the `(nrows, ncols, 100)` array; the recursion depth is capped at 3 so it can be unrolled), or drop to `numba`/Cython for this kernel, or reduce profile samples from 100 to ~40 for the grid. Easily a 10–50× speedup on the hot path.

### 🔵 1.9 `get_profile` uses scalar interpolation in a Python loop
`terrain.py:248-260` builds the 100-point profile with scalar `get_elevation` in a loop, though `get_elevation_np` exists. Only matters per-CPE (few calls), so low priority — but trivially vectorizable.

---

## 2. Architecture & Best Practices

### 🟠 2.1 FastAPI concurrency on a 0.1-CPU / 512 MB free tier
All routes are sync `def` (`api.py:131,167,262,544,…`), so FastAPI runs them in the anyio threadpool — they won't block the event loop, which is correct. **But** the heavy work is CPU-bound NumPy + Python loops holding the GIL; two concurrent `/api/simulate` calls will serialize and can blow the 512 MB limit (the `(nrows,ncols,100)` elevation array + WorldCover up to 512×512 + SRTM 1201×1201 all coexist). On free tier, **single-flight the simulate endpoint** (a lock or a small queue) and/or cap grid size, rather than letting concurrent requests OOM the box.

### 🟠 2.2 In-memory state is fragile and not concurrency-safe
- `_simulation_cache` (`api.py:59-60`, max 20) is a plain dict. The check-then-evict (`api.py:433-435`) is a race under the threadpool, and the cache is **lost on every Render restart/cold start**.
- `/api/generate-report` depends on the grid being in that cache. After 20 sims or any restart, report generation for an older run silently breaks. Persist the grid (or recompute deterministically from params) instead of relying on volatile memory.

### 🔵 2.3 Frontend state management is at the edge of what `useState` should carry
`page.tsx` holds **~30 `useState` hooks** (`page.tsx:128-175`) including the large `SimulationResults`, `cpeResults`, `terrainProfile`, plus a dozen UI toggles. This is past the point where a `useReducer` (for the simulation domain state) or a small store (Zustand/Context) pays for itself — particularly because several handlers re-run the full simulation. Recommend extracting a `simulation` reducer + a `ui` slice.

### 🔵 2.4 React re-render / closure issues
- **Stale closure:** `handleSimulate` reads `prevCoverage` inside `setRunCount` (`page.tsx:316-317`) but `prevCoverage` is **not** in its `useCallback` deps (`page.tsx:387`) — the delta arrow can compare against a stale value. Use a functional ref or include it in deps.
- **Heavy implicit re-runs:** `handleSelectBtsMap` (`page.tsx:389-398`) triggers a full `handleSimulate` on every BTS marker selection — a click on the map kicks off a multi-second backend round-trip. Consider debouncing or making BTS-switch reuse cached grids.
- **Memo defeated:** in `MapInner`, `btsCandidates` is recomputed every render (`MapInner.tsx:149`) and is a dependency of the `sectorGeoJSON` `useMemo` (`MapInner.tsx:161`), so the memo recomputes every render. `getMapStyle()` (`MapInner.tsx:116`) returns a fresh style object each render for satellite mode, which can churn the map. Wrap `btsCandidates` in `useMemo` and hoist the static style objects.

### 🔵 2.5 Dead / divergent code
`heatmap.compute_cpe_analysis` (`heatmap.py:473-610`) is **not called** by the API (the live `/api/cpe-analysis` reimplements the loop inline in `api.py:587-678`). The dead copy also contains a **clutter double-count** in its pessimistic branch (`heatmap.py:545`: `pl_result.total_db + clutter + …`, where `total_db` already includes clutter via `PathLossResult.total_db`). It's dead today, but it's a trap waiting to be re-wired. Delete it or make it the single source of truth.

### 🔵 2.6 Duplicate constants in `propagation.py`
`HB_EFF_MIN_M` / `HB_EFF_MAX_M` are defined twice (`propagation.py:34-35` and `39-40`). Harmless but signals incomplete cleanup.

---

## 3. UI/UX & Component Library

### 🔵 3.1 Accessibility gaps (glassmorphic "VisionOS" UI)
- Icon-only toolbar buttons in `MapInner.tsx:371-391` use `title` but no `aria-label`; screen readers will read nothing useful. The theme `<select>` (`MapInner.tsx:395`) has no associated label.
- Heavy reliance on `text-[10px]`/`text-[9px]` (`MapInner.tsx`, `Sidebar.tsx`) plus `text-muted-foreground` over translucent glass risks failing WCAG AA contrast — worth a contrast audit on the actual rendered backgrounds.
- Color is the sole carrier of meaning in the signal legend and CPE dots (green/amber/red). Add a shape/label channel for color-blind users (the status strings exist server-side — surface them in the marker too).

### 🔵 3.2 Responsive bounds
The legend and panels use hard-coded absolute offsets keyed to sidebar state (`MapInner.tsx:407-409`: `left-[430px]` / `left-[120px]`; auto-fit padding `left: 400` at `MapInner.tsx:112`). At ≤1024 px these overlap the map content and the 400 px fit-padding can exceed half the viewport, pushing markers off-screen. There are no breakpoints handling <768 px. Recommend a `lg:` breakpoint that collapses the sidebar to an overlay and switches absolute offsets to responsive values.

---

## 4. PDF Generation & Mapping

### 🟠 4.1 `fetch_basemap_image` is not robust across latitudes / zooms (`heatmap.py:687-730`)
- **Hard-coded `zoom = 13`** regardless of bbox size. A small site over-zooms (blurry, few tiles); a regional bbox at zoom 13 spans hundreds of tiles → hundreds of synchronous `requests.get` calls (`heatmap.py:696-705`), each with a 5 s timeout — the report can hang for minutes or hit rate limits. Zoom should be derived from the bbox extent and target pixel size.
- **Web-Mercator pole failure:** `asinh(tan(radians(lat)))` (`heatmap.py:684,715`) diverges as |lat|→90°; high-latitude reports will produce wrong crops or exceptions. Clamp to Mercator's ±85.05° and guard.
- **No crop clamping:** `crop_left/top/right/bottom` (`heatmap.py:724-729`) are used unclamped; floating-point edges can yield negative or out-of-image coords and a degenerate crop.
- **Mislabeled provider:** annotation says "CartoDB Basemap" (`heatmap.py:788`) but the source is ArcGIS (`heatmap.py:698`) — leftover from the CartoDB→ArcGIS switch (commit `7d31764`).
- **Longitude hemisphere label bug:** `lon_e` formatting (`heatmap.py:779`) labels east bound by its own sign, but a bbox straddling the antimeridian or with mixed signs will mislabel. Minor.

### 🔵 4.2 PDF layout resilience — mostly OK, two notes
- **Long CPE names: handled.** Names render through `Paragraph` (`report.py:515`), which wraps — good.
- **Per-row `ParagraphStyle` churn:** a uniquely-named style is created per CPE row (`report.py:515-524`, `_s(f'RN{i}', …)`). Hundreds of CPEs → hundreds of style objects and a growing stylesheet; works but wasteful. Reuse a fixed set of styles.
- **Missing terrain profile:** confirm the report degrades gracefully when `terrain_profile`/`coverage_grid` is absent — `coverage_to_image` (`report.py:346-355`) is called unconditionally and itself triggers the network basemap fetch (4.1). If the cached grid was evicted (§2.2), this path can raise inside report generation.

---

## Severity summary

| # | Finding | Severity |
|---|---------|----------|
| 0 | Committed HEAD fails to import (`okumura_hata` removed, 4 callers remain) → backend can't boot, deployed build is stale, Longley-Rice not actually live | 🔴 Critical |
| 1.1 | Heatmap (Hata+Deygout) and CPE dots (Longley-Rice) use different models despite "identical physics" claims | 🔴 Critical |
| 1.8 | Per-cell Python diffraction loop is the runtime bottleneck (10k recursive calls) | 🔴 Critical |
| 1.2 | Grid never wired to the new ITM path (refactor half-done) | 🟠 Warning |
| 1.3 | ITM/terrain failures silently fall back to optimistic FSPL | 🟠 Warning |
| 1.4 | Built-up double-penalty (urban env + clutter); hand-tuned, undocumented | 🟠 Warning |
| 1.5 | CPE MDT vertical angle ignores terrain ASL (map/dot mismatch) | 🟠 Warning |
| 2.1 | Sync CPU-bound routes can OOM/serialize on 0.1-CPU/512 MB free tier | 🟠 Warning |
| 2.2 | Volatile, non-thread-safe in-memory cache; report depends on it | 🟠 Warning |
| 4.1 | `fetch_basemap_image`: fixed zoom, pole failure, tile blowup, unclamped crop | 🟠 Warning |
| 1.6 | `hpbw`/`vpbw` = 0 → divide-by-zero into RSSI (no validation) | 🔵 Opt |
| 2.3–2.6 | 30× useState, stale closure, defeated memos, dead code, dup constants | 🔵 Opt |
| 3.1–3.2 | a11y (aria-labels, contrast, color-only meaning), <1024 px overlap | 🔵 Opt |
| 4.2 | Per-row PDF style churn; verify missing-grid report path | 🔵 Opt |

---

## Proposed action plan (ordered)

**Phase 0 — Make it boot & deploy (blocks everything).**
1. Resolve the `okumura_hata` import in `heatmap.py`, `api.py`, `app.py`, `test_propagation_model.py`. Decision required (see questions below): re-add a thin `okumura_hata()` shim, or rip the Hata grid path out entirely in favor of ITM.
2. Add a CI smoke test: `python -c "import api, heatmap, app"` + one `/api/simulate` call on a tiny fixture. This single test would have caught finding #0. Wire it as a Render pre-deploy / GitHub Action gate.
3. Redeploy and confirm via `/api/defaults` build hash that the *new* code is actually live.

**Phase 1 — Make the physics consistent and correct.**
4. Choose the canonical model. Recommendation: **ITM Longley-Rice everywhere** (it's the deterministic model the product advertises). Replace the Hata+Deygout grid kernel with a vectorized ITM/diffraction pass, sharing one code path with the per-CPE budget.
5. Fix the CPE MDT geometry to use ASL (§1.5), so sector gain matches the grid.
6. Make ITM fallbacks loud: count fallbacks, return a `model_degraded` flag in the API, surface in UI/PDF.
7. Document the clutter calibration (§1.4) or replace the magic 8 dB with a derived value; add a regression test asserting urban ≥ suburban ≥ open ordering at a reference link.

**Phase 2 — Performance & robustness.**
8. Vectorize the grid diffraction kernel (§1.8) — target <2 s for a 100×100 grid; this also blunts the cold-start pain.
9. Single-flight / size-cap the simulate endpoint for the free tier (§2.1); persist or recompute report inputs instead of the volatile cache (§2.2).
10. Harden `fetch_basemap_image`: derive zoom from extent, clamp to ±85.05°, clamp crop, cap tile count, fix the provider label (§4.1).

**Phase 3 — Frontend & a11y polish.**
11. Extract a `useReducer`/store for simulation state; fix the `prevCoverage` stale closure and memoize `btsCandidates`/map style (§2.3–2.4).
12. a11y pass: aria-labels, contrast audit, non-color status channel; add `<1024 px` responsive handling (§3).

---

## Decisions needed from you
1. **One model or two?** Standardize on ITM Longley-Rice for both map and dots (recommended), or keep Hata for the fast grid and document the divergence honestly?
2. **Free tier or paid?** Several robustness items (concurrency, cold start, persistent cache) largely dissolve on Render Starter. `render.yaml` already specifies `plan: starter` — is the intent to move off free tier?
3. Scope of this pass: do you want me to execute **Phase 0** now (un-break the build) as a focused fix, and leave Phases 1–3 as planned follow-ups?
