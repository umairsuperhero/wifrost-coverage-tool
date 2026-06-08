"use client";

import React, { useState } from "react";
import { Gift, X, ExternalLink } from "lucide-react";

export default function WhatsNewButton() {
  const [isOpen, setIsOpen] = useState(false);

  const releases = [
    {
      date: "Jun 8, 2026",
      title: "Enhancements & 3D Propagation",
      changes: [
        "Physics Engine: Implemented 3D mechanical downtilt (MDT) pattern for precise vertical antenna modeling.",
        "UI & UX: Hid the RF Deployment Profile dropdown in Advanced mode. Refactored 'RF Presets' to 'Deployment Profiles'.",
        "Honesty Harness: Added automated hooks and verification protocols for AI code generation.",
        "Reporting: Added a comprehensive Propagation Methodology page to the PDF report exports."
      ]
    },
    {
      date: "Jun 6, 2026",
      title: "Terrain-Aware Modeling & P2MP",
      changes: [
        "Propagation: Added bandwidth-aware sensitivity calculations and auto-environment detection utilizing ESA WorldCover.",
        "Features: Introduced manual CPE placement for Point-to-Multipoint (P2MP) analysis directly on the map.",
        "Infrastructure: Pinned Cloud Run memory to 2 GiB to resolve OOM errors. Fixed land-cover fetch CA certificates."
      ]
    },
    {
      date: "Jun 5, 2026",
      title: "Full Layout Polish & Realism",
      changes: [
        "UI Overhaul: Added a new run-summary bar at the bottom, improved scenario cards to give honest estimations.",
        "Physics Engine: Added Earth-curvature adjustments and unified the link-budget threshold math."
      ]
    },
    {
      date: "Jun 1, 2026",
      title: "Cloud Run Migration & V2 Frontend",
      changes: [
        "Architecture: Officially migrated backend APIs from Render to Google Cloud Run.",
        "Features: Added Simple vs. Advanced mode toggles, Link Budget panels, and CPE summary bars."
      ]
    },
    {
      date: "May 30, 2026",
      title: "Sector Antennas & Terrain Heatmaps",
      changes: [
        "Features: Introduced sector wedge map overlays, PDF terrain profiles, and vectorised heatmaps."
      ]
    }
  ];

  return (
    <>
      <button 
        onClick={() => setIsOpen(true)}
        className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-white/70 bg-white/5 hover:bg-white/10 hover:text-white border border-white/10 rounded-full transition duration-300"
      >
        <Gift className="w-3.5 h-3.5" />
        <span>What's New</span>
      </button>

      {isOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40 backdrop-blur-sm animate-in fade-in duration-300">
          <div className="relative w-full max-w-2xl bg-black/60 backdrop-blur-2xl border border-white/10 rounded-2xl shadow-2xl flex flex-col max-h-[85vh] animate-in zoom-in-95 duration-300">
            {/* Header */}
            <div className="flex items-start justify-between px-6 py-5 border-b border-white/5">
              <div>
                <h2 className="text-xl font-medium tracking-tight text-white flex items-center gap-2.5">
                  <Gift className="w-5 h-5 text-blue-400" />
                  What's New in WiFrost TVWS
                </h2>
                <p className="text-xs text-white/40 mt-1.5 max-w-md leading-relaxed font-medium">
                  Note: This is an open source hobby project for internal use by WiFrost and its customers, not a commercial product.
                </p>
              </div>
              <button 
                onClick={() => setIsOpen(false)}
                className="p-2 -mr-2 text-white/40 hover:text-white hover:bg-white/5 rounded-full transition duration-200"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Timeline Body */}
            <div className="flex-1 overflow-y-auto p-6 space-y-8 custom-scrollbar">
              <div className="relative border-l border-white/10 ml-3 space-y-10">
                {releases.map((release, i) => (
                  <div key={i} className="relative pl-7">
                    {/* Glowing Dot */}
                    <div className="absolute -left-[5px] top-1.5 w-2.5 h-2.5 rounded-full bg-blue-500 shadow-[0_0_8px_rgba(59,130,246,0.8)]"></div>
                    
                    <div className="mb-1.5 flex items-center gap-2">
                      <span className="text-[11px] uppercase tracking-widest font-semibold text-blue-400">{release.date}</span>
                    </div>
                    <h3 className="text-base font-medium text-white/90 mb-3">{release.title}</h3>
                    <ul className="space-y-2.5">
                      {release.changes.map((change, j) => {
                        const splitIdx = change.indexOf(": ");
                        if (splitIdx === -1) {
                          return <li key={j} className="text-[13px] text-white/60 leading-relaxed"><span className="text-white/80">{change}</span></li>;
                        }
                        const boldPart = change.substring(0, splitIdx);
                        const restPart = change.substring(splitIdx + 2);
                        return (
                          <li key={j} className="text-[13px] text-white/60 leading-relaxed">
                            <strong className="text-white/90 font-medium">{boldPart}:</strong> {restPart}
                          </li>
                        );
                      })}
                    </ul>
                  </div>
                ))}
              </div>
            </div>

            {/* Footer */}
            <div className="px-6 py-4 border-t border-white/5 bg-black/20 rounded-b-2xl flex justify-between items-center">
              <a 
                href="https://github.com/umairsuperhero/wifrost-coverage-tool/commits/main" 
                target="_blank" 
                rel="noreferrer"
                className="text-xs text-white/40 hover:text-white flex items-center gap-1 transition duration-200"
              >
                View full commit history <ExternalLink className="w-3 h-3" />
              </a>
              <button 
                onClick={() => setIsOpen(false)}
                className="px-5 py-2 bg-white/10 hover:bg-white/20 text-white text-sm font-medium rounded-full transition duration-300 backdrop-blur-md border border-white/5"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
