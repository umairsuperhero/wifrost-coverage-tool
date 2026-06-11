interface LinkBudgetProps {
  txPowerDbm: number;
  antennaGainDbi: number;
  cableLossDb: number;
  cpeGainDbi: number;
  cpeCableLossDb: number;
  cpeSensitivityDbm: number;
  systemMarginDb: number;
  frequencyMhz: number;
  maxRangeKm: number | null;
}

export default function LinkBudget({
  txPowerDbm,
  antennaGainDbi,
  cableLossDb,
  cpeGainDbi,
  cpeCableLossDb,
  cpeSensitivityDbm,
  systemMarginDb,
  maxRangeKm,
}: LinkBudgetProps) {
  const eirpDbm = txPowerDbm + antennaGainDbi - cableLossDb;
  const maxAllowedPathLoss = eirpDbm - cpeSensitivityDbm + cpeGainDbi - cpeCableLossDb - systemMarginDb;

  const fmtSigned = (v: number, unit: string) => {
    const sign = v >= 0 ? "+" : "−";
    return `${sign}${Math.abs(v).toFixed(1)} ${unit}`;
  };
  const fmtLoss = (v: number, unit: string) => `−${Math.abs(v).toFixed(1)} ${unit}`;
  const fmtUnsigned = (v: number, unit: string) => `${v.toFixed(1)} ${unit}`;

  return (
    <details className="group border border-white/10 rounded-2xl bg-white/[0.02] overflow-hidden transition-all duration-200">
      <summary className="px-4 py-3 text-xs font-bold text-white uppercase tracking-wider cursor-pointer flex justify-between items-center hover:bg-white/5 transition duration-200">
        <span className="flex items-center gap-2">
          <span className="text-blue-400">⚡</span> Link Budget
        </span>
        <span className="group-open:rotate-90 transition-transform duration-200 text-slate-400">▶</span>
      </summary>
      <div className="p-4 border-t border-white/5 space-y-2.5 bg-black/25">
        <div className="flex justify-between text-xs">
          <span className="text-slate-400">TX Power</span>
          <span className="text-white/95 font-medium tabular-nums">{fmtSigned(txPowerDbm, "dBm")}</span>
        </div>
        <div className="flex justify-between text-xs">
          <span className="text-slate-400">BTS Antenna Gain</span>
          <span className="text-white/95 font-medium tabular-nums">{fmtSigned(antennaGainDbi, "dBi")}</span>
        </div>
        <div className="flex justify-between text-xs">
          <span className="text-slate-400">Cable Loss</span>
          <span className="text-white/95 font-medium tabular-nums">{fmtLoss(cableLossDb, "dB")}</span>
        </div>

        <div className="border-t border-white/5 my-2" />

        <div className="flex justify-between text-xs font-bold">
          <span className="text-blue-400">EIRP</span>
          <span className="text-blue-400 tabular-nums">{fmtSigned(eirpDbm, "dBm")}</span>
        </div>

        <div className="border-t border-white/5 my-2" />

        <div className="flex justify-between text-xs">
          <span className="text-slate-400">Rx Sensitivity</span>
          <span className="text-white/95 font-medium tabular-nums">{fmtSigned(cpeSensitivityDbm, "dBm")}</span>
        </div>
        <div className="flex justify-between text-xs">
          <span className="text-slate-400">Rx Antenna Gain</span>
          <span className="text-white/95 font-medium tabular-nums">{fmtSigned(cpeGainDbi, "dBi")}</span>
        </div>
        <div className="flex justify-between text-xs">
          <span className="text-slate-400">Rx Cable Loss</span>
          <span className="text-white/95 font-medium tabular-nums">{fmtLoss(cpeCableLossDb, "dB")}</span>
        </div>
        <div className="flex justify-between text-xs">
          <span className="text-slate-400">System Margin</span>
          <span className="text-white/95 font-medium tabular-nums">{fmtLoss(systemMarginDb, "dB")}</span>
        </div>

        <div className="border-t border-white/5 my-2" />

        <div className="flex justify-between text-xs font-bold">
          <span className="text-white">Max Allowed PL</span>
          <span className="text-white tabular-nums">{fmtUnsigned(maxAllowedPathLoss, "dB")}</span>
        </div>

        <div className="flex justify-between text-xs pt-1">
          <span className="text-slate-400">Max Range (sim)</span>
          {maxRangeKm !== null ? (
            <span className="text-emerald-400 font-bold tabular-nums">{maxRangeKm.toFixed(1)} km</span>
          ) : (
            <span className="text-slate-500 tabular-nums">—</span>
          )}
        </div>
      </div>
    </details>
  );
}
