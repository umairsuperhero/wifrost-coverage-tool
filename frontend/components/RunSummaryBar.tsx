import React, { useEffect, useState } from "react";
import { Activity, Radio, Waves, Mountain, Trees, Gauge, ShieldCheck } from "lucide-react";
import { cn } from "../lib/utils";

interface RunSummaryBarProps {
  runCount: number;
  lastRunAt: Date | null;
  isLoading: boolean;
  projectName?: string;
  btsName?: string;
  frequencyMhz?: number;
  model?: string;
  environment?: string;
  eirpDbm?: number;
  systemMarginDb?: number;
  terrainLoaded?: boolean;
  landcoverLoaded?: boolean;
  environmentAuto?: boolean;
}

const MODEL_LABEL: Record<string, string> = {
  terrain_aware: "Terrain-aware",
  flat: "Flat-earth",
};

const ENV_LABEL: Record<string, string> = {
  open: "Open",
  open_water: "Open water",
  suburban: "Suburban",
  urban: "Urban",
  vegetation_light: "Light vegetation",
  vegetation_dense: "Dense vegetation",
  port_industrial: "Port / industrial",
};

function timeAgo(date: Date): string {
  const s = Math.floor((Date.now() - date.getTime()) / 1000);
  if (s < 5) return "just now";
  if (s < 60) return `${s}s ago`;
  const m = Math.floor(s / 60);
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  return `${h}h ago`;
}

function Chip({ icon, label, value }: { icon: React.ReactNode; label: string; value: string }) {
  return (
    <span className="inline-flex items-center gap-1.5 text-[11px] uppercase tracking-wider text-white/70 bg-white/5 border border-white/10 rounded-full px-3 py-1">
      <span className="text-blue-400/80">{icon}</span>
      <span className="text-white/40">{label}</span>
      <span className="font-medium tracking-normal normal-case text-white/90">{value}</span>
    </span>
  );
}

