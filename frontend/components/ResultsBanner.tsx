import React, { useState } from "react";
import { CheckCircle2, AlertTriangle, FileText, Loader2 } from "lucide-react";
import axios from "axios";
import { cn } from "../lib/utils";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

interface ResultsBannerProps {
  plainEnglishResult: string;
  coveragePct: number;
  projectName: string;
  activeSimulationParams: any;
  stats: any;
  threeScenarios?: any;
  cpeResults?: any[];
  showToast?: (message: string, type?: "success" | "error" | "warning") => void;
}

export default function ResultsBanner({
  plainEnglishResult,
  coveragePct,
  projectName,
  activeSimulationParams,
  stats,
  threeScenarios,
  cpeResults,
  showToast,
}: ResultsBannerProps) {
  const [downloading, setDownloading] = useState(false);

  const handleDownloadPdf = async () => {
    if (!activeSimulationParams) return;
    try {
      setDownloading(true);
      const res = await axios.post(`${API_BASE}/api/generate-report`, {
        project_name: projectName || "WiFrost TVWS Project",
        simulation_params: activeSimulationParams,
        stats: stats,
        plain_english_result: plainEnglishResult,
        three_scenarios: threeScenarios ?? null,
        cpe_results: cpeResults ?? null,
      });

      const base64Pdf = res.data.pdf_base64;
      const binStr = window.atob(base64Pdf);
      const len = binStr.length;
      const bytes = new Uint8Array(len);
      for (let i = 0; i < len; i++) {
        bytes[i] = binStr.charCodeAt(i);
      }
      const blob = new Blob([bytes], { type: "application/pdf" });
      const link = document.createElement("a");
      link.href = window.URL.createObjectURL(blob);
      link.download = `${projectName.replace(/\s+/g, "_") || "wifrost"}_coverage_report.pdf`;
      link.click();
      if (showToast) showToast("PDF report downloaded successfully!", "success");
    } catch (e) {
      console.error("Failed to download PDF report:", e);
      if (showToast) {
        showToast("Error generating PDF report. Please check backend connection.", "error");
      } else {
        alert("Error generating PDF report. Please check backend connection.");
      }
    } finally {
      setDownloading(false);
    }
  };

  const isSuccess = coveragePct >= 85.0;

  return (
    <div
      className={`p-4 rounded-2xl border flex flex-col gap-4 transition-all duration-300 ${
        isSuccess
          ? "glass-panel border-emerald-500/20 text-emerald-300"
          : "glass-panel border-amber-500/20 text-amber-300"
      }`}
    >
      <div className="flex items-start gap-3">
        <div className="mt-0.5 flex-shrink-0">
          {isSuccess ? (
            <CheckCircle2 className="w-4 h-4 text-emerald-400" />
          ) : (
            <AlertTriangle className="w-4 h-4 text-amber-400" />
          )}
        </div>
        <div className="min-w-0">
          <h3 className="text-xs font-bold text-white uppercase tracking-wider">Simulation Outcome</h3>
          <p className="text-xs opacity-90 mt-1 leading-relaxed text-slate-300">{plainEnglishResult}</p>
        </div>
      </div>

      <button
        onClick={handleDownloadPdf}
        disabled={downloading || !activeSimulationParams}
        className="w-full flex items-center justify-center gap-2 py-2.5 bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 disabled:opacity-50 text-white rounded-xl font-semibold text-xs transition-all duration-300 shadow-[0_0_15px_rgba(79,70,229,0.3)] border border-white/10 cursor-pointer"
      >
        {downloading ? (
          <>
            <Loader2 className="w-3.5 h-3.5 animate-spin" />
            Generating PDF Report...
          </>
        ) : (
          <>
            <FileText className="w-3.5 h-3.5" />
            Download PDF Report
          </>
        )}
      </button>
    </div>
  );
}
