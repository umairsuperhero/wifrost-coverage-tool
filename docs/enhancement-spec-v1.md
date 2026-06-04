# WiFrost FWA Enhancement Spec — v1.0

**Project:** WiFrost TVWS Coverage Tool  
**Date:** 2026-06-01  
**Scope:** 4 focused UI/UX and functional improvements for Fixed Wireless Access (FWA) use cases  
**Constraints:** Zero new backend HTTP calls. All features reuse single simulation-run data. Free-tier safe (Vercel + Google Cloud Run).

---

## Stack Reference

| Layer | Tech |
|-------|------|
| Frontend | Next.js 15, React 19, Tailwind CSS 4, Leaflet (react-leaflet) |
| Backend | FastAPI, Python 3.11 (Google Cloud Run — scales to zero, sub-second cold start, ephemeral in-memory filesystem) |
| Deployment | Vercel (frontend), Google Cloud Run (backend API at `https://wifrost-api-508425876629.northamerica-south1.run.app`) |

### Key files

```
frontend/
  app/page.tsx                  — root page, all state lives here
  components/Sidebar.tsx        — all simulation params + Run button
  components/CpeTable.tsx       — per-CPE results table
  components/MapInner.tsx       — Leaflet map, BTS/CPE markers
  components/TerrainChart.tsx   — terrain profile chart
  components/MetricsRow.tsx     — summary stat cards
  components/ResultsBanner.tsx  — post-run banner
  components/LinkBudget.tsx     — NEW: link budget panel
  components/CpeSummaryBar.tsx  — NEW: CPE pass/fail summary bar
```

### CpeResult shape (from `/api/cpe-analysis` — DO NOT add fields)

```typescript
export interface CpeResult {
  name: string;
  distance_km: number;
  elevation_m: number;
  rssi_dbm: number;
  margin_db: number;
  status: string;           // "🟢 Pass (Excellent)" | "🟡 Pass (Marginal)" | "🔴 Fail (No Signal)"
  latitude: number;
  longitude: number;
  best_sector?: number;     // 0-indexed
  best_sector_gain_db?: number;
}
```

### EIRP (already computed in Sidebar.tsx line ~169)

```typescript
const eirpDbm = Number(txPowerDbm) + Number(antennaGainDbi) - Number(cableLossDb);
```

### BW → sensitivity lookup (Sidebar.tsx)

```typescript
const BW_SENSITIVITY: Record<number, number> = { 6: -95, 12: -92, 18: -90, 24: -89 };
```

---

## Feature 1 — Simple / Advanced Mode Toggle

**Goal:** Reduce cognitive load for first-time users. Hide advanced RF parameters behind a toggle; keep only the essentials visible by default.

### Behaviour

- Default state: **Simple mode** (advanced fields hidden)
- Toggle button: top of Sidebar, below the BTS site selector. Label: `"Advanced ▾"` / `"Advanced ▴"` — small, right-aligned, blue text
- Persists in `localStorage` key `wifrost_advanced_mode` so it survives page reload

### Fields hidden in Simple mode

Group 1 — **BTS Equipment Config** `<details>` accordion (lines ~190–270 of Sidebar.tsx):
- Antenna Gain (dBi)
- Cable Loss (dB)
- Sector Count, Sector Azimuths, HPBW, VPBW, F/B Ratio

Group 2 — **CPE Client Config** `<details>` accordion (lines ~280–360 of Sidebar.tsx):
- CPE Antenna Gain (dBi)
- CPE Cable Loss (dB)

Group 3 — **Model / Environment** (lines ~370–430):
- Propagation Model selector
- Environment selector
- Coverage Probability slider

### Fields always visible (Simple + Advanced)

- Frequency (MHz)
- BTS Height (m)
- TX Power (dBm)
- CPE Sensitivity (dBm) — shown as "Receiver Sensitivity"
- System Margin (dB)
- Run Simulation button

### Implementation notes

- Add `const [advancedMode, setAdvancedMode] = useState(() => localStorage.getItem('wifrost_advanced_mode') === 'true');` to Sidebar
- Wrap hidden groups with `{advancedMode && ( ... )}` — do NOT remove the JSX, just conditionally render
- In Simple mode, display a one-line read-only summary below the always-visible fields:
  ```
  Model: ITU-R P.1546 · Urban · Gain 17 dBi · Margin 10 dB
  ```
  Format: `Model: {modelType} · {environment} · Gain {antennaGainDbi} dBi · Margin {systemMarginDb} dB`
- Button style: `className="text-xs text-blue-400 hover:text-blue-300 font-medium"`

---

## Feature 2 — Link Budget Panel

**Goal:** Show a live, transparent breakdown of the RF link budget so engineers can audit every dB.

### New component: `frontend/components/LinkBudget.tsx`

**Props:**

