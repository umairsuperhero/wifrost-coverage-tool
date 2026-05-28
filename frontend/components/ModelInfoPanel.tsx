import React from "react";
import { Info, HelpCircle, HardDrive, Network } from "lucide-react";

interface ModelInfoPanelProps {
  modelType: string;
  frequencyMhz: number;
}

export default function ModelInfoPanel({ modelType, frequencyMhz }: ModelInfoPanelProps) {
  return (
    <div className="bg-slate-900/60 rounded-xl border border-slate-800 p-5 space-y-4">
      <div className="flex items-center gap-2 text-white border-b border-slate-800 pb-3">
        <Info className="w-5 h-5 text-blue-400" />
        <h3 className="font-semibold">TVWS Propagation Model Details</h3>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm text-slate-300">
        <div className="space-y-2">
          <div className="flex justify-between border-b border-slate-800/40 py-1">
            <span className="text-slate-400">Propagation Base</span>
            <span className="font-medium text-white">Modified Okumura-Hata</span>
          </div>
          <div className="flex justify-between border-b border-slate-800/40 py-1">
            <span className="text-slate-400">Terrain Processing</span>
            <span className="font-medium text-white">
              {modelType === "terrain_aware" ? "SRTM Elevation Aware (2D Profile)" : "Flat Terrain Assumption"}
            </span>
          </div>
          <div className="flex justify-between border-b border-slate-800/40 py-1">
            <span className="text-slate-400">Operating Frequency</span>
            <span className="font-medium text-white">{frequencyMhz} MHz</span>
          </div>
        </div>

        <div className="space-y-2">
          <div className="flex justify-between border-b border-slate-800/40 py-1">
            <span className="text-slate-400">SRTM Data Source</span>
            <span className="font-medium text-white">OpenTopography 30m Global</span>
          </div>
          <div className="flex justify-between border-b border-slate-800/40 py-1">
            <span className="text-slate-400">Diffraction Model</span>
            <span className="font-medium text-white">Deygout / Knife-Edge Method</span>
          </div>
          <div className="flex justify-between border-b border-slate-800/40 py-1">
            <span className="text-slate-400">Default Environment</span>
            <span className="font-medium text-white">Suburban (8 dB clutter loss)</span>
          </div>
        </div>
      </div>

      <div className="p-3 bg-slate-800/40 rounded-lg border border-slate-800/80 text-xs text-slate-400 flex items-start gap-2.5">
        <HelpCircle className="w-4 h-4 text-blue-400 flex-shrink-0 mt-0.5" />
        <p className="leading-relaxed">
          {modelType === "terrain_aware"
            ? "Terrain-Aware mode pulls real-time elevation profile slices between the BTS and each pixel. It uses Knife-Edge diffraction to calculate shadow loss from terrain blockages. Recommended for hilly or mountainous terrain."
            : "Flat mode assumes a line-of-sight path over flat ground, running the empirical Okumura-Hata equations. Useful for quick estimations or flat coastal areas."}
        </p>
      </div>
    </div>
  );
}
