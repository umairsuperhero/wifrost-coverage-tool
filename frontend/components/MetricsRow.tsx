import React from "react";
import { Signal, CheckCircle2, ShieldCheck } from "lucide-react";
import { cn } from "../lib/utils";

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
  const activeScenario = threeScenarios[activeScenarioName];
  const activeMeta = SCENARIO_META[activeScenarioName];

  return (
    <div className="space-y-3">
      {/* Scenario Segmented Toggler */}
      <div className="flex glass-panel rounded-xl p-0.5 gap-0.5">
        {(["best", "realistic", "conservative"] as const).map((key) => {
          const isActive = key === activeScenarioName;
          return (
            <button
              key={key}
              type="button"
              onClick={() => onScenarioChange?.(key)}
              className={`flex-1 py-2 text-xs font-semibold rounded-lg transition-all duration-300 cursor-pointer text-center ${
                isActive
                  ? "bg-white/10 text-white shadow-sm"
                  : "text-white/40 hover:text-white/70"
              }`}
            >
              {SCENARIO_META[key].label}
            </button>
          );
        })}
      </div>

      {/* Active Scenario Card */}
      <div className="glass-panel rounded-2xl p-4 space-y-3">
        <div className="flex justify-between items-start">
          <div>
            <h4 className="text-sm font-bold text-white flex items-center gap-1.5">
              {activeMeta.label} View
              {typeof activeScenario.margin_db === "number" && (
                <span className="text-[10px] text-slate-500 font-medium tracking-normal">
                  ({activeScenario.margin_db.toFixed(0)} dB margin)
                </span>
              )}
            </h4>
            <p className="text-xs text-slate-400 mt-0.5">{activeMeta.sub}</p>
          </div>
          <span className="text-3xl font-extrabold text-white tracking-tight font-mono">
            {activeScenario.coverage_pct}%
          </span>
        </div>

        {/* Modern progress bar indicator */}
        <div className="w-full bg-white/5 rounded-full h-2 overflow-hidden border border-white/5">
          <div
            className={`h-full rounded-full transition-all duration-500 ${
              activeScenario.coverage_pct >= 85
                ? "bg-gradient-to-r from-emerald-500 to-teal-400 shadow-[0_0_8px_rgba(52,211,153,0.5)]"
                : activeScenario.coverage_pct >= 60
                ? "bg-gradient-to-r from-amber-500 to-yellow-400 shadow-[0_0_8px_rgba(245,158,11,0.5)]"
                : "bg-gradient-to-r from-red-500 to-rose-400 shadow-[0_0_8px_rgba(239,68,68,0.5)]"
            }`}
            style={{ width: `${activeScenario.coverage_pct}%` }}
          />
        </div>

        {/* Detailed stats list */}
        <div className="space-y-3 pt-2 border-t border-white/5">
          <div className="flex items-center justify-between text-xs">
            <div className="flex items-center gap-2 text-slate-300">
              <CheckCircle2 className="w-4 h-4 text-emerald-400" />
              <span>Reliable Area Coverage</span>
            </div>
            <span className="font-semibold text-white font-mono">{activeScenario.coverage_pct}%</span>
          </div>

          <div className="flex items-center justify-between text-xs">
            <div className="flex items-center gap-2 text-slate-300">
              <Signal className="w-4 h-4 text-blue-400" />
              <span>Strong Signal Coverage</span>
            </div>
            <span className="font-semibold text-white font-mono">{activeScenario.good_pct}%</span>
          </div>

          <div className="flex items-center justify-between text-xs">
            <div className="flex items-center gap-2 text-slate-300">
              <ShieldCheck className="w-4 h-4 text-indigo-400" />
              <span>Safety Link Margin</span>
            </div>
            <span className="font-semibold text-white font-mono">
              {typeof activeScenario.margin_db === "number" ? `${activeScenario.margin_db.toFixed(0)} dB` : "—"}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
