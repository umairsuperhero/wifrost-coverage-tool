"use client";

import React, { useState } from "react";
import { Table, Download, Search, Check, AlertTriangle, X } from "lucide-react";

interface CpeResult {
  name: string;
  distance_km: number;
  elevation_m: number;
  rssi_dbm: number;
  margin_db: number;
  status: string;
  latitude: number;
  longitude: number;
}

interface CpeTableProps {
  cpeResults: CpeResult[];
  selectedCpeName: string | null;
  onSelectCpe: (cpe: CpeResult) => void;
}

export default function CpeTable({ cpeResults, selectedCpeName, onSelectCpe }: CpeTableProps) {
  const [searchTerm, setSearchTerm] = useState("");

  const handleExportCsv = () => {
    if (!cpeResults || cpeResults.length === 0) return;
    const headers = ["Name", "Distance (km)", "Elevation (m ASL)", "RSSI (dBm)", "Link Margin (dB)", "Status", "Latitude", "Longitude"];
    const rows = cpeResults.map((r) => [
      `"${r.name.replace(/"/g, '""')}"`,
      r.distance_km,
      r.elevation_m,
      r.rssi_dbm,
      r.margin_db,
      `"${r.status.replace(/🟢|🟡|🔴/g, "").trim()}"`,
      r.latitude,
      r.longitude,
    ]);
    
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
    <div className="bg-slate-900/60 rounded-xl border border-slate-800 p-5 space-y-4">
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center border-b border-slate-800 pb-3 gap-3">
        <div className="flex items-center gap-2">
          <Table className="w-5 h-5 text-blue-400" />
          <h3 className="font-semibold text-white">Client Link Margin Analysis</h3>
        </div>

        <div className="flex items-center gap-3 w-full sm:w-auto">
          {/* Search box */}
          <div className="relative flex-1 sm:w-60">
            <Search className="absolute left-3 top-2.5 w-4 h-4 text-slate-500" />
            <input
              type="text"
              placeholder="Search CPEs..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="pl-9 pr-3 py-1.5 w-full bg-slate-950/60 border border-slate-850 rounded-lg text-sm text-gray-200 placeholder-slate-500 focus:outline-none focus:border-blue-500"
            />
          </div>

          <button
            onClick={handleExportCsv}
            disabled={cpeResults.length === 0}
            className="flex items-center gap-2 px-3 py-1.5 bg-slate-800 hover:bg-slate-700 disabled:opacity-50 text-white rounded-lg text-sm transition font-medium cursor-pointer border border-slate-700"
          >
            <Download className="w-4 h-4" />
            Export CSV
          </button>
        </div>
      </div>

      <div className="overflow-x-auto rounded-lg border border-slate-850 max-h-[300px]">
        <table className="w-full text-left text-sm text-slate-300">
          <thead className="bg-slate-950/50 text-slate-400 font-semibold border-b border-slate-850">
            <tr>
              <th className="py-3 px-4">CPE Name</th>
              <th className="py-3 px-4">Distance</th>
              <th className="py-3 px-4">Elevation</th>
              <th className="py-3 px-4">RSSI</th>
              <th className="py-3 px-4">Link Margin</th>
              <th className="py-3 px-4">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-850">
            {filteredCpes.length === 0 ? (
              <tr>
                <td colSpan={6} className="py-8 text-center text-slate-500 text-sm">
                  {cpeResults.length === 0 ? "No simulation data available. Run simulation first." : "No matching CPEs found."}
                </td>
              </tr>
            ) : (
              filteredCpes.map((cpe, idx) => {
                const isSelected = cpe.name === selectedCpeName;
                return (
                  <tr
                    key={idx}
                    onClick={() => onSelectCpe(cpe)}
                    className={`hover:bg-slate-800/40 transition cursor-pointer ${
                      isSelected ? "bg-blue-600/10 hover:bg-blue-600/15 font-medium" : ""
                    }`}
                  >
                    <td className="py-3 px-4 text-white flex items-center gap-2">
                      {isSelected && <span className="w-1.5 h-1.5 rounded-full bg-blue-500 animate-pulse" />}
                      {cpe.name}
                    </td>
                    <td className="py-3 px-4">{cpe.distance_km.toFixed(2)} km</td>
                    <td className="py-3 px-4">{cpe.elevation_m.toFixed(1)} m</td>
                    <td className={`py-3 px-4 ${cpe.rssi_dbm >= -85 ? "text-slate-100" : "text-red-400"}`}>
                      {cpe.rssi_dbm.toFixed(1)} dBm
                    </td>
                    <td className={`py-3 px-4 font-semibold ${cpe.margin_db >= 10 ? "text-emerald-400" : cpe.margin_db >= 0 ? "text-amber-400" : "text-red-400"}`}>
                      {cpe.margin_db.toFixed(1)} dB
                    </td>
                    <td className="py-3 px-4">
                      <span className={`px-2 py-0.5 rounded-full text-xs font-semibold border ${getStatusStyle(cpe.status)}`}>
                        {cpe.status.replace(/🟢|🟡|🔴/g, "").trim()}
                      </span>
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
