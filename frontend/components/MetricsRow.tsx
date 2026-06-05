import React from "react";
import { Signal, CheckCircle2, ShieldCheck } from "lucide-react";

interface ScenarioStats {
  coverage_pct: number;
  good_pct: number;
  avg_rssi: number;
  margin_db?: number;
}

interface MetricsRowProps {
  threeScenarios: {
    best: ScenarioStats;
    realistic: ScenarioStats;
    conservative: ScenarioStats;
  };
  activeScenarioName: "best" | "realistic" | "conservative";
  onScenarioChange?: (scenario: "best" | "realistic" | "conservative") => void;
}

// Honest scenario framing: the three views are the SAME RSSI field judged at
// three reliability confidences. Only the margin (how much head-room we demand
// before calling a cell "covered") changes — so we surface the margin and the
// resulting reliable / strong area, NOT an "average RSSI" that perversely drops
// as coverage grows.
const SCENARIO_META = {
  best: {
    label: "Best Case",
    sub: "Optimistic — lower margin",
    accent: "emerald",
  },
  realistic: {
    label: "Realistic",
    sub: "Recommended baseline",
    accent: "blue",
  },
  conservative: {
    label: "Conservative",
    sub: "Worst case — higher margin",
    accent: "amber",
  },
} as const;

export default function MetricsRow({ threeScenarios, activeScenarioName, onScenarioChange }: MetricsRowProps) {
  const getBorderColor = (key: string) => {
    if (key === activeScenarioName) {
      return "border-blue-500 bg-blue-500/5 ring-1 ring-blue-500/30";
    }
    return "border-slate-800 bg-slate-900/40";
  };

  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
      {(["best", "realistic", "conservative"] as const).map((key) => {
        const scenario = threeScenarios[key];
        const meta = SCENARIO_META[key];
        const isActive = key === activeScenarioName;

        return (
          <div
            key={key}
            onClick={() => onScenarioChange?.(key)}
            className={`p-5 rounded-xl border transition-all duration-300 relative flex flex-col justify-between cursor-pointer ${getBorderColor(
              key
            )} ${!isActive ? "hover:border-slate-700 hover:bg-slate-900/60" : ""}`}
          >
            {isActive && (
              <span className="absolute top-3 right-3 text-xs bg-blue-600/20 border border-blue-500/30 text-blue-400 px-2 py-0.5 rounded-full font-medium">
                Active View
              </span>
            )}

            <div>
              <div className="flex items-baseline gap-2">
                <h4 className="text-sm font-semibold text-white">{meta.label}</h4>
                {typeof scenario.margin_db === "number" && (
                  <span className="text-xs text-slate-500">
                    {scenario.margin_db.toFixed(0)} dB margin
                  </span>
                )}
              </div>
              <p className="text-xs text-slate-500 mt-0.5">{meta.sub}</p>

              <div className="mt-4 space-y-4">
                {/* Reliable coverage */}
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2 text-slate-300">
                    <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                    <span className="text-sm">Reliable area</span>
                  </div>
                  <span className="text-lg font-bold text-white">
                    {scenario.coverage_pct}%
                  </span>
                </div>

                {/* Strong signal */}
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2 text-slate-300">
                    <Signal className="w-4 h-4 text-blue-400" />
                    <span className="text-sm">Strong signal</span>
                  </div>
                  <span className="text-lg font-bold text-white">
                    {scenario.good_pct}%
                  </span>
                </div>

                {/* Confidence margin */}
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2 text-slate-300">
                    <ShieldCheck className="w-4 h-4 text-indigo-400" />
                    <span className="text-sm">Link margin</span>
                  </div>
                  <span className="text-lg font-bold text-white">
                    {typeof scenario.margin_db === "number" ? `${scenario.margin_db.toFixed(0)} dB` : "—"}
                  </span>
                </div>
              </div>
            </div>

            {/* Quick status bar — reliable area */}
            <div className="w-full bg-slate-800 rounded-full h-1.5 mt-5 overflow-hidden">
              <div
                className={`h-full rounded-full transition-all duration-500 ${
                  scenario.coverage_pct >= 85
                    ? "bg-emerald-500"
                    : scenario.coverage_pct >= 60
                    ? "bg-amber-500"
                    : "bg-red-500"
                }`}
                style={{ width: `${scenario.coverage_pct}%` }}
              />
            </div>
          </div>
        );
      })}
    </div>
  );
}
