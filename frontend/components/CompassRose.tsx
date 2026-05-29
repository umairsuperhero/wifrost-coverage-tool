"use client";

import React, { useRef, useState, useEffect, useCallback } from "react";

const SECTOR_COLORS = ["#3B82F6", "#22C55E", "#F59E0B"];

interface SectorDef {
  azimuth: number;
  color: string;
}

interface CompassRoseProps {
  sectors: SectorDef[];
  hpbw: number;
  size?: number;
  onAzimuthChange?: (sectorIndex: number, azimuth: number) => void;
}

// Convert compass bearing (0=N, CW) to SVG radians (0=E, CW in screen coords)
const toRad = (compassDeg: number) => ((compassDeg - 90) * Math.PI) / 180;

// Round to 2 dp so SSR and client emit identical attribute strings (prevents hydration mismatch)
const r2 = (n: number) => Math.round(n * 100) / 100;

function wedgePath(cx: number, cy: number, r: number, azimuth: number, hpbw: number): string {
  const start = toRad(azimuth - hpbw / 2);
  const end = toRad(azimuth + hpbw / 2);
  const x1 = cx + r * Math.cos(start);
  const y1 = cy + r * Math.sin(start);
  const x2 = cx + r * Math.cos(end);
  const y2 = cy + r * Math.sin(end);
  const large = hpbw > 180 ? 1 : 0;
  return `M ${cx} ${cy} L ${x1.toFixed(2)} ${y1.toFixed(2)} A ${r} ${r} 0 ${large} 1 ${x2.toFixed(2)} ${y2.toFixed(2)} Z`;
}

function coverageSummary(azimuths: number[], hpbw: number): { text: string; color: string } {
  const covered = new Array(360).fill(false);
  for (const az of azimuths) {
    for (let d = -hpbw / 2; d <= hpbw / 2; d++) {
      covered[Math.round(((az + d) % 360 + 360) % 360)] = true;
    }
  }
  const coveredDeg = covered.filter(Boolean).length;
  const uncovered = 360 - coveredDeg;
  const n = azimuths.length;

  if (uncovered <= 5)
    return { text: "✓ Full 360° coverage with overlap", color: "#22C55E" };
  if (n === 1)
    return { text: `Sector coverage: ${coveredDeg}° arc · ${uncovered}° uncovered`, color: "#94A3B8" };
  if (uncovered > 20)
    return { text: `⚠ Gaps in coverage — ${uncovered}° uncovered`, color: "#F59E0B" };
  return { text: `Combined coverage: ${coveredDeg}° arc`, color: "#94A3B8" };
}