```typescript
interface LinkBudgetProps {
  txPowerDbm: number;
  antennaGainDbi: number;
  cableLossDb: number;
  cpeGainDbi: number;
  cpeCableLossDb: number;
  cpeSensitivityDbm: number;  // from BW_SENSITIVITY or manual entry
  systemMarginDb: number;
  frequencyMhz: number;
  maxRangeKm: number | null;   // from simulationResults.stats.max_range_km (null before first run)
}
```

**Layout — vertical table, dark card style:**

```
┌─────────────────────────────────────────────┐
│  ⚡ Link Budget                              │
├─────────────────────────────────────────────┤
│  TX Power          +23.0 dBm                │
│  BTS Antenna Gain  +17.0 dBi                │
│  Cable Loss         −2.0 dB                 │
│  ─────────────────────────────              │
│  EIRP              +38.0 dBm  ← bold, blue │
│                                             │
│  Rx Sensitivity    −92.0 dBm               │
│  Rx Antenna Gain   +5.0 dBi                │
│  Rx Cable Loss      −1.0 dB                │
│  System Margin     −10.0 dB                │
│  ─────────────────────────────              │
│  Max Allowed PL    142.0 dB   ← bold       │
│                                             │
│  Max Range (sim)   18.3 km    ← from stats │
└─────────────────────────────────────────────┘
```

**Computed values:**

```typescript
const eirpDbm = txPowerDbm + antennaGainDbi - cableLossDb;
const maxAllowedPathLoss = eirpDbm - cpeSensitivityDbm + cpeGainDbi - cpeCableLossDb - systemMarginDb;
```

**Styling:**
- Container: `bg-slate-900/60 rounded-xl border border-slate-800 p-5`
- Row: `flex justify-between text-sm py-1`
- Label: `text-slate-400`
- Value: `text-slate-100 tabular-nums`
- Divider rows: `border-t border-slate-700 my-1`
- EIRP row: `text-blue-400 font-bold`
- Max Allowed PL row: `text-white font-bold`
- Max Range row: `text-emerald-400 font-semibold` (or `text-slate-500` with "—" when null)

### Wiring in page.tsx

Pass `simulationResults?.stats?.max_range_km ?? null` as `maxRangeKm`.
Pass all other values from `activeSimulationParams` (which is set from Sidebar on run).

Add `SidebarProps.simStats?: { max_range_km: number } | null` to Sidebar if needed to bubble up — but since `activeSimulationParams` already lives in page.tsx state, pass directly to `<LinkBudget />` from page.tsx.

### Placement in page.tsx

Render `<LinkBudget />` in the right-hand column, **above** `<TerrainChart />`, below `<MetricsRow />`.

---

## Feature 3 — CPE Hero Layout + Colored Map Markers

This is two sub-features. Implement in order: 3A (markers) then 3B (layout).

### Feature 3A — Colored CPE Markers on Map

**File:** `frontend/components/MapInner.tsx`

Replace the current single CPE `CircleMarker` colour with a dynamic colour based on `margin_db`:

```typescript
const getCpeColor = (margin_db: number): string => {
  if (margin_db >= 10) return "#22C55E";  // emerald-500 — good
  if (margin_db >= 0)  return "#F59E0B";  // amber-500  — marginal
  return "#EF4444";                        // red-500    — fail
};
```

Apply to `fillColor` and `color` (stroke) of each CPE `CircleMarker`.

The selected CPE should have `radius={9}` and `weight={2}`; unselected CPEs `radius={6}` and `weight={1}`.

**MapInner props to check:** It currently receives `cpeResults: CpeResult[]`. Verify this before editing.

### Feature 3B — CPE Summary Bar + Table Reorder

#### New component: `frontend/components/CpeSummaryBar.tsx`

**Props:**

```typescript
interface CpeSummaryBarProps {
  cpeResults: CpeResult[];
}
```

**Layout:**

```
┌──────────────────────────────────────────────────────────────┐
│  CPE Coverage   ●24 Excellent  ●8 Marginal  ●3 No Signal    │
│                 ████████████████████░░░░░░░──  77% Excellent │
└──────────────────────────────────────────────────────────────┘
```

**Logic:**

```typescript
const excellent = cpeResults.filter(c => c.margin_db >= 10).length;
const marginal  = cpeResults.filter(c => c.margin_db >= 0 && c.margin_db < 10).length;
const failed    = cpeResults.filter(c => c.margin_db < 0).length;
const total     = cpeResults.length;
const pct       = total > 0 ? Math.round((excellent / total) * 100) : 0;
```

**Progress bar:** Three segments in a single `div` row — widths proportional to count.

```tsx
<div className="flex rounded-full overflow-hidden h-2 mt-2">
  <div className="bg-emerald-500" style={{ width: `${(excellent/total)*100}%` }} />
  <div className="bg-amber-500"   style={{ width: `${(marginal/total)*100}%`  }} />
  <div className="bg-red-500"     style={{ width: `${(failed/total)*100}%`    }} />
</div>
```