function DataChip({ label, on }: { label: string; on: boolean }) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 text-[11px] uppercase tracking-wider font-semibold rounded-full px-3 py-1 border transition-all ${
        on
          ? "text-emerald-400 bg-emerald-500/10 border-emerald-500/20 shadow-[0_0_8px_rgba(16,185,129,0.15)]"
          : "text-white/40 bg-white/5 border-white/10"
      }`}
      title={on ? `${label} data loaded for this run` : `${label} unavailable — using fallback assumption`}
    >
      <span className={`h-1.5 w-1.5 rounded-full ${on ? "bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.8)]" : "bg-white/20"}`} />
      {label} {on ? "on" : "off"}
    </span>
  );
}

export default function RunSummaryBar({
  runCount, lastRunAt, isLoading, projectName, btsName,
  frequencyMhz, model, environment, eirpDbm, systemMarginDb,
  terrainLoaded, landcoverLoaded, environmentAuto,
}: RunSummaryBarProps) {
  // Re-render every 15 s so the "x ago" label stays fresh.
  const [, setTick] = useState(0);
  useEffect(() => {
    const id = setInterval(() => setTick((t) => t + 1), 15000);
    return () => clearInterval(id);
  }, []);

  return (
    <div className="glass-panel rounded-2xl p-4 space-y-3">
      {/* Header Info */}
      <div className="flex items-center justify-between border-b border-white/5 pb-2">
        <div className="flex items-center gap-2">
          <span className="relative flex h-2 w-2">
            {isLoading && (
              <span className="absolute inline-flex h-full w-full rounded-full bg-amber-400 opacity-75 animate-ping" />
            )}
            <span className={`relative inline-flex rounded-full h-2 w-2 ${isLoading ? "bg-amber-400 shadow-[0_0_8px_rgba(251,191,36,0.8)]" : "bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.8)]"}`} />
          </span>
          <span className="text-xs font-semibold text-white/90">
            {isLoading ? "Running simulation…" : `Run #${runCount}`}
          </span>
          {!isLoading && lastRunAt && (
            <span className="text-[10px] text-white/40">({timeAgo(lastRunAt)})</span>
          )}
        </div>
        {projectName && (
          <span className="text-[10px] text-white/40 truncate max-w-[150px] font-medium uppercase tracking-wider">
            {projectName}
          </span>
        )}
      </div>

      {/* 2-Column Parameter Grid */}
      <div className="grid grid-cols-2 gap-x-4 gap-y-3">
        {btsName && (
          <div className="flex flex-col gap-0.5">
            <span className="text-[9px] uppercase tracking-widest font-semibold text-white/30">Active Tower</span>
            <span className="text-xs font-medium text-white/80 truncate">{btsName}</span>
          </div>
        )}
        {typeof frequencyMhz === "number" && (
          <div className="flex flex-col gap-0.5">
            <span className="text-[9px] uppercase tracking-widest font-semibold text-white/30">Frequency</span>
            <span className="text-xs font-medium text-white/80">{frequencyMhz.toFixed(0)} MHz</span>
          </div>
        )}
        {model && (
          <div className="flex flex-col gap-0.5">
            <span className="text-[9px] uppercase tracking-widest font-semibold text-white/30">Propagation Model</span>
            <span className="text-xs font-medium text-white/80">{MODEL_LABEL[model] ?? model}</span>
          </div>
        )}
        {environment && (
          <div className="flex flex-col gap-0.5">
            <span className="text-[9px] uppercase tracking-widest font-semibold text-white/30">Clutter environment</span>
            <span className="text-xs font-medium text-white/80 truncate">
              {ENV_LABEL[environment] ?? environment}
              {environmentAuto && <span className="text-[10px] text-slate-500 font-normal ml-1">(auto)</span>}
            </span>
          </div>
        )}
        {typeof eirpDbm === "number" && (
          <div className="flex flex-col gap-0.5">
            <span className="text-[9px] uppercase tracking-widest font-semibold text-white/30">BTS EIRP</span>
            <span className="text-xs font-medium text-white/80">{eirpDbm.toFixed(1)} dBm</span>
          </div>
        )}
        {typeof systemMarginDb === "number" && (
          <div className="flex flex-col gap-0.5">
            <span className="text-[9px] uppercase tracking-widest font-semibold text-white/30">Required Margin</span>
            <span className="text-xs font-medium text-white/80">{systemMarginDb.toFixed(0)} dB</span>
          </div>
        )}
      </div>

      {/* Data Status Indicators */}
      {(typeof terrainLoaded === "boolean" || typeof landcoverLoaded === "boolean") && (
        <div className="flex items-center justify-between border-t border-white/5 pt-2 mt-2">
          <span className="text-[9px] uppercase tracking-widest font-semibold text-white/30">Data layers</span>
          <div className="flex items-center gap-2">
            {typeof terrainLoaded === "boolean" && (
              <span
                className={`inline-flex items-center gap-1.5 text-[9px] uppercase tracking-wider font-semibold rounded-full px-2 py-0.5 border ${
                  terrainLoaded
                    ? "text-emerald-400 bg-emerald-500/10 border-emerald-500/20"
                    : "text-white/30 bg-white/5 border-white/10"
                }`}
                title={terrainLoaded ? "Real SRTM terrain data loaded" : "Flat terrain fallback"}
              >
                <span className={`h-1 w-1 rounded-full ${terrainLoaded ? "bg-emerald-400" : "bg-white/20"}`} />
                SRTM
              </span>
            )}
            {typeof landcoverLoaded === "boolean" && (
              <span
                className={`inline-flex items-center gap-1.5 text-[9px] uppercase tracking-wider font-semibold rounded-full px-2 py-0.5 border ${
                  landcoverLoaded
                    ? "text-emerald-400 bg-emerald-500/10 border-emerald-500/20"
                    : "text-white/30 bg-white/5 border-white/10"
                }`}
                title={landcoverLoaded ? "ESA land cover data loaded" : "No land cover data"}
              >
                <span className={`h-1 w-1 rounded-full ${landcoverLoaded ? "bg-emerald-400" : "bg-white/20"}`} />
                Landcover
              </span>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
