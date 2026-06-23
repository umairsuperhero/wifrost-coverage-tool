# UI/UX Refactoring Task

- [x] Refactor `frontend/components/Sidebar.tsx`: Changed container to use `glass-panel`. Used `cn` to clean up classes. Redesigned form inputs and segmented controls to look like premium frosted glass widgets.
- [x] Refactor Right HUD components: Converted `ResultsBanner`, `MetricsRow`, `CpeSummaryBar`, `CpeTable`, `TerrainChart`, `LinkBudget`, and `RunSummaryBar` into sleek, compact glass cards using the `glass-panel` class. Applied `font-mono` to numbers and data. Removed excessive padding to ensure compactness.
- [x] Refactor `frontend/app/page.tsx`:
  - Created a top ornament navbar with the WiFrost Logo and theme toggle.
  - Ensured the Right Results HUD maintains a strict Tabbed Interface (`Overview`, `Clients`, `Path Link`).
  - Map View is full screen and maintains its width and height properly.
