import React from "react";
import { Wifi, User, HelpCircle } from "lucide-react";

interface LayoutProps {
  children: React.ReactNode;
}

export default function Layout({ children }: LayoutProps) {
  return (
    <div className="flex flex-col h-screen overflow-hidden bg-[#0F1117]">
      {/* Top Header Bar */}
      <header className="flex items-center justify-between px-6 py-4 border-b border-slate-800 bg-slate-900/50 backdrop-blur-md z-10">
        <div className="flex items-center space-x-3">
          <div className="p-2 bg-blue-600 rounded-lg text-white">
            <Wifi className="w-6 h-6 animate-pulse" />
          </div>
          <div>
            <h1 className="text-xl font-bold tracking-tight text-white flex items-center gap-2">
              WiFrost <span className="text-blue-500 font-semibold text-sm px-2 py-0.5 bg-blue-500/10 border border-blue-500/20 rounded">TVWS RF Coverage</span>
            </h1>
            <p className="text-xs text-slate-400">TVWS Propagation Planning Tool</p>
          </div>
        </div>

        {/* Marcelo Profile Greeting */}
        <div className="flex items-center space-x-6">
          <div className="flex items-center space-x-3 text-right">
            <div>
              <p className="text-xs text-slate-400">Sales Engineer</p>
              <p className="text-sm font-semibold text-white">Welcome back, Marcelo</p>
            </div>
            <div className="w-10 h-10 rounded-full bg-blue-600/20 border border-blue-500/40 flex items-center justify-center text-blue-400 font-bold">
              M
            </div>
          </div>
        </div>
      </header>

      {/* Main Container */}
      <div className="flex flex-1 overflow-hidden">
        {children}
      </div>
    </div>
  );
}
