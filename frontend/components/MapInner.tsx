"use client";

import React, { useEffect } from "react";
import { MapContainer, TileLayer, Marker, Popup, GeoJSON, Polygon, Polyline, useMap } from "react-leaflet";
import L from "leaflet";

// Custom Leaflet CSS DivIcons to avoid path issues and enable modern styling
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
}: MapInnerProps) {
  // Default center Buonaventura Colombia (SPRBUN)
  const defaultCenter: [number, number] = [3.89, -77.08];

  const geojsonStyle = (feature: any) => {
    return {
      fillColor: feature.properties.fill,
      fillOpacity: feature.properties["fill-opacity"] || 0.45,
      stroke: false,
      weight: 0,
    };
  };

  const btsCandidates = sites.filter((s) => s.is_bts_candidate);

  return (
    <div className="w-full h-full relative">
      <MapContainer center={defaultCenter} zoom={13} className="w-full h-full">
        {/* CartoDB Dark Matter map tiles */}
        <TileLayer
          url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>'
        />

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
            key={JSON.stringify(coverageGeojson.features?.[0]?.properties || {})}
            data={coverageGeojson}
            style={geojsonStyle}
          />
        )}

        {/* BTS Site Markers */}
        {btsCandidates.map((site, index) => {
          // Check if this BTS is active
          // Note: index matches btsCandidates
          const isActive = index === selectedBtsIndex;
          const latLng: [number, number] = [site.latitude, site.longitude];

          return (
            <Marker key={`bts-${index}`} position={latLng} icon={getBtsIcon(isActive)}>
              <Popup>
                <div className="text-xs space-y-2">
                  <div>
                    <span className="font-bold text-sm text-amber-400">BTS: {site.name}</span>
                    <span className="text-slate-400 block mt-0.5">Lat: {site.latitude.toFixed(5)}, Lon: {site.longitude.toFixed(5)}</span>
                  </div>
                  {!isActive && (
                    <button
                      onClick={() => onSelectBts(index)}
                      className="px-2 py-1 bg-amber-500 text-slate-950 font-semibold rounded hover:bg-amber-400 text-[10px] w-full transition cursor-pointer"
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
          const latLng: [number, number] = [cpe.latitude, cpe.longitude];

          return (
            <Marker
              key={`cpe-${index}`}
              position={latLng}
              icon={getCpeIcon(cpe.status, isSelected)}
              eventHandlers={{
                click: () => onSelectCpe(cpe),
              }}
            >
              <Popup>
                <div className="text-xs space-y-1">
                  <span className="font-bold text-white block">{cpe.name}</span>
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
            </Marker>
          );
        })}
      </MapContainer>

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
