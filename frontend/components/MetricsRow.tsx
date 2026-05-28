import React from "react";
import { Shield, Signal, CheckCircle2, HelpCircle } from "lucide-react";

interface ScenarioStats {
  coverage_pct: number;
  good_pct: number;
  avg_rssi: number;
}

interface MetricsRowProps {
  threeScenarios: {
    best: ScenarioStats;
    realistic: ScenarioStats;
    conservative: ScenarioStats;
  };
  activeScenarioName: "best" | "realistic" | "conservative";
}

export default function MetricsRow({ threeScenarios, activeScenarioName }: MetricsRowProps) {
  const getScenarioLabel = (key: string) => {
    switch (key) {
      case "best":
        return "Best Case (+5 dB Margin Off)";
      case "realistic":
        return "Realistic (Baseline)";
      case "conservative":
        return "Conservative (-5 dB Margin)";
      default:
        return key;
    }
  };

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
        const isActive = key === activeScenarioName;

        return (
          <div
            key={key}
            className={`p-5 rounded-xl border transition-all duration-300 relative flex flex-col justify-between ${getBorderColor(
              key
            )}`}
          >
            {isActive && (
              <span className="absolute top-3 right-3 text-xs bg-blue-600/20 border border-blue-500/30 text-blue-400 px-2 py-0.5 rounded-full font-medium">
                Active View
              </span>
            )}
            
            <div>
              <h4 className="text-sm font-semibold text-slate-400">
                {getScenarioLabel(key)}
              </h4>
              
              <div className="mt-4 space-y-4">
                {/* Coverage KPI */}
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2 text-slate-300">
                    <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                    <span className="text-sm">RF Coverage</span>
                  </div>
                  <span className="text-lg font-bold text-white">
                    {scenario.coverage_pct}%
                  </span>
                </div>

                {/* Good Signal KPI */}
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2 text-slate-300">
                    <Signal className="w-4 h-4 text-blue-400" />
                    <span className="text-sm">Good Signal (&gt;10dB Margin)</span>
                  </div>
                  <span className="text-lg font-bold text-white">
                    {scenario.good_pct}%
                  </span>
                </div>

                {/* Avg RSSI KPI */}
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2 text-slate-300">
                    <Shield className="w-4 h-4 text-indigo-400" />
                    <span className="text-sm">Average RSSI</span>
                  </div>
                  <span className="text-lg font-bold text-white">
                    {scenario.avg_rssi} dBm
                  </span>
                </div>
              </div>
            </div>

            {/* Quick status bar */}
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
