"use client";

import React, { useState } from "react";
import { Table, Download, Search, Check, AlertTriangle, X } from "lucide-react";
import { cn } from "../lib/utils";

const SECTOR_COLORS = ["#3B82F6", "#22C55E", "#F59E0B"];
const SECTOR_LABELS = ["S1", "S2", "S3"];

export interface CpeResult {
  name: string;
  distance_km: number;
  elevation_m: number;
  rssi_dbm: number;
  margin_db: number;          // head-room above the reliability threshold (dB)
  raw_margin_db?: number;     // RSSI minus raw sensitivity (dB)
  tier?: number;              // 0 no-link, 1 marginal, 2 good, 3 excellent
  status: string;
  marker_color?: string;
  line_color?: string;
  latitude: number;
  longitude: number;
  best_sector?: number;
  best_sector_gain_db?: number;
  serving_bts_name?: string;
  serving_bts_index?: number;
}

// Single source of truth for CPE tier → colour, mirrors heatmap.coverage_tier.
// Falls back to head-room margin when the backend predates the tier field.
export function cpeTier(c: { tier?: number; margin_db: number }): number {
  if (typeof c.tier === "number") return c.tier;
  if (c.margin_db >= 20) return 3;
  if (c.margin_db >= 10) return 2;
  if (c.margin_db >= 0) return 1;
  return 0;
}

export const TIER_HEX = ["#EF4444", "#F59E0B", "#22C55E", "#16A34A"];

interface CpeTableProps {
  cpeResults: CpeResult[];
  selectedCpeName: string | null;
  onSelectCpe: (cpe: CpeResult) => void;
  sectorCount?: number;
}

