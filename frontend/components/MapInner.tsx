"use client";

import React, { useEffect } from "react";
import { MapContainer, TileLayer, Marker, Popup, GeoJSON, Polygon, Polyline, CircleMarker, Tooltip, useMap, useMapEvents } from "react-leaflet";
import L from "leaflet";
import { MousePointer, Ruler } from "lucide-react";

// Custom Leaflet CSS DivIcons to enable modern styling
const getBtsIcon = (isActive: boolean) => {
  return L.divIcon({
    html: `<div class="relative flex items-center justify-center">
      ${isActive ? '<span class="absolute w-10 h-10 rounded-full bg-amber-500/30 animate-ping"></span>' : ""}
      <div class="w-6 h-6 rounded-full ${
        isActive ? "bg-amber-500 border-2 border-white" : "bg-slate-700 border border-slate-500"
      } flex items-center justify-center shadow-xl">
        <div class="w-2.5 h-2.5 rounded-full bg-slate-950"></div>
      </div>
    </div>`,
    className: "custom-bts-icon",
    iconSize: [40, 40],
    iconAnchor: [20, 20],
    popupAnchor: [0, -10],
  });
};

const getCpeColor = (margin_db: number): string => {
  if (margin_db >= 10) return "#22C55E"; // emerald-500 — good
  if (margin_db >= 0)  return "#F59E0B"; // amber-500  — marginal
  return "#EF4444";                       // red-500    — fail
};

const getCpeIcon = (status: string, isSelected: boolean) => {
  let color = "#EF4444"; // red (fail)
  if (status.includes("Excellent") || status.includes("🟢")) color = "#10B981"; // emerald
  else if (status.includes("Marginal") || status.includes("🟡") || status.includes("Pass")) color = "#F59E0B"; // amber

  return L.divIcon({
    html: `<div class="relative flex items-center justify-center">
      ${isSelected ? '<span class="absolute w-8 h-8 rounded-full bg-blue-500/40 animate-ping"></span>' : ""}
      <div class="w-4 h-4 rounded-full border border-white flex items-center justify-center shadow-lg transition-transform duration-300 ${
        isSelected ? "scale-125 border-2" : ""
      }" style="background-color: ${color};">
      </div>
    </div>`,
    className: "custom-cpe-icon",
    iconSize: [32, 32],
    iconAnchor: [16, 16],
    popupAnchor: [0, -10],
  });
};

const getStartPinIcon = () => L.divIcon({
  html: `<div class="relative flex items-center justify-center">
    <div class="w-3.5 h-3.5 rounded-full bg-blue-500 border-2 border-white shadow-md animate-bounce"></div>
  </div>`,
  className: "start-pin-icon",
  iconSize: [14, 14],
  iconAnchor: [7, 7]
});

const getEndPinIcon = () => L.divIcon({
  html: `<div class="relative flex items-center justify-center">
    <div class="w-3.5 h-3.5 rounded-full bg-emerald-500 border-2 border-white shadow-md animate-bounce"></div>
  </div>`,
  className: "end-pin-icon",
  iconSize: [14, 14],
  iconAnchor: [7, 7]
});

// Map controller to dynamically update center and fit bounds when data changes
function MapController({ sites, polygons, lines }: { sites: any[]; polygons: any[]; lines: any[] }) {
  const map = useMap();

  useEffect(() => {
    if (sites.length === 0) return;

    // Collect all coordinates to calculate bounds
    const coords: [number, number][] = [];
    sites.forEach((s) => coords.push([s.latitude, s.longitude]));
    
    polygons.forEach((p) => {
      p.coordinates.forEach((c: any) => coords.push([c[1], c[0]]));
    });

    lines.forEach((l) => {
      l.coordinates.forEach((c: any) => coords.push([c[1], c[0]]));
    });

    if (coords.length > 0) {
      const bounds = L.latLngBounds(coords);
      map.fitBounds(bounds, { padding: [50, 50], maxZoom: 15 });
    }
  }, [sites, polygons, lines, map]);

  return null;
}

