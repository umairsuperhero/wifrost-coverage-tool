import React from "react";
import { Wifi } from "lucide-react";
import WhatsNewButton from "./WhatsNewButton";

interface LayoutProps {
  children: React.ReactNode;
}

export default function Layout({ children }: LayoutProps) {
  return (
    <div className="flex flex-col h-screen overflow-hidden bg-black text-white relative">
      {/* Top Dynamic Island */}
      <header className="absolute top-4 left-1/2 -translate-x-1/2 flex items-center justify-between px-4 py-2 bg-slate-950/85 backdrop-blur-3xl border border-white/10 rounded-full shadow-[0_8px_32px_rgba(0,0,0,0.4)] z-50 pointer-events-auto gap-6 sm:gap-10">
        <div className="flex items-center space-x-3">
          <div className="p-1.5 bg-blue-500/20 rounded-full text-blue-400 border border-blue-500/30 shadow-[0_0_15px_rgba(59,130,246,0.5)]">
            <Wifi className="w-5 h-5 animate-pulse" />
          </div>
          <div>
            <h1 className="text-[15px] font-bold text-white tracking-wide leading-tight">Snowball</h1>
            <span className="text-[9px] uppercase tracking-[0.2em] font-semibold text-blue-400/80 bg-blue-500/10 px-1.5 py-0.5 rounded ml-1">TVWS</span>
          </div>
        </div>

        {/* Action Center & Profile */}
        <div className="flex items-center space-x-4">
          <WhatsNewButton />
          
          <div className="h-6 w-[1px] bg-white/10" />

          <div className="flex items-center space-x-2 text-right">
            <div className="hidden sm:block text-left mr-1">
              <p className="text-[10px] uppercase tracking-wider text-white/40 font-semibold leading-none mb-0.5">Sales Engineer</p>
              <p className="text-xs font-medium text-white/90 leading-none">Marcelo</p>
            </div>
            <div className="w-8 h-8 rounded-full bg-gradient-to-br from-blue-500/40 to-purple-500/40 border border-white/20 flex items-center justify-center text-white text-xs font-bold shadow-inner">
              M
            </div>
          </div>
        </div>
      </header>

      {/* Main Container */}
      <div className="flex-1 w-full h-full relative">
        {children}
      </div>
    </div>
  );
}