**Styling:**
- Container: `bg-slate-900/60 rounded-xl border border-slate-800 px-5 py-3`
- Title: `text-sm font-semibold text-white`
- Dots: `w-2 h-2 rounded-full inline-block mr-1`
- Count labels: `text-xs text-slate-300`

#### Layout reorder in page.tsx right-hand column (top to bottom):

1. `<MetricsRow />`
2. `<CpeSummaryBar cpeResults={cpeResults} />` ← new, appears only when `cpeResults.length > 0`
3. `<CpeTable />` ← was below TerrainChart, move above
4. `<TerrainChart />` ← stays but pushed down
5. `<LinkBudget />` ← new (Feature 2)

> **Note:** `<CpeSummaryBar />` and `<CpeTable />` should only render when `cpeResults.length > 0`.

---

## Feature 4 — Cold-Start Loading UX

**Goal:** The backend scales to zero when idle, so the first request after a quiet period incurs a cold start. Users currently see a spinner with no explanation. Show a friendly, informative message. (Originally written for the Render free tier's 30–50 s cold start; the tool now runs on Cloud Run with a sub-second cold start, but the graceful-wait UX is retained as a safety net for slow networks and the OpenTopography fetch.)

### State to add in page.tsx

```typescript
const [slowStart, setSlowStart] = useState(false);
```

### Timer logic in `handleSimulate` (in page.tsx)

```typescript
const handleSimulate = async () => {
  setIsLoading(true);
  setSlowStart(false);

  // After 8 seconds, if still loading, show the slow-start message
  const slowTimer = setTimeout(() => setSlowStart(true), 8000);

  try {
    // ... existing fetch calls ...
  } finally {
    clearTimeout(slowTimer);
    setIsLoading(false);
    setSlowStart(false);
  }
};
```

### UI — overlay or inline message

When `isLoading && slowStart`, show this **below the spinner** (not instead of it):

```tsx
{isLoading && slowStart && (
  <div className="flex flex-col items-center gap-2 mt-4 text-center">
    <p className="text-sm text-amber-400 font-medium">⏳ Waking up the backend…</p>
    <p className="text-xs text-slate-400 max-w-xs">
      The server sleeps after inactivity. First run takes 30–50 s on the free tier. Hang tight!
    </p>
  </div>
)}
```

**Placement:** Wherever the current loading spinner is rendered in page.tsx. Look for `isLoading` in the JSX.

---

## Implementation Order

Build and commit features in this sequence to avoid conflicts in shared files:

| Step | Feature | Primary files touched |
|------|---------|----------------------|
| 1 | Cold-start UX | `page.tsx` only (low risk) |
| 2 | Link Budget panel | New `LinkBudget.tsx` + minor `page.tsx` wiring |
| 3 | CPE markers | `MapInner.tsx` only |
| 4 | CPE Summary Bar + layout | New `CpeSummaryBar.tsx` + `page.tsx` reorder |
| 5 | Simple/Advanced toggle | `Sidebar.tsx` only |

**Commit after each step.** Do not batch steps. Each commit should be independently deployable.

---

## Testing Checklist (per feature)

**Feature 1 (toggle):**
- [ ] Simple mode hides BTS Equipment Config, CPE Client Config, Model/Env sections
- [ ] Advanced mode shows all fields
- [ ] Summary line renders with real values in Simple mode
- [ ] Toggle state persists across page refresh (localStorage)
- [ ] Simulation still runs correctly in both modes (no missing params)

**Feature 2 (link budget):**
- [ ] All rows render with correct values before first run
- [ ] Max Range shows "—" before first run, populates after
- [ ] EIRP and Max Allowed PL rows bold/colored correctly
- [ ] Values update live when Sidebar inputs change (reactive to props)

**Feature 3A (map markers):**
- [ ] Green markers for margin_db ≥ 10
- [ ] Amber markers for 0 ≤ margin_db < 10
- [ ] Red markers for margin_db < 0
- [ ] Selected CPE is larger radius
- [ ] Clicking a marker still triggers CPE selection

**Feature 3B (summary bar + layout):**
- [ ] Bar and table hidden when no CPE results
- [ ] Three-color progress bar proportions correct
- [ ] Count labels match actual data
- [ ] TerrainChart still renders below table
- [ ] No layout breaks on mobile (< 640px)

**Feature 4 (cold-start UX):**
- [ ] Message does NOT appear if response < 8 s
- [ ] Message appears and amber text shows after 8 s of waiting
- [ ] Message clears immediately when response arrives
- [ ] Spinner still shows alongside message (not replaced)

---

## Out of Scope (do not implement)

- Any new backend endpoints or changes to `api.py`
- Adding `has_los` field to CpeResult (requires backend change)
- Downloadable PDF from new components (existing Generate Report covers this)
- Authentication / user accounts
- Paying-tier infrastructure (Redis, persistent DB beyond SQLite, CDN)
- Mobile-native app
- Real-time websocket streaming
