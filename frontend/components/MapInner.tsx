"use client";

import React, { useState, useMemo, useRef, useEffect, useCallback } from "react";
import Map, { Source, Layer, Marker, Popup, NavigationControl, MapRef } from "react-map-gl/maplibre";
import "maplibre-gl/dist/maplibre-gl.css";
import { MousePointer, Ruler, MapPin } from "lucide-react";
import * as turf from "@turf/turf";

// Helper to generate a GeoJSON polygon for a sector wedge
function generateSectorGeoJSON(btsLat: number, btsLon: number, azimuth: number, hpbw: number, radiusKm: number) {
  const points: [number, number][] = [[btsLon, btsLat]]; // turf uses [lon, lat]
  const startAngle = azimuth - hpbw / 2;
  const endAngle = azimuth + hpbw / 2;
  const numPts = 30;

  for (let i = 0; i <= numPts; i++) {
    const angle = startAngle + (i / numPts) * (endAngle - startAngle);
    // standard bearing is clockwise from North. turf.destination takes bearing in degrees (-180 to 180 or 0 to 360)
    const pt = turf.destination([btsLon, btsLat], radiusKm, angle, { units: "kilometers" });
    points.push(pt.geometry.coordinates as [number, number]);
  }
  points.push([btsLon, btsLat]);
  
  return turf.polygon([points]);
}

const TIER_HEX = ["#EF4444", "#F59E0B", "#22C55E", "#16A34A"];
const getCpeColor = (cpe: { tier?: number; margin_db: number }): string => {
  if (typeof cpe.tier === "number") return TIER_HEX[cpe.tier] ?? "#EF4444";
  if (cpe.margin_db >= 20) return "#16A34A";
  if (cpe.margin_db >= 10) return "#22C55E";
  if (cpe.margin_db >= 0)  return "#F59E0B";
  return "#EF4444";
};