export default function CpeTable({ cpeResults, selectedCpeName, onSelectCpe, sectorCount = 1 }: CpeTableProps) {
  const [searchTerm, setSearchTerm] = useState("");

  const handleExportCsv = () => {
    if (!cpeResults || cpeResults.length === 0) return;
    const hasServingBts = cpeResults.some((cpe: any) => cpe.serving_bts_name !== undefined && cpe.serving_bts_name !== "");
    const headers = ["Name", "Distance (km)", "Elevation (m ASL)", "RSSI (dBm)", "Link Margin (dB)", "Status", "Latitude", "Longitude"];
    if (hasServingBts) {
      headers.push("Serving Tower");
    }
    const rows = cpeResults.map((r: any) => {
      const row = [
        `"${r.name.replace(/"/g, '""')}"`,
        r.distance_km,
        r.elevation_m,
        r.rssi_dbm,
        r.margin_db,
        `"${r.status.replace(/🟢|🟡|🔴|⛔/g, "").trim()}"`,
        r.latitude,
        r.longitude,
      ];
      if (hasServingBts) {
        row.push(`"${(r.serving_bts_name || "").replace(/"/g, '""')}"`);
      }
      return row;
    });
    
    const csvContent = "\uFEFF" + [headers.join(","), ...rows.map((e) => e.join(","))].join("\n");
    const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.setAttribute("href", url);
    link.setAttribute("download", "wifrost_cpe_analysis.csv");
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  const filteredCpes = cpeResults.filter((cpe) =>
    cpe.name.toLowerCase().includes(searchTerm.toLowerCase())
  );

  const getStatusStyle = (status: string) => {
    if (status.includes("🟢") || status.toLowerCase().includes("excellent")) {
      return "text-emerald-400 bg-emerald-500/10 border-emerald-500/20";
    }
    if (status.includes("🟡") || status.toLowerCase().includes("marginal")) {
      return "text-amber-400 bg-amber-500/10 border-amber-500/20";
    }
    return "text-red-400 bg-red-500/10 border-red-500/20";
  };

  return (
    <div className="glass-panel rounded-2xl p-4 space-y-4">
      {/* Header controls */}
      <div className="flex flex-col gap-3 pb-3 border-b border-white/5">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Table className="w-4 h-4 text-blue-400" />
            <h3 className="text-xs font-bold text-white uppercase tracking-wider">Client Link Margin</h3>
          </div>
          <button
            onClick={handleExportCsv}
            disabled={cpeResults.length === 0}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-white/5 border border-white/10 hover:bg-white/10 hover:border-white/20 disabled:opacity-50 text-white rounded-xl text-xs transition font-semibold cursor-pointer"
          >
            <Download className="w-3.5 h-3.5" />
            Export CSV
          </button>
        </div>

        {/* Search box */}
        <div className="relative w-full">
          <Search className="absolute left-3 top-2.5 w-3.5 h-3.5 text-slate-500" />
          <input
            type="text"
            placeholder="Search CPEs..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="pl-9 pr-3 py-2 w-full bg-black/30 border border-white/10 rounded-xl text-xs text-gray-200 placeholder-slate-500 focus:outline-none focus:border-blue-500/50"
          />
        </div>
      </div>

      {/* CPE List Cards */}
      <div className="overflow-y-auto overflow-x-hidden rounded-xl space-y-2 max-h-[320px] pr-1 custom-scrollbar">
        {filteredCpes.length === 0 ? (
          <div className="py-8 text-center text-slate-500 text-xs bg-white/[0.01] border border-white/5 rounded-xl">
            {cpeResults.length === 0 ? "No simulation data available. Run simulation first." : "No matching CPEs found."}
          </div>
        ) : (
          filteredCpes.map((cpe, idx) => {
            const isSelected = cpe.name === selectedCpeName;
            const tierVal = cpeTier(cpe);
            
            // Tier color mappings
            const textTierColors = ["text-red-400", "text-amber-400", "text-emerald-400", "text-green-400"];
            const bgDotColors = [
              "bg-red-500 shadow-[0_0_6px_rgba(239,68,68,0.6)]",
              "bg-amber-500 shadow-[0_0_6px_rgba(245,158,11,0.6)]",
              "bg-emerald-500 shadow-[0_0_6px_rgba(16,185,129,0.6)]",
              "bg-green-500 shadow-[0_0_6px_rgba(34,197,94,0.6)]"
            ];

            return (
              <div
                key={idx}
                onClick={() => onSelectCpe(cpe)}
                className={`p-3 rounded-xl border transition-all duration-300 cursor-pointer flex items-center justify-between gap-3 ${
                  isSelected
                    ? "bg-blue-600/10 border-blue-500/40 shadow-[0_0_12px_rgba(59,130,246,0.1)] animate-pulse-subtle"
                    : "bg-white/[0.02] border-white/5 hover:bg-white/[0.05] hover:border-white/10"
                }`}
              >
                {/* Left Side: Name, serving tower, best sector badge */}
                <div className="flex flex-col gap-1 min-w-0">
                  <span className="text-xs font-bold text-white truncate flex items-center gap-1.5">
                    {isSelected && <span className="w-1.5 h-1.5 rounded-full bg-blue-500 flex-shrink-0" />}
                    {cpe.name}
                  </span>
                  
                  <div className="flex items-center gap-1.5 flex-wrap">
                    {cpe.serving_bts_name && (
                      <span className="text-[10px] text-slate-400 font-medium truncate max-w-[120px]">
                        📡 {cpe.serving_bts_name}
                      </span>
                    )}
                    
                    {cpe.best_sector !== undefined && (
                      <span
                        className="inline-flex items-center gap-1 text-[9px] font-semibold px-1.5 py-0.5 rounded-md"
                        style={{
                          color: SECTOR_COLORS[cpe.best_sector % 3],
                          backgroundColor: `${SECTOR_COLORS[cpe.best_sector % 3]}10`,
                          border: `1px solid ${SECTOR_COLORS[cpe.best_sector % 3]}20`
                        }}
                      >
                        {sectorCount > 1 ? SECTOR_LABELS[cpe.best_sector] : "S1"}
                      </span>
                    )}

                    {cpe.best_sector !== undefined && (cpe.best_sector_gain_db ?? 0) < -20 && (
                      <span className="text-[9px] font-semibold text-amber-400 bg-amber-500/10 border border-amber-500/20 px-1 py-0.5 rounded-md">
                        Gap ⚠
                      </span>
                    )}
                  </div>
                </div>

                {/* Right Side: Margin, RSSI, status indicator dot */}
                <div className="flex items-center gap-3 flex-shrink-0 text-right">
                  <div className="flex flex-col gap-0.5">
                    <span className={`text-xs font-bold ${textTierColors[tierVal]}`}>
                      {cpe.margin_db.toFixed(1)} dB
                    </span>
                    <span className="text-[10px] text-slate-400 font-medium">
                      {cpe.rssi_dbm.toFixed(1)} dBm
                    </span>
                  </div>
                  <span className={`w-2 h-2 rounded-full flex-shrink-0 ${bgDotColors[tierVal]}`} />
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