export default function CompassRose({
  sectors,
  hpbw,
  size = 140,
  onAzimuthChange,
}: CompassRoseProps) {
  const cx = size / 2;
  const cy = size / 2;
  const outerR = size * 0.44;
  const wedgeR = size * 0.41;
  const tickOuter = size * 0.43;
  const tickInner = size * 0.38;

  const svgRef = useRef<SVGSVGElement>(null);
  const [dragging, setDragging] = useState<number | null>(null);

  const handleMouseMove = useCallback(
    (e: MouseEvent) => {
      if (dragging === null || !svgRef.current) return;
      const rect = svgRef.current.getBoundingClientRect();
      const dx = e.clientX - (rect.left + rect.width / 2);
      const dy = e.clientY - (rect.top + rect.height / 2);
      const angleDeg = (Math.atan2(dy, dx) * 180) / Math.PI;
      // SVG 0°=East → compass: add 90°
      const bearing = ((angleDeg + 90) % 360 + 360) % 360;
      const snapped = Math.round(bearing / 5) * 5 % 360;
      onAzimuthChange?.(dragging, snapped);
    },
    [dragging, onAzimuthChange]
  );

  const handleMouseUp = useCallback(() => setDragging(null), []);

  useEffect(() => {
    if (dragging === null) return;
    window.addEventListener("mousemove", handleMouseMove);
    window.addEventListener("mouseup", handleMouseUp);
    return () => {
      window.removeEventListener("mousemove", handleMouseMove);
      window.removeEventListener("mouseup", handleMouseUp);
    };
  }, [dragging, handleMouseMove, handleMouseUp]);

  const summary = coverageSummary(sectors.map((s) => s.azimuth), hpbw);
  const interactive = !!onAzimuthChange;

  // Cardinal labels
  const cardinals = [
    { label: "N", deg: 0 },
    { label: "E", deg: 90 },
    { label: "S", deg: 180 },
    { label: "W", deg: 270 },
  ];

  return (
    <div className="flex flex-col items-center gap-1">
      <svg
        ref={svgRef}
        width={size}
        height={size}
        viewBox={`0 0 ${size} ${size}`}
        style={{ userSelect: "none" }}
      >
        {/* Background circle */}
        <circle cx={cx} cy={cy} r={outerR} fill="#0D1020" stroke="#1E2640" strokeWidth="1" />

        {/* Tick marks every 30° */}
        {Array.from({ length: 12 }, (_, i) => i * 30).map((deg) => {
          const r1 = deg % 90 === 0 ? tickInner - 3 : tickInner;
          const r2 = tickOuter;
          const rad = toRad(deg);
          return (
            <line
              key={deg}
              x1={r2(cx + r1 * Math.cos(rad))}
              y1={r2(cy + r1 * Math.sin(rad))}
              x2={r2(cx + tickOuter * Math.cos(rad))}
              y2={r2(cy + tickOuter * Math.sin(rad))}
              stroke={deg % 90 === 0 ? "#2E3A50" : "#1E2640"}
              strokeWidth={deg % 90 === 0 ? 1 : 0.5}
            />
          );
        })}

        {/* Cardinal degree numbers */}
        {[{ deg: 0, lbl: "0°" }, { deg: 90, lbl: "90°" }, { deg: 180, lbl: "180°" }, { deg: 270, lbl: "270°" }].map(
          ({ deg, lbl }) => {
            const r = tickInner - 10;
            const rad = toRad(deg);
            return (
              <text
                key={deg}
                x={r2(cx + r * Math.cos(rad))}
                y={r2(cy + r * Math.sin(rad))}
                textAnchor="middle"
                dominantBaseline="central"
                fontSize="7"
                fill="#64748B"
              >
                {lbl}
              </text>
            );
          }
        )}

        {/* Sector wedges */}
        {sectors.map((sec, i) => {
          const path = wedgePath(cx, cy, wedgeR, sec.azimuth, hpbw);
          const labelRad = toRad(sec.azimuth);
          const labelR = wedgeR * 0.58;
          const lx = r2(cx + labelR * Math.cos(labelRad));
          const ly = r2(cy + labelR * Math.sin(labelRad));
          return (
            <g key={i}>
              <path
                d={path}
                fill={sec.color}
                fillOpacity={0.25}
                stroke={sec.color}
                strokeWidth={1.5}
                strokeOpacity={0.8}
                style={interactive ? { cursor: dragging === i ? "grabbing" : "grab" } : {}}
                onMouseDown={interactive ? (e) => { e.preventDefault(); setDragging(i); } : undefined}
              />
              <text
                x={lx}
                y={ly}
                textAnchor="middle"
                dominantBaseline="central"
                fontSize="8"
                fontWeight="600"
                fill={sec.color}
                style={{ pointerEvents: "none" }}
              >
                {String(sec.azimuth).padStart(3, "0")}°
              </text>
            </g>
          );
        })}

        {/* Cardinal direction labels */}
        {cardinals.map(({ label, deg }) => {
          const r = outerR + 9;
          const rad = toRad(deg);
          return (
            <text
              key={label}
              x={r2(cx + r * Math.cos(rad))}
              y={r2(cy + r * Math.sin(rad))}
              textAnchor="middle"
              dominantBaseline="central"
              fontSize="10"
              fontWeight="700"
              fill={label === "N" ? "#94A3B8" : "#475569"}
            >
              {label}
            </text>
          );
        })}

        {/* Centre dot */}
        <circle cx={cx} cy={cy} r={3} fill="#475569" />
      </svg>

      {/* Coverage summary */}
      <p className="text-[10px] text-center leading-tight px-1" style={{ color: summary.color }}>
        {summary.text}
      </p>
    </div>
  );
}
