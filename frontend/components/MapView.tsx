"use client";

import dynamic from "next/dynamic";
import React from "react";

// Load MapInner dynamically with SSR disabled to prevent Leaflet window reference crashes during build
const MapInner = dynamic(() => import("./MapInner"), {
  ssr: false,
  loading: () => (
    <div className="w-full h-full bg-[#0F1117] flex flex-col items-center justify-center text-slate-400">
      <div className="w-8 h-8 rounded-full border-2 border-blue-500 border-t-transparent animate-spin mb-2" />
      <p className="text-sm">Initializing Leaflet maps...</p>
    </div>
  ),
});

interface MapViewProps {
  sites: any[];
  polygons: any[];
  lines: any[];
  coverageGeojson: any;
  cpeResults: any[];
  selectedBtsIndex: number;
  onSelectBts: (index: number) => void;
  selectedCpeName: string | null;
  onSelectCpe: (cpe: any) => void;
}

export default function MapView(props: MapViewProps) {
  return <MapInner {...props} />;
}
