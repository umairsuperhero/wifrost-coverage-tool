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
    <div className="bg-slate-900/60 rounded-xl border border-slate-800 p-5">
      <p className="text-sm font-semibold text-white mb-3">⚡ Link Budget</p>

      <div className="flex justify-between text-sm py-1">
        <span className="text-slate-400">TX Power</span>
        <span className="text-slate-100 tabular-nums">{fmtSigned(txPowerDbm, "dBm")}</span>
      </div>
      <div className="flex justify-between text-sm py-1">
        <span className="text-slate-400">BTS Antenna Gain</span>
        <span className="text-slate-100 tabular-nums">{fmtSigned(antennaGainDbi, "dBi")}</span>
      </div>
      <div className="flex justify-between text-sm py-1">
        <span className="text-slate-400">Cable Loss</span>
        <span className="text-slate-100 tabular-nums">{fmtLoss(cableLossDb, "dB")}</span>
      </div>

      <div className="border-t border-slate-700 my-1" />

      <div className="flex justify-between text-sm py-1">
        <span className="text-blue-400 font-bold">EIRP</span>
        <span className="text-blue-400 font-bold tabular-nums">{fmtSigned(eirpDbm, "dBm")}</span>
      </div>

      <div className="py-1" />

      <div className="flex justify-between text-sm py-1">
        <span className="text-slate-400">Rx Sensitivity</span>
        <span className="text-slate-100 tabular-nums">{fmtSigned(cpeSensitivityDbm, "dBm")}</span>
      </div>
      <div className="flex justify-between text-sm py-1">
        <span className="text-slate-400">Rx Antenna Gain</span>
        <span className="text-slate-100 tabular-nums">{fmtSigned(cpeGainDbi, "dBi")}</span>
      </div>
      <div className="flex justify-between text-sm py-1">
        <span className="text-slate-400">Rx Cable Loss</span>
        <span className="text-slate-100 tabular-nums">{fmtLoss(cpeCableLossDb, "dB")}</span>
      </div>
      <div className="flex justify-between text-sm py-1">
        <span className="text-slate-400">System Margin</span>
        <span className="text-slate-100 tabular-nums">{fmtLoss(systemMarginDb, "dB")}</span>
      </div>

      <div className="border-t border-slate-700 my-1" />

      <div className="flex justify-between text-sm py-1">
        <span className="text-white font-bold">Max Allowed PL</span>
        <span className="text-white font-bold tabular-nums">{fmtUnsigned(maxAllowedPathLoss, "dB")}</span>
      </div>

      <div className="py-1" />

      <div className="flex justify-between text-sm py-1">
        <span className="text-slate-400">Max Range (sim)</span>
        {maxRangeKm !== null ? (
          <span className="text-emerald-400 font-semibold tabular-nums">{maxRangeKm.toFixed(1)} km</span>
        ) : (
          <span className="text-slate-500 tabular-nums">—</span>
        )}
      </div>
    </div>
  );
}
