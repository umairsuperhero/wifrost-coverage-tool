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
      <header className="absolute top-4 left-1/2 -translate-x-1/2 flex items-center justify-between px-4 py-2 bg-white/5 backdrop-blur-3xl border border-white/10 rounded-full shadow-[0_8px_32px_rgba(0,0,0,0.4)] z-50 pointer-events-auto gap-6 sm:gap-10">
        <div className="flex items-center space-x-3">
          <div className="p-1.5 bg-blue-500/20 rounded-full text-blue-400 border border-blue-500/30 shadow-[0_0_15px_rgba(59,130,246,0.5)]">
            <Wifi className="w-5 h-5 animate-pulse" />
          </div>
          <div className="flex flex-col justify-center">
            <h1 className="text-sm font-semibold tracking-wide text-white flex items-center gap-2">
              WiFrost <span className="text-white/50 font-normal text-[10px] px-2 py-0.5 bg-white/5 border border-white/10 rounded-full">TVWS</span>
            </h1>
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
