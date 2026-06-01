import { CpeResult } from "./CpeTable";

interface CpeSummaryBarProps {
  cpeResults: CpeResult[];
}

export default function CpeSummaryBar({ cpeResults }: CpeSummaryBarProps) {
  const excellent = cpeResults.filter(c => c.margin_db >= 10).length;
  const marginal  = cpeResults.filter(c => c.margin_db >= 0 && c.margin_db < 10).length;
  const failed    = cpeResults.filter(c => c.margin_db < 0).length;
  const total     = cpeResults.length;
  const pct       = total > 0 ? Math.round((excellent / total) * 100) : 0;

  return (
    <div className="bg-slate-900/60 rounded-xl border border-slate-800 px-5 py-3">
      <div className="flex items-center gap-4 flex-wrap">
        <span className="text-sm font-semibold text-white">CPE Coverage</span>
        <div className="flex items-center gap-3 flex-wrap">
          <span className="text-xs text-slate-300">
            <span className="w-2 h-2 rounded-full inline-block mr-1 bg-emerald-500" />
            {excellent} Excellent
          </span>
          <span className="text-xs text-slate-300">
            <span className="w-2 h-2 rounded-full inline-block mr-1 bg-amber-500" />
            {marginal} Marginal
          </span>
          <span className="text-xs text-slate-300">
            <span className="w-2 h-2 rounded-full inline-block mr-1 bg-red-500" />
            {failed} No Signal
          </span>
        </div>
      </div>
      <div className="flex items-center gap-2 mt-2">
        <div className="flex-1 flex rounded-full overflow-hidden h-2">
          <div className="bg-emerald-500" style={{ width: `${(excellent / total) * 100}%` }} />
          <div className="bg-amber-500"   style={{ width: `${(marginal / total) * 100}%` }} />
          <div className="bg-red-500"     style={{ width: `${(failed / total) * 100}%` }} />
        </div>
        <span className="text-xs text-slate-300 whitespace-nowrap">{pct}% Excellent</span>
      </div>
    </div>
  );
}
