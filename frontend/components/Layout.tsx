import React from "react";
import { Wifi } from "lucide-react";
import WhatsNewButton from "./WhatsNewButton";

interface LayoutProps {
  children: React.ReactNode;
}

export default function Layout({ children }: LayoutProps) {
  return (
    <div className="flex flex-col h-screen overflow-hidden bg-black text-white relative">
      {/* Top Header Bar */}
      <header className="absolute top-0 left-0 right-0 flex items-center justify-between px-6 py-4 border-b border-white/5 bg-black/40 backdrop-blur-2xl z-50">
        <div className="flex items-center space-x-3">
          <div className="p-2 bg-blue-600 rounded-lg text-white">
            <Wifi className="w-6 h-6 animate-pulse" />
          </div>
          <div>
            <h1 className="text-xl font-medium tracking-tight text-white flex items-center gap-2">
              WiFrost <span className="text-white/70 font-normal text-xs px-2 py-0.5 bg-white/5 border border-white/10 rounded-full">TVWS RF Coverage</span>
            </h1>
            <p className="text-[11px] uppercase tracking-widest font-semibold text-white/40 mt-0.5">TVWS Propagation Planning Tool</p>
          </div>
        </div>

        {/* Marcelo Profile Greeting & What's New */}
        <div className="flex items-center space-x-6">
          <WhatsNewButton />
          
          <div className="flex items-center space-x-3 text-right">
            <div>
              <p className="text-[10px] tracking-wider uppercase text-white/40 font-semibold">Sales Engineer</p>
              <p className="text-sm font-medium text-white/90">Welcome back, Marcelo</p>
            </div>
            <div className="w-9 h-9 rounded-full bg-white/5 border border-white/10 flex items-center justify-center text-white/80 font-medium">
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
