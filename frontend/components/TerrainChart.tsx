"use client";

import React from "react";
import { AlertCircle, Activity } from "lucide-react";

interface ProfilePoint {
  distance_km: number;
  terrain_m: number;
  los_m: number;
  fresnel_lower_m: number;
  fresnel_upper_m: number;
}

interface TerrainChartProps {
  profileData: ProfilePoint[];
  label: string;
  isFlat: boolean;
  cpeName: string;
  btsElevation?: number;
  cpeElevation?: number;
  btsTotalHeight?: number;
  cpeTotalHeight?: number;
}

export default function TerrainChart({
  profileData,
  label,
  isFlat,
  cpeName,
  btsElevation = 0,
  cpeElevation = 0,
  btsTotalHeight = 0,
  cpeTotalHeight = 0,
}: TerrainChartProps) {
  if (isFlat) {
    return (
      <div className="bg-slate-900/60 rounded-xl border border-slate-800 p-5 flex flex-col items-center justify-center h-[280px] text-slate-400">
        <Activity className="w-8 h-8 text-slate-500 mb-2" />
        <p className="text-sm">Terrain profile is not available in Flat Earth mode.</p>
        <p className="text-xs text-slate-500 mt-1">Provide an OpenTopography API key to download SRTM terrain profiles.</p>
      </div>
    );
  }

  if (!profileData || profileData.length === 0) {
    return (
      <div className="bg-slate-900/60 rounded-xl border border-slate-800 p-5 flex flex-col items-center justify-center h-[280px] text-slate-400">
        <Activity className="w-8 h-8 text-slate-500 mb-2" />
        <p className="text-sm">Select a CPE site to view the terrain profile.</p>
      </div>
    );
  }

  // Dimensions
  const width = 800;
  const height = 300;
  const paddingX = 60;
  const paddingY = 40;

  // Extents
  const distances = profileData.map((d) => d.distance_km);
  const maxDist = Math.max(...distances, 0.1);

  // We want to scale Y axis based on all heights
  const allHeights = profileData.flatMap((d) => [
    d.terrain_m,
    d.los_m,
    d.fresnel_lower_m,
    d.fresnel_upper_m,
  ]);
  const minHeight = Math.min(...allHeights, btsElevation, cpeElevation);
  const maxHeight = Math.max(...allHeights, btsTotalHeight, cpeTotalHeight);
  const heightRange = maxHeight - minHeight || 10;
  const padY = heightRange * 0.15; // 15% padding top and bottom

  const yMin = Math.max(0, minHeight - padY);
  const yMax = maxHeight + padY;
  const yRange = yMax - yMin;

  // Helper functions to map coordinates to SVG space
  const getX = (dist: number) => {
    return paddingX + (dist / maxDist) * (width - 2 * paddingX);
  };

  const getY = (h: number) => {
    return height - paddingY - ((h - yMin) / yRange) * (height - 2 * paddingY);
  };

  // Build SVG Paths
  // 1. Terrain filled path
  let terrainPath = `M ${getX(profileData[0].distance_km)} ${getY(0)}`;
  profileData.forEach((pt) => {
    terrainPath += ` L ${getX(pt.distance_km)} ${getY(pt.terrain_m)}`;
  });
  terrainPath += ` L ${getX(profileData[profileData.length - 1].distance_km)} ${getY(0)} Z`;

  // 2. Fresnel Zone filled band path
  let fresnelPath = `M ${getX(profileData[0].distance_km)} ${getY(profileData[0].fresnel_upper_m)}`;
  profileData.forEach((pt) => {
    fresnelPath += ` L ${getX(pt.distance_km)} ${getY(pt.fresnel_upper_m)}`;
  });
  for (let i = profileData.length - 1; i >= 0; i--) {
    const pt = profileData[i];
    fresnelPath += ` L ${getX(pt.distance_km)} ${getY(pt.fresnel_lower_m)}`;
  }
  fresnelPath += " Z";

  // 3. Line of Sight Path
  let losPath = `M ${getX(profileData[0].distance_km)} ${getY(profileData[0].los_m)}`;
  profileData.forEach((pt) => {
    losPath += ` L ${getX(pt.distance_km)} ${getY(pt.los_m)}`;
  });

  const isObstructed = label.includes("⚠️") || label.toLowerCase().includes("obstruction");

  return (
    <div className="bg-slate-900/60 rounded-xl border border-slate-800 p-5 space-y-4">
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center border-b border-slate-800 pb-3 gap-2">
        <div className="flex items-center gap-2">
          <Activity className="w-5 h-5 text-blue-400" />
          <h3 className="font-semibold text-white">Terrain Cross-Section &amp; Fresnel Zone</h3>
        </div>
        <span
          className={`px-3 py-1 rounded-full text-xs font-semibold border ${
            isObstructed
              ? "bg-red-500/10 border-red-500/20 text-red-400"
              : "bg-emerald-500/10 border-emerald-500/20 text-emerald-400"
          }`}
        >
          {label}
        </span>
      </div>

      <div className="relative w-full overflow-x-auto bg-slate-950/40 rounded-lg p-2 border border-slate-850">
        <svg viewBox={`0 0 ${width} ${height}`} className="w-full min-w-[700px] h-auto overflow-visible">
          {/* Grid lines */}
          {[0, 0.25, 0.5, 0.75, 1].map((pct, idx) => {
            const h = yMin + pct * yRange;
            const y = getY(h);
            const dist = pct * maxDist;
            const x = getX(dist);
            return (
              <React.Fragment key={idx}>
                {/* Horizontal grid lines */}
                <line x1={paddingX} y1={y} x2={width - paddingX} y2={y} stroke="#334155" strokeWidth="0.5" strokeDasharray="3,3" />
                <text x={paddingX - 10} y={y + 4} fill="#94a3b8" fontSize="10" textAnchor="end">
                  {Math.round(h)}m
                </text>

                {/* Vertical grid lines */}
                <line x1={x} y1={paddingY} x2={x} y2={height - paddingY} stroke="#334155" strokeWidth="0.5" strokeDasharray="3,3" />
                <text x={x} y={height - paddingY + 15} fill="#94a3b8" fontSize="10" textAnchor="middle">
                  {dist.toFixed(2)} km
                </text>
              </React.Fragment>
            );
          })}

          {/* Shaded Fresnel Zone */}
          <path d={fresnelPath} fill="rgba(59, 130, 246, 0.12)" stroke="rgba(59, 130, 246, 0.3)" strokeWidth="0.5" />

          {/* Shaded Terrain */}
          <path d={terrainPath} fill="url(#terrainGradient)" stroke="#8B7765" strokeWidth="2" />

          {/* Line of Sight */}
          <path d={losPath} fill="none" stroke="#2563EB" strokeWidth="2" strokeDasharray="5,5" />

          {/* Tower markings */}
          {/* BTS Tower */}
          <line x1={getX(0)} y1={getY(btsElevation)} x2={getX(0)} y2={getY(btsTotalHeight)} stroke="#3B82F6" strokeWidth="3" />
          <circle cx={getX(0)} cy={getY(btsTotalHeight)} r="4" fill="#3B82F6" />
          <text x={getX(0)} y={getY(btsTotalHeight) - 10} fill="#FFFFFF" fontSize="10" fontWeight="bold" textAnchor="middle">
            BTS ({btsTotalHeight - btsElevation}m)
          </text>

          {/* CPE Tower */}
          <line x1={getX(maxDist)} y1={getY(cpeElevation)} x2={getX(maxDist)} y2={getY(cpeTotalHeight)} stroke="#10B981" strokeWidth="3" />
          <circle cx={getX(maxDist)} cy={getY(cpeTotalHeight)} r="4" fill="#10B981" />
          <text x={getX(maxDist)} y={getY(cpeTotalHeight) - 10} fill="#FFFFFF" fontSize="10" fontWeight="bold" textAnchor="middle">
            {cpeName} ({cpeTotalHeight - cpeElevation}m)
          </text>

          {/* Gradients */}
          <defs>
            <linearGradient id="terrainGradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#4A3B32" stopOpacity="0.85" />
              <stop offset="100%" stopColor="#1E1611" stopOpacity="0.4" />
            </linearGradient>
          </defs>
        </svg>
      </div>

      <div className="flex flex-wrap gap-4 text-xs justify-center border-t border-slate-800/60 pt-3">
        <div className="flex items-center gap-1.5">
          <span className="w-3 h-0.5 bg-[#8B7765] block" />
          <span className="text-slate-400">Terrain Elevation</span>
        </div>
        <div className="flex items-center gap-1.5">
          <span className="w-3 h-0.5 bg-[#2563EB] border-t border-dashed border-spacing-1 block" />
          <span className="text-slate-400">Line of Sight (LoS)</span>
        </div>
        <div className="flex items-center gap-1.5">
          <span className="w-3 h-2 bg-blue-500/10 border border-blue-500/20 block rounded-sm" />
          <span className="text-slate-400">1st Fresnel Zone (60% clearance required)</span>
        </div>
      </div>
    </div>
  );
}