const SECTOR_COLORS = ["#3B82F6", "#22C55E", "#F59E0B"];

interface SectorInfo {
  azimuths: number[];
  hpbw: number;
  radiusKm: number;
}

interface MapInnerProps {
  sites: any[];
  polygons: any[];
  lines: any[];
  coverageGeojson: any;
  cpeResults: any[];
  selectedBtsIndex: number;
  onSelectBts: (index: number) => void;
  selectedCpeName: string | null;
  onSelectCpe: (cpe: any) => void;
  sectorInfo?: SectorInfo | null;
  activeScenario?: "best" | "realistic" | "conservative";
  activeThreshold?: number;
  onMoveBts?: (index: number, lat: number, lng: number) => void;
  mapMode?: "normal" | "measure";
  setMapMode?: (mode: "normal" | "measure") => void;
  hoverPoint?: [number, number] | null;
  opacity?: number;
  setOpacity?: (opacity: number) => void;
  mapTheme?: "dark" | "satellite" | "street";
  setMapTheme?: (theme: "dark" | "satellite" | "street") => void;
  measurePoints?: [number, number][];
  setMeasurePoints?: (points: [number, number][]) => void;
}

function sectorPolygon(
  btsLat: number,
  btsLon: number,
  azimuth: number,
  hpbw: number,
  radiusKm: number
): [number, number][] {
  const points: [number, number][] = [[btsLat, btsLon]];
  const startAngle = azimuth - hpbw / 2;
  const endAngle = azimuth + hpbw / 2;
  const numPts = 30;
  const btsLatRad = (btsLat * Math.PI) / 180;

  for (let i = 0; i <= numPts; i++) {
    const angle = startAngle + (i / numPts) * (endAngle - startAngle);
    const angleRad = (angle * Math.PI) / 180;
    const dLat = (radiusKm / 111.32) * Math.cos(angleRad);
    const dLon = (radiusKm / (111.32 * Math.cos(btsLatRad))) * Math.sin(angleRad);
    points.push([btsLat + dLat, btsLon + dLon]);
  }
  points.push([btsLat, btsLon]);
  return points;
}

