# WiFrost TVWS RF Coverage Simulation Tool — Release Notes

## [2026-06-08] - Enhancements & 3D Propagation
- **Physics Engine**: Implemented 3D mechanical downtilt (MDT) pattern for precise vertical antenna modeling and coverage umbrellas.
- **UI & UX**: Hid the RF Deployment Profile dropdown in Advanced mode to ensure accurate simulation defaults. Refactored "RF Presets" to "Deployment Profiles" to avoid overriding auto-environment logic.
- **Honesty Harness**: Added `CLAUDE.md` and automated hooks to enforce strict verification protocols for all AI code generation, improving codebase integrity.
- **Reporting**: Added a comprehensive Propagation Methodology page to the PDF report exports.
- **Bug Fixes**: Handled edge cases in physics engine related to grid boundaries, Deygout diffraction logic, and flat clutter.

## [2026-06-06] - Terrain-Aware Modeling & P2MP
- **Propagation**: Added bandwidth-aware sensitivity calculations and auto-environment detection utilizing ESA WorldCover land cover data.
- **Features**: Introduced manual CPE placement for Point-to-Multipoint (P2MP) analysis directly on the map.
- **Infrastructure**: Pinned Cloud Run memory to 2 GiB to resolve OOM errors during heavy terrain simulations. Fixed land-cover fetch CA certificates in slim containers. 

## [2026-06-05] - Full Layout Polish & Realism
- **UI Overhaul**: Added a new run-summary bar at the bottom, improved scenario cards to give honest ("best, realistic, conservative") estimations, and polished the overall layout.
- **Physics Engine**: Added Earth-curvature (radio horizon) adjustments and unified the link-budget threshold math between the coverage heatmap and individual CPE pins.

## [2026-06-01] - Cloud Run Migration & V2 Frontend
- **Architecture**: Officially migrated backend APIs from Render to Google Cloud Run, updating all frontend endpoints.
- **Features**: Added Simple vs. Advanced mode toggles, Link Budget panels, and CPE summary bars.
- **Reporting**: Added usage counter API and cold-start loading UX (handling 503 errors during scale-to-zero wakeups).

## [2026-05-30] - Sector Antennas & Terrain Heatmaps
- **Features**: Introduced sector wedge map overlays, PDF terrain profiles, and vectorised heatmaps.
- **Infrastructure**: Finalised production-ready Dockerfiles for Render + Vercel deployment.

## [2026-05-26] - v1 Release
- **Initial Build**: Full UI overhaul with map-first layout. Implemented Okumura-Hata and terrain-aware diffraction models. Added sectorized antennas, CPE analysis, and history.
