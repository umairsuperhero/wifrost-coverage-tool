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
        className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-blue-400 bg-blue-500/10 hover:bg-blue-500/20 border border-blue-500/20 rounded-full transition"
      >
        <Gift className="w-3.5 h-3.5" />
        <span>What's New</span>
      </button>

      {isOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm">
          <div className="relative w-full max-w-2xl bg-slate-900 border border-slate-800 rounded-2xl shadow-2xl flex flex-col max-h-[85vh]">
            {/* Header */}
            <div className="flex items-start justify-between px-6 py-4 border-b border-slate-800">
              <div>
                <h2 className="text-xl font-bold text-white flex items-center gap-2">
                  <Gift className="w-5 h-5 text-blue-400" />
                  What's New in WiFrost TVWS
                </h2>
                <p className="text-xs text-slate-400 mt-1.5 max-w-md leading-relaxed">
                  Note: This is an open source hobby project for internal use by WiFrost and its customers, not a commercial product.
                </p>
              </div>
              <button 
                onClick={() => setIsOpen(false)}
                className="p-2 -mr-2 text-slate-400 hover:text-white hover:bg-slate-800 rounded-full transition"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Timeline Body */}
            <div className="flex-1 overflow-y-auto p-6 space-y-8">
              <div className="relative border-l border-slate-700 ml-3 space-y-8">
                {releases.map((release, i) => (
                  <div key={i} className="relative pl-6">
                    {/* Dot */}
                    <div className="absolute -left-1.5 top-1 w-3 h-3 rounded-full bg-blue-500 ring-4 ring-slate-900"></div>
                    
                    <div className="mb-1 flex items-center gap-2">
                      <span className="text-xs font-semibold text-blue-400">{release.date}</span>
                    </div>
                    <h3 className="text-base font-bold text-white mb-2">{release.title}</h3>
                    <ul className="space-y-1.5">
                      {release.changes.map((change, j) => {
                        const splitIdx = change.indexOf(": ");
                        if (splitIdx === -1) {
                          return <li key={j} className="text-sm text-slate-300 leading-relaxed"><span className="text-slate-100">{change}</span></li>;
                        }
                        const boldPart = change.substring(0, splitIdx);
                        const restPart = change.substring(splitIdx + 2);
                        return (
                          <li key={j} className="text-sm text-slate-300 leading-relaxed">
                            <strong className="text-slate-100">{boldPart}:</strong> {restPart}
                          </li>
                        );
                      })}
                    </ul>
                  </div>
                ))}
              </div>
            </div>

            {/* Footer */}
            <div className="px-6 py-4 border-t border-slate-800 bg-slate-900/50 rounded-b-2xl flex justify-between items-center">
              <a 
                href="https://github.com/umairsuperhero/wifrost-coverage-tool/commits/main" 
                target="_blank" 
                rel="noreferrer"
                className="text-xs text-slate-400 hover:text-blue-400 flex items-center gap-1 transition"
              >
                View full commit history <ExternalLink className="w-3 h-3" />
              </a>
              <button 
                onClick={() => setIsOpen(false)}
                className="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white text-sm font-medium rounded-lg transition"
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
