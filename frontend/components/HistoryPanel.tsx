"use client";

import React from "react";
import { Trash2, Calendar, MapPin, Radio, RefreshCw, Database } from "lucide-react";

export interface HistoryRunSummary {
  id: string;
  created_at: string;
  project: string;
  bts_name: string;
  bts_lat: number;
  bts_lon: number;
  frequency: number;
  eirp_dbm: number;
  environment: string;
  model: string;
  coverage_pct: number;
  max_range_km: number;
  avg_rssi: number;
}

interface HistoryPanelProps {
  runs: HistoryRunSummary[];
  loading: boolean;
  onSelectRun: (id: string) => void;
  onDeleteRun: (id: string) => void;
  onRefresh: () => void;
}

export default function HistoryPanel({
  runs,
  loading,
  onSelectRun,
  onDeleteRun,
  onRefresh,
}: HistoryPanelProps) {
  const formatDate = (dateStr: string) => {
    try {
      const date = new Date(dateStr);
      return date.toLocaleDateString(undefined, {
        month: "short",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      });
    } catch {
      return dateStr;
    }
  };

  return (
    <div className="flex flex-col h-full space-y-4 p-5">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold text-slate-350 uppercase tracking-wider flex items-center gap-2">
          <Database className="w-4 h-4 text-blue-500" />
          Simulation History
        </h2>
        <button
          onClick={onRefresh}
          disabled={loading}
          className="p-1.5 rounded-lg bg-slate-800 border border-slate-700 hover:bg-slate-700 hover:border-slate-650 text-slate-400 hover:text-white transition disabled:opacity-50"
          title="Refresh History"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} />
        </button>
      </div>

      {loading && runs.length === 0 ? (
        <div className="flex-1 flex flex-col items-center justify-center py-10 space-y-2 text-slate-500">
          <span className="w-6 h-6 rounded-full border-2 border-blue-500 border-t-transparent animate-spin" />
          <span className="text-xs">Loading history...</span>
        </div>
      ) : runs.length === 0 ? (
        <div className="flex-1 border border-dashed border-slate-800 rounded-xl p-8 text-center text-slate-500 flex flex-col items-center justify-center">
          <Database className="w-8 h-8 text-slate-700 mb-2" />
          <p className="text-sm">No saved runs yet.</p>
          <p className="text-xs text-slate-600 mt-1">
            Simulate a coverage layout to save it to history.
          </p>
        </div>
      ) : (
        <div className="flex-1 space-y-3 overflow-y-auto max-h-[calc(100vh-250px)] pr-1">
          {runs.map((run) => {
            const isGood = run.coverage_pct >= 85;
            return (
              <div
                key={run.id}
                onClick={() => onSelectRun(run.id)}
                className="group relative border border-slate-800 hover:border-blue-500/40 bg-slate-900/30 hover:bg-blue-900/5 rounded-xl p-4 cursor-pointer transition duration-200"
              >
                <div className="flex justify-between items-start mb-2">
                  <div className="pr-6">
                    <h4 className="font-semibold text-slate-200 text-sm group-hover:text-blue-400 transition truncate max-w-[200px]">
                      {run.project || "WiFrost Project"}
                    </h4>
                    <p className="text-xs text-slate-400 font-medium flex items-center gap-1.5 mt-0.5">
                      <MapPin className="w-3 h-3 text-slate-500" />
                      {run.bts_name}
                    </p>
                  </div>
                  <span
                    className={`text-[10px] font-bold px-2 py-0.5 rounded-full border ${
                      isGood
                        ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/20"
                        : "bg-amber-500/10 text-amber-400 border-amber-500/20"
                    }`}
                  >
                    {run.coverage_pct}%
                  </span>
                </div>

                <div className="grid grid-cols-2 gap-y-1.5 gap-x-2 text-[10px] text-slate-500 border-t border-slate-800/60 pt-2.5">
                  <div className="flex items-center gap-1">
                    <Radio className="w-3 h-3 text-slate-650" />
                    <span>{run.frequency} MHz</span>
                  </div>
                  <div className="text-right truncate">
                    {run.model === "terrain_aware" ? "Terrain-Aware" : "Flat Earth"}
                  </div>
                  <div className="flex items-center gap-1">
                    <Calendar className="w-3 h-3 text-slate-655" />
                    <span>{formatDate(run.created_at)}</span>
                  </div>
                  <div className="text-right capitalize">
                    {run.environment.replace("_", " ")}
                  </div>
                </div>

                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    onDeleteRun(run.id);
                  }}
                  className="absolute right-3 bottom-3 p-1.5 rounded-lg border border-transparent hover:border-red-900/30 hover:bg-red-500/10 text-slate-600 hover:text-red-400 opacity-0 group-hover:opacity-100 transition duration-150"
                  title="Delete Run"
                >
                  <Trash2 className="w-3.5 h-3.5" />
                </button>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