const SECTOR_COLORS = ["#38BDF8", "#22C55E", "#F59E0B"];

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
  onAddCpe?: (lat: number, lng: number) => void;
  mapMode?: "normal" | "measure" | "addcpe";
  setMapMode?: (mode: "normal" | "measure" | "addcpe") => void;
  hoverPoint?: [number, number] | null;
  opacity?: number;
  setOpacity?: (opacity: number) => void;
  mapTheme?: "dark" | "satellite" | "street";
  setMapTheme?: (theme: "dark" | "satellite" | "street") => void;
  measurePoints?: [number, number][];
  setMeasurePoints?: (points: [number, number][]) => void;
  isSidebarExpanded?: boolean;
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
  onAddCpe,
  mapMode = "normal",
  setMapMode,
  hoverPoint,
  opacity = 0.45,
  setOpacity,
  mapTheme = "dark",
  setMapTheme,
  measurePoints = [],
  setMeasurePoints,
  isSidebarExpanded = true,
}: MapInnerProps) {
  const mapRef = useRef<MapRef>(null);
  const defaultCenter = { longitude: -77.08, latitude: 3.89, zoom: 13 };

  const [popupInfo, setPopupInfo] = useState<any>(null);

  // Auto-fit bounds when sites or geometry changes
  useEffect(() => {
    if (!mapRef.current || sites.length === 0) return;
    const coords: [number, number][] = [];
    sites.forEach((s) => coords.push([s.longitude, s.latitude]));
    
    if (coords.length > 0) {
      const line = turf.lineString(coords);
      const bbox = turf.bbox(line) as [number, number, number, number];
      // Padding handles sidebar overlap nicely
      mapRef.current.fitBounds(bbox, { padding: { top: 50, bottom: 50, left: isSidebarExpanded ? 400 : 100, right: 50 }, maxZoom: 15, duration: 1000 });
    }
  }, [sites, isSidebarExpanded]);

  const getMapStyle = () => {
    if (mapTheme === "satellite") {
      return {
        version: 8,
        sources: {
          satellite: {
            type: "raster",
            tiles: ["https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"],
            tileSize: 256,
          },
        },
        layers: [{ id: "satellite", type: "raster", source: "satellite" }],
      } as any;
    }
    if (mapTheme === "street") {
      return "https://basemaps.cartocdn.com/gl/voyager-gl-style/style.json";
    }
    return "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json";
  };

  const handleMapClick = (e: maplibregl.MapMouseEvent) => {
    if (mapMode === "measure" && setMeasurePoints) {
      const newPoints = [...measurePoints, [e.lngLat.lat, e.lngLat.lng] as [number, number]];
      if (newPoints.length > 2) {
        setMeasurePoints([[e.lngLat.lat, e.lngLat.lng]]);
      } else {
        setMeasurePoints(newPoints);
      }
    } else if (mapMode === "addcpe" && onAddCpe) {
      onAddCpe(e.lngLat.lat, e.lngLat.lng);
    }
  };

  const btsCandidates = sites.filter((s) => s.is_bts_candidate);

  // Create sector feature collection
  const sectorGeoJSON = useMemo(() => {
    if (!sectorInfo || selectedBtsIndex === -1 || !btsCandidates[selectedBtsIndex]) return null;
    const bts = btsCandidates[selectedBtsIndex];
    const features = sectorInfo.azimuths.map((az, i) => {
      const poly = generateSectorGeoJSON(bts.latitude, bts.longitude, az, sectorInfo.hpbw, sectorInfo.radiusKm);
      poly.properties = { color: SECTOR_COLORS[i % SECTOR_COLORS.length] };
      return poly;
    });
    return turf.featureCollection(features);
  }, [sectorInfo, selectedBtsIndex, btsCandidates]);

  // Filter the coverage geojson based on threshold
  const filteredCoverage = useMemo(() => {
    if (!coverageGeojson || !coverageGeojson.features) return null;
    const filteredFeatures = coverageGeojson.features.filter((f: any) => {
      if (typeof f.properties?.rssi === "number") {
        return f.properties.rssi >= activeThreshold;
      }
      return true;
    });
    return turf.featureCollection(filteredFeatures);
  }, [coverageGeojson, activeThreshold]);

  return (
    <div className={`w-full h-full relative ${mapMode !== "normal" ? "cursor-crosshair" : ""}`}>
      <Map
        ref={mapRef}
        initialViewState={defaultCenter}
        mapStyle={getMapStyle()}
        onClick={handleMapClick}
        interactiveLayerIds={['coverage-fill']}
      >
        <NavigationControl position="bottom-right" />

        {/* Heatmap GeoJSON */}
        {filteredCoverage && (
          <Source id="coverage-source" type="geojson" data={filteredCoverage as any}>
            <Layer
              id="coverage-fill"
              type="fill"
              paint={{
                "fill-color": ["get", "fill"],
                "fill-opacity": opacity,
                "fill-outline-color": "rgba(0,0,0,0)",
              }}
            />
          </Source>
        )}

        {/* Sector wedges */}
        {sectorGeoJSON && (
          <Source id="sectors-source" type="geojson" data={sectorGeoJSON as any}>
            <Layer
              id="sectors-fill"
              type="fill"
              paint={{
                "fill-color": ["get", "color"],
                "fill-opacity": 0.12,
              }}
            />
            <Layer
              id="sectors-line"
              type="line"
              paint={{
                "line-color": ["get", "color"],
                "line-width": 1,
                "line-dasharray": [5, 5],
              }}
            />
          </Source>
        )}

        {/* BTS Site Markers */}
        {btsCandidates.map((site, index) => {
          const isActive = index === selectedBtsIndex;
          return (
            <Marker
              key={`bts-${index}`}
              longitude={site.longitude}
              latitude={site.latitude}
              anchor="center"
              draggable
              onDragEnd={(e) => {
                if (onMoveBts) onMoveBts(index, e.lngLat.lat, e.lngLat.lng);
              }}
              onClick={(e) => {
                e.originalEvent.stopPropagation();
                setPopupInfo({ type: "bts", site, index, isActive });
              }}
            >
              <div className="relative flex items-center justify-center cursor-pointer">
                {isActive && <span className="absolute w-10 h-10 rounded-full bg-primary/30 animate-ping"></span>}
                <div className={`w-6 h-6 rounded-full flex items-center justify-center shadow-xl ${isActive ? "bg-primary border-2 border-white" : "bg-slate-700 border border-slate-500"}`}>
                  <div className="w-2.5 h-2.5 rounded-full bg-slate-950"></div>
                </div>
              </div>
            </Marker>
          );
        })}

        {/* CPE Markers */}
        {cpeResults.map((cpe, index) => {
          const isSelected = cpe.name === selectedCpeName;
          const color = getCpeColor(cpe);
          return (
            <Marker
              key={`cpe-${index}`}
              longitude={cpe.longitude}
              latitude={cpe.latitude}
              anchor="center"
              onClick={(e) => {
                e.originalEvent.stopPropagation();
                onSelectCpe(cpe);
                setPopupInfo({ type: "cpe", cpe });
              }}
            >
              <div className="relative flex items-center justify-center cursor-pointer">
                {isSelected && <span className="absolute w-8 h-8 rounded-full bg-primary/40 animate-ping"></span>}
                <div 
                  className={`rounded-full border border-white shadow-lg transition-transform duration-300 ${isSelected ? "w-4 h-4 border-2 scale-125" : "w-3 h-3"}`}
                  style={{ backgroundColor: color }}
                />
              </div>
            </Marker>
          );
        })}

        {/* Popup Rendering */}
        {popupInfo?.type === "bts" && (
          <Popup
            anchor="bottom"
            longitude={popupInfo.site.longitude}
            latitude={popupInfo.site.latitude}
            onClose={() => setPopupInfo(null)}
            closeOnClick={false}
            offset={14}
            className="spatial-popup"
          >
            <div className="space-y-2">
              <div>
                <span className="font-bold text-sm text-primary">BTS: {popupInfo.site.name}</span>
                <span className="text-muted-foreground block mt-0.5 text-xs font-mono">Lat: {popupInfo.site.latitude.toFixed(5)}, Lon: {popupInfo.site.longitude.toFixed(5)}</span>
              </div>
              {!popupInfo.isActive && (
                <button
                  onClick={() => {
                    onSelectBts(popupInfo.index);
                    setPopupInfo(null);
                  }}
                  className="px-2 py-1.5 bg-primary text-primary-foreground font-semibold rounded hover:bg-opacity-80 text-[10px] w-full transition cursor-pointer border-none uppercase tracking-wider"
                >
                  Set as Active BTS
                </button>
              )}
            </div>
          </Popup>
        )}

        {popupInfo?.type === "cpe" && (
          <Popup
            anchor="bottom"
            longitude={popupInfo.cpe.longitude}
            latitude={popupInfo.cpe.latitude}
            onClose={() => setPopupInfo(null)}
            closeOnClick={false}
            offset={12}
            className="spatial-popup"
          >
            <div className="text-xs space-y-1">
              <span className="font-bold text-foreground block">{popupInfo.cpe.name}</span>
              {popupInfo.cpe.serving_bts_name && (
                <span className="text-[10px] text-primary block">Server: {popupInfo.cpe.serving_bts_name}</span>
              )}
              <div className="grid grid-cols-2 gap-x-2 text-[10px] font-mono mt-2">
                <span className="text-muted-foreground">Dist:</span>
                <span className="text-right">{popupInfo.cpe.distance_km.toFixed(2)} km</span>
                <span className="text-muted-foreground">RSSI:</span>
                <span className="text-right font-medium">{popupInfo.cpe.rssi_dbm.toFixed(1)} dBm</span>
                <span className="text-muted-foreground">Margin:</span>
                <span className={`text-right font-bold ${popupInfo.cpe.margin_db >= 10 ? "text-emerald-400" : popupInfo.cpe.margin_db >= 0 ? "text-amber-400" : "text-red-400"}`}>
                  {popupInfo.cpe.margin_db.toFixed(1)} dB
                </span>
              </div>
            </div>
          </Popup>
        )}
      </Map>

      {/* Floating Toolbar Overlay */}
      <div className="glass-panel absolute top-4 right-4 z-[10] flex flex-col gap-1 p-1 rounded-xl">
        <button
          onClick={() => { if (setMapMode) setMapMode("normal"); if (setMeasurePoints) setMeasurePoints([]); }}
          title="Pan & Selection Mode"
          className={`p-2.5 rounded-lg transition-all ${mapMode === "normal" ? "bg-primary text-primary-foreground shadow-md" : "text-muted-foreground hover:text-foreground hover:bg-white/5"}`}
        >
          <MousePointer className="w-4 h-4" />
        </button>
        <button
          onClick={() => { if (setMapMode) setMapMode("measure"); if (setMeasurePoints) setMeasurePoints([]); }}
          title="Measure Tool"
          className={`p-2.5 rounded-lg transition-all ${mapMode === "measure" ? "bg-primary text-primary-foreground shadow-md" : "text-muted-foreground hover:text-foreground hover:bg-white/5"}`}
        >
          <Ruler className="w-4 h-4" />
        </button>
        <button
          onClick={() => { if (setMapMode) setMapMode("addcpe"); if (setMeasurePoints) setMeasurePoints([]); }}
          title="Add CPE Client"
          className={`p-2.5 rounded-lg transition-all ${mapMode === "addcpe" ? "bg-primary text-primary-foreground shadow-md" : "text-muted-foreground hover:text-foreground hover:bg-white/5"}`}
        >
          <MapPin className="w-4 h-4" />
        </button>

        <div className="w-full h-px bg-border my-1" />
        
        <select
          value={mapTheme}
          onChange={(e) => setMapTheme && setMapTheme(e.target.value as any)}
          className="bg-transparent text-[10px] font-medium text-foreground p-1.5 focus:outline-none w-full text-center appearance-none cursor-pointer"
        >
          <option value="dark">Dark</option>
          <option value="satellite">Sat</option>
          <option value="street">Street</option>
        </select>
      </div>

      {/* Map Legend Floating Ornament */}
      <div className={`glass-panel absolute bottom-8 z-[10] p-4 rounded-2xl text-xs text-foreground space-y-3 min-w-[220px] transition-all duration-700 ease-[cubic-bezier(0.16,1,0.3,1)] ${
        isSidebarExpanded ? "left-[380px]" : "left-[96px]"
      }`}>
        <h4 className="font-bold text-[10px] uppercase tracking-widest text-muted-foreground">Signal Legend</h4>
        <div className="space-y-2 font-mono">
          <div className="flex items-center justify-between gap-3">
            <div className="flex items-center gap-2">
              <span className="w-3 h-3 rounded-md bg-[#2ecc71] border border-white/10" />
              <span>High</span>
            </div>
            <span className="text-[10px] text-muted-foreground">&ge; -65 dBm</span>
          </div>
          <div className="flex items-center justify-between gap-3">
            <div className="flex items-center gap-2">
              <span className="w-3 h-3 rounded-md bg-[#27ae60] border border-white/10" />
              <span>Good</span>
            </div>
            <span className="text-[10px] text-muted-foreground">-65 to -75</span>
          </div>
          <div className="flex items-center justify-between gap-3">
            <div className="flex items-center gap-2">
              <span className="w-3 h-3 rounded-md bg-[#f1c40f] border border-white/10" />
              <span>Marginal</span>
            </div>
            <span className="text-[10px] text-muted-foreground">-75 to -85</span>
          </div>
          
          <div className="w-full h-px bg-border my-2" />
          
          <div className="space-y-1.5">
            <div className="flex justify-between text-[9px] text-muted-foreground uppercase tracking-wider">
              <span>Heatmap Opacity</span>
              <span>{Math.round(opacity * 100)}%</span>
            </div>
            <input
              type="range"
              min="0.1"
              max="0.9"
              step="0.05"
              value={opacity}
              onChange={(e) => setOpacity && setOpacity(Number(e.target.value))}
              className="w-full h-1.5 bg-secondary rounded-full appearance-none cursor-pointer accent-primary"
            />
          </div>
        </div>
      </div>
    </div>
  );
}
