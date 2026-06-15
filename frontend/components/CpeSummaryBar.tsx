import { CpeResult, cpeTier } from "./CpeTable";
import { cn } from "../lib/utils";

interface CpeSummaryBarProps {
  cpeResults: CpeResult[];
}

export default function CpeSummaryBar({ cpeResults }: CpeSummaryBarProps) {
  // Tier from the backend: 2-3 = reliable (green), 1 = marginal (amber), 0 = no link (red).
  const excellent = cpeResults.filter(c => cpeTier(c) >= 2).length;
  const marginal  = cpeResults.filter(c => cpeTier(c) === 1).length;
  const failed    = cpeResults.filter(c => cpeTier(c) === 0).length;
  const total     = cpeResults.length;
  // Reliable = clears sensitivity + system margin (tier >= 1).
  const reliable  = excellent + marginal;
  const pct       = total > 0 ? Math.round((reliable / total) * 100) : 0;

  return (
    <div className="glass-panel rounded-xl px-4 py-2">
      <div className="flex items-center gap-4 flex-wrap">
        <span className="text-sm font-medium text-white/90">CPE Coverage</span>
        <div className="flex items-center gap-3 flex-wrap">
          <span className="text-[11px] uppercase tracking-wider text-white/60">
            <span className="w-1.5 h-1.5 rounded-full inline-block mr-1.5 bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.8)]" />
            {excellent} Reliable
          </span>
          <span className="text-[11px] uppercase tracking-wider text-white/60">
            <span className="w-1.5 h-1.5 rounded-full inline-block mr-1.5 bg-amber-400 shadow-[0_0_8px_rgba(251,191,36,0.8)]" />
            {marginal} Marginal
          </span>
          <span className="text-[11px] uppercase tracking-wider text-white/60">
            <span className="w-1.5 h-1.5 rounded-full inline-block mr-1.5 bg-red-400 shadow-[0_0_8px_rgba(248,113,113,0.8)]" />
            {failed} No Signal
          </span>
        </div>
      </div>
      <div className="flex items-center gap-3 mt-2.5">
        <div className="flex-1 flex rounded-full overflow-hidden h-1.5 bg-white/5">
          <div className="bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.8)]" style={{ width: `${(excellent / total) * 100}%` }} />
          <div className="bg-amber-400 shadow-[0_0_8px_rgba(251,191,36,0.8)]"   style={{ width: `${(marginal / total) * 100}%` }} />
          <div className="bg-red-400 shadow-[0_0_8px_rgba(248,113,113,0.8)]"     style={{ width: `${(failed / total) * 100}%` }} />
        </div>
        <span className="text-[11px] uppercase tracking-wider font-semibold text-white/80 whitespace-nowrap">{pct}% Reliable</span>
      </div>
    </div>
  );
}