export default function MapInner({
  sites,
  polygons,
  lines,
  coverageGeojson,
  cpeResults,
  selectedBtsIndex,
  onSelectBts,
  selectedCpeName,
  onSelectCpe,
  sectorInfo,
  activeScenario = "realistic",
  activeThreshold = -89.0,
  onMoveBts,
  mapMode = "normal",
  setMapMode,
  hoverPoint,
  opacity = 0.45,
  setOpacity,
  mapTheme = "dark",
  setMapTheme,
  measurePoints = [],
  setMeasurePoints,
}: MapInnerProps) {
  // Default center Buonaventura Colombia (SPRBUN)
  const defaultCenter: [number, number] = [3.89, -77.08];

  const getTileUrl = () => {
    if (mapTheme === "satellite") {
      return "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}";
    }
    if (mapTheme === "street") {
      return "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png";
    }
    return "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png";
  };

  const getTileAttribution = () => {
    if (mapTheme === "satellite") {
      return "Tiles &copy; Esri &mdash; Source: Esri, i-cubed, USDA, USGS, AEX, GeoEye, Getmapping, Aerogrid, IGN, IGP, UPR-EGP, and the GIS User Community";
    }
    if (mapTheme === "street") {
      return '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors';
    }
    return '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>';
  };

  const geojsonStyle = (feature: any) => {
    return {
      fillColor: feature.properties.fill,
      fillOpacity: opacity,
      stroke: false,
      weight: 0,
    };
  };

  const btsCandidates = sites.filter((s) => s.is_bts_candidate);

  const haversineKm = (a: [number, number], b: [number, number]) => {
    const R = 6371;
    const dLat = ((b[0] - a[0]) * Math.PI) / 180;
    const dLon = ((b[1] - a[1]) * Math.PI) / 180;
    const lat1 = (a[0] * Math.PI) / 180;
    const lat2 = (b[0] * Math.PI) / 180;
    const x = Math.sin(dLat / 2) ** 2 + Math.cos(lat1) * Math.cos(lat2) * Math.sin(dLon / 2) ** 2;
    return R * 2 * Math.asin(Math.sqrt(x));
  };

  // Map clicks helper component
  function MapEventsHelper() {
    useMapEvents({
      click(e) {
        if (mapMode === "measure" && setMeasurePoints) {
          const newPoints = [...measurePoints, [e.latlng.lat, e.latlng.lng] as [number, number]];
          if (newPoints.length > 2) {
            setMeasurePoints([[e.latlng.lat, e.latlng.lng]]);
          } else {
            setMeasurePoints(newPoints);
          }
        }
      }
    });
    return null;
  }

  return (
    <div className={`w-full h-full relative ${mapMode !== "normal" ? "cursor-crosshair" : ""}`}>
      <MapContainer center={defaultCenter} zoom={13} className="w-full h-full">
        {/* Switchable map tiles */}
        <TileLayer
          key={mapTheme}
          url={getTileUrl()}
          attribution={getTileAttribution()}
        />

        {/* Map events click handler */}
        <MapEventsHelper />

        {/* Map Controller */}
        <MapController sites={sites} polygons={polygons} lines={lines} />

        {/* KML Polygons (Blue boundary outline) */}
        {polygons.map((poly, idx) => (
          <Polygon
            key={`poly-${idx}`}
            positions={poly.coordinates.map((c: any) => [c[1], c[0]])}
            pathOptions={{ color: "#3B82F6", fillOpacity: 0.05, weight: 2 }}
          >
            <Popup>
              <div className="text-xs">
                <span className="font-semibold block">{poly.name || "KML Polygon"}</span>
                {poly.description && <span className="text-slate-400 mt-1 block">{poly.description}</span>}
              </div>
            </Popup>
          </Polygon>
        ))}

        {/* KML Lines (Dashed blue lines) */}
        {lines.map((line, idx) => (
          <Polyline
            key={`line-${idx}`}
            positions={line.coordinates.map((c: any) => [c[1], c[0]])}
            pathOptions={{ color: "#3B82F6", weight: 2, dashArray: "5,5" }}
          >
            <Popup>
              <div className="text-xs">
                <span className="font-semibold block">{line.name || "KML Line"}</span>
              </div>
            </Popup>
          </Polyline>
        ))}

        {/* Heatmap GeoJSON Layer */}
        {coverageGeojson && (
          <GeoJSON
            key={`${activeScenario}-${activeThreshold}-${opacity}-${JSON.stringify(coverageGeojson.features?.[0]?.properties || {})}`}
            data={coverageGeojson}
            style={geojsonStyle}
            filter={(feature) => {
              if (feature && feature.properties && typeof feature.properties.rssi === "number") {
                return feature.properties.rssi >= activeThreshold;
              }
              return true;
            }}
          />
        )}

        {/* Sector wedge overlays — shown after simulation only */}
        {selectedBtsIndex !== -1 && sectorInfo && btsCandidates[selectedBtsIndex] &&
          sectorInfo.azimuths.map((az, i) => {
            const bts = btsCandidates[selectedBtsIndex];
            const pts = sectorPolygon(bts.latitude, bts.longitude, az, sectorInfo.hpbw, sectorInfo.radiusKm);
            const color = SECTOR_COLORS[i % SECTOR_COLORS.length];
            return (
              <Polygon
                key={`sector-${i}-${az}-${sectorInfo.hpbw}-${sectorInfo.radiusKm}`}
                positions={pts}
                pathOptions={{
                  fillColor: color,
                  fillOpacity: 0.12,
                  color: color,
                  weight: 1,
                  dashArray: "5,5",
                  opacity: 0.5,
                }}
              />
            );
          })
        }

        {/* BTS Site Markers */}
        {btsCandidates.map((site, index) => {
          const isActive = index === selectedBtsIndex;
          const latLng: [number, number] = [site.latitude, site.longitude];

          return (
            <Marker
              key={`bts-${index}`}
              position={latLng}
              icon={getBtsIcon(isActive)}
              draggable={true}
              eventHandlers={{
                dragend: (e) => {
                  const marker = e.target;
                  const position = marker.getLatLng();
                  if (onMoveBts) {
                    onMoveBts(index, position.lat, position.lng);
                  }
                }
              }}
            >
              <Popup>
                <div className="text-xs space-y-2">
                  <div>
                    <span className="font-bold text-sm text-amber-400">BTS: {site.name}</span>
                    <span className="text-slate-400 block mt-0.5">Lat: {site.latitude.toFixed(5)}, Lon: {site.longitude.toFixed(5)}</span>
                  </div>
                  {!isActive && (
                    <button
                      onClick={() => onSelectBts(index)}
                      className="px-2 py-1 bg-amber-500 text-slate-950 font-semibold rounded hover:bg-amber-400 text-[10px] w-full transition cursor-pointer border-none"
                    >
                      Set as Active BTS
                    </button>
                  )}
                </div>
              </Popup>
            </Marker>
          );
        })}

        {/* CPE client Markers */}
        {cpeResults.map((cpe, index) => {
          const isSelected = cpe.name === selectedCpeName;
          const color = getCpeColor(cpe.margin_db);

          return (
            <CircleMarker
              key={`cpe-${index}`}
              center={[cpe.latitude, cpe.longitude]}
              radius={isSelected ? 9 : 6}
              weight={isSelected ? 2 : 1}
              color={color}
              fillColor={color}
              fillOpacity={0.9}
              eventHandlers={{
                click: () => onSelectCpe(cpe),
              }}
            >
              <Popup>
                <div className="text-xs space-y-1">
                  <span className="font-bold text-white block">{cpe.name}</span>
                  {cpe.serving_bts_name && (
                    <span className="text-[10px] text-amber-300 block">Server: {cpe.serving_bts_name}</span>
                  )}
                  <div className="grid grid-cols-2 gap-x-2 text-[10px]">
                    <span className="text-slate-400">Distance:</span>
                    <span className="text-right">{cpe.distance_km.toFixed(2)} km</span>
                    <span className="text-slate-400">RSSI:</span>
                    <span className="text-right font-medium">{cpe.rssi_dbm.toFixed(1)} dBm</span>
                    <span className="text-slate-400">Margin:</span>
                    <span
                      className={`text-right font-bold ${
                        cpe.margin_db >= 10
                          ? "text-emerald-400"
                          : cpe.margin_db >= 0
                          ? "text-amber-400"
                          : "text-red-400"
                      }`}
                    >
                      {cpe.margin_db.toFixed(1)} dB
                    </span>
                  </div>
                  <span className="text-[9px] text-slate-500 block mt-1">Click in table to show terrain profile</span>
                </div>
              </Popup>
            </CircleMarker>
          );
        })}

        {/* Measure Tool Rendering */}
        {measurePoints.length > 0 && (
          <Marker position={measurePoints[0]} icon={getStartPinIcon()} />
        )}
        {measurePoints.length > 1 && (
          <>
            <Marker position={measurePoints[1]} icon={getEndPinIcon()} />
            <Polyline positions={measurePoints} pathOptions={{ color: "#3B82F6", weight: 3, dashArray: "6,6" }}>
              <Tooltip permanent direction="center" className="measure-distance-tooltip">
                {haversineKm(measurePoints[0], measurePoints[1]).toFixed(2)} km
              </Tooltip>
            </Polyline>
          </>
        )}

        {/* Live Hover Pulse Marker */}
        {hoverPoint && (
          <Marker
            position={hoverPoint}
            icon={L.divIcon({
              html: `<div class="relative flex items-center justify-center">
                <span class="absolute w-8 h-8 rounded-full bg-blue-500/40 animate-ping"></span>
                <div class="w-3 h-3 rounded-full bg-blue-500 border border-white shadow-lg"></div>
              </div>`,
              className: "hover-pulse-icon",
              iconSize: [24, 24],
              iconAnchor: [12, 12],
            })}
          />
        )}
      </MapContainer>

      {/* Map Mode Floating Toolbar Overlay */}
      <div className="absolute top-4 right-4 z-[1000] flex flex-col gap-1.5 bg-slate-900/90 border border-slate-800 p-1.5 rounded-lg shadow-xl backdrop-blur max-w-[120px]">
        <button
          onClick={() => {
            if (setMapMode) setMapMode("normal");
            if (setMeasurePoints) setMeasurePoints([]);
          }}
          title="Pan & Selection Mode"
          className={`p-2 rounded-md transition ${
            mapMode === "normal"
              ? "bg-blue-600 text-white font-bold"
              : "text-slate-400 hover:text-white hover:bg-slate-800"
          }`}
        >
          <MousePointer className="w-4 h-4" />
        </button>
        <button
          onClick={() => {
            if (setMapMode) setMapMode("measure");
            if (setMeasurePoints) setMeasurePoints([]);
          }}
          title="Interactive Distance & Profile Measure Tool"
          className={`p-2 rounded-md transition ${
            mapMode === "measure"
              ? "bg-blue-600 text-white font-bold"
              : "text-slate-400 hover:text-white hover:bg-slate-800"
          }`}
        >
          <Ruler className="w-4 h-4" />
        </button>
        
        <div className="border-t border-slate-800 my-1"></div>
        
        {/* Theme Select Switcher */}
        <select
          value={mapTheme}
          onChange={(e) => setMapTheme && setMapTheme(e.target.value as any)}
          className="bg-slate-950 text-[10px] text-slate-300 border border-slate-800 rounded px-1 py-1 focus:outline-none focus:border-blue-500 w-full"
        >
          <option value="dark">Dark Matter</option>
          <option value="satellite">Satellite</option>
          <option value="street">Street Map</option>
        </select>
      </div>

      {/* Map Legend Overlay */}
      <div className="absolute bottom-4 left-4 z-[1000] p-3 rounded-lg border border-slate-800 bg-slate-900/90 backdrop-blur text-xs text-slate-300 space-y-2 max-w-[200px]">
        <h4 className="font-bold text-white text-[10px] uppercase tracking-wider">Legend</h4>
        <div className="space-y-1.5">
          <div className="flex items-center gap-2">
            <span className="w-3 h-3 rounded bg-[#2ecc71] block" />
            <span>High RSSI (&ge; -65 dBm)</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="w-3 h-3 rounded bg-[#27ae60] block" />
            <span>Good RSSI (-65 to -75)</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="w-3 h-3 rounded bg-[#f1c40f] block" />
            <span>Marginal (-75 to -85)</span>
          </div>
          
          {/* Opacity Slider */}
          <div className="border-t border-slate-800 my-1 pt-1.5 space-y-1">
            <div className="flex justify-between text-[9px] text-slate-400">
              <span>Grid Opacity</span>
              <span>{Math.round(opacity * 100)}%</span>
            </div>
            <input
              type="range"
              min="0.1"
              max="0.9"
              step="0.05"
              value={opacity}
              onChange={(e) => setOpacity && setOpacity(Number(e.target.value))}
              className="w-full h-1 bg-slate-800 rounded-lg appearance-none cursor-pointer accent-blue-500"
            />
          </div>

          <div className="border-t border-slate-800 my-1 pt-1.5 space-y-1.5">
            <div className="flex items-center gap-2">
              <span className="w-3.5 h-3.5 rounded-full bg-amber-500 border border-white flex items-center justify-center"><span className="w-1.5 h-1.5 rounded-full bg-slate-950"></span></span>
              <span>Active BTS Site</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="w-3.5 h-3.5 rounded-full bg-slate-700 border border-slate-500 flex items-center justify-center"><span className="w-1.5 h-1.5 rounded-full bg-slate-950"></span></span>
              <span>Candidate BTS</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="w-2.5 h-2.5 rounded-full bg-emerald-500 border border-white block" />
              <span>CPE: Excellent / Good</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="w-2.5 h-2.5 rounded-full bg-red-500 border border-white block" />
              <span>CPE: No Link</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
