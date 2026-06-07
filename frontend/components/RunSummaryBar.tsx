import React, { useEffect, useState } from "react";
import { Activity, Radio, Waves, Mountain, Trees, Gauge, ShieldCheck } from "lucide-react";

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
    <span className="inline-flex items-center gap-1.5 text-xs text-slate-300 bg-slate-800/60 border border-slate-700/60 rounded-lg px-2.5 py-1">
      <span className="text-slate-400">{icon}</span>
      <span className="text-slate-500">{label}</span>
      <span className="font-semibold text-white">{value}</span>
    </span>
  );
}

function DataChip({ label, on }: { label: string; on: boolean }) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 text-xs rounded-lg px-2.5 py-1 border ${
        on
          ? "text-emerald-300 bg-emerald-500/10 border-emerald-500/30"
          : "text-slate-400 bg-slate-800/60 border-slate-700/60"
      }`}
      title={on ? `${label} data loaded for this run` : `${label} unavailable — using fallback assumption`}
    >
      <span className={`h-1.5 w-1.5 rounded-full ${on ? "bg-emerald-400" : "bg-slate-500"}`} />
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
    <div className="bg-slate-900/70 rounded-xl border border-slate-800 px-5 py-3">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div className="flex items-center gap-2">
          <span className={`relative flex h-2.5 w-2.5`}>
            {isLoading && (
              <span className="absolute inline-flex h-full w-full rounded-full bg-amber-400 opacity-75 animate-ping" />
            )}
            <span className={`relative inline-flex rounded-full h-2.5 w-2.5 ${isLoading ? "bg-amber-400" : "bg-emerald-400"}`} />
          </span>
          <span className="text-sm font-semibold text-white">
            {isLoading ? "Running simulation…" : `Run #${runCount}`}
          </span>
          {!isLoading && lastRunAt && (
            <span className="text-xs text-slate-500">· {timeAgo(lastRunAt)}</span>
          )}
          {projectName && (
            <span className="text-xs text-slate-400 truncate max-w-[180px]">· {projectName}</span>
          )}
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          {btsName && <Chip icon={<Radio className="w-3.5 h-3.5" />} label="BTS" value={btsName} />}
          {typeof frequencyMhz === "number" && (
            <Chip icon={<Waves className="w-3.5 h-3.5" />} label="Freq" value={`${frequencyMhz.toFixed(0)} MHz`} />
          )}
          {model && (
            <Chip
              icon={model === "flat" ? <Activity className="w-3.5 h-3.5" /> : <Mountain className="w-3.5 h-3.5" />}
              label="Model"
              value={MODEL_LABEL[model] ?? model}
            />
          )}
          {environment && (
            <Chip
              icon={<Trees className="w-3.5 h-3.5" />}
              label="Env"
              value={`${ENV_LABEL[environment] ?? environment}${environmentAuto ? " (auto)" : ""}`}
            />
          )}
          {typeof eirpDbm === "number" && (
            <Chip icon={<Gauge className="w-3.5 h-3.5" />} label="EIRP" value={`${eirpDbm.toFixed(1)} dBm`} />
          )}
          {typeof systemMarginDb === "number" && (
            <Chip icon={<ShieldCheck className="w-3.5 h-3.5" />} label="Margin" value={`${systemMarginDb.toFixed(0)} dB`} />
          )}
          {typeof terrainLoaded === "boolean" && <DataChip label="Terrain" on={terrainLoaded} />}
          {typeof landcoverLoaded === "boolean" && <DataChip label="Land cover" on={landcoverLoaded} />}
        </div>
      </div>
    </div>
  );
}
