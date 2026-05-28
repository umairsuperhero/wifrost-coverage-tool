import React, { useState } from "react";
import { CheckCircle2, AlertTriangle, FileText, Loader2 } from "lucide-react";
import axios from "axios";

interface ResultsBannerProps {
  plainEnglishResult: string;
  coveragePct: number;
  projectName: string;
  activeSimulationParams: any;
  stats: any;
}

export default function ResultsBanner({
  plainEnglishResult,
  coveragePct,
  projectName,
  activeSimulationParams,
  stats,
}: ResultsBannerProps) {
  const [downloading, setDownloading] = useState(false);

  const handleDownloadPdf = async () => {
    if (!activeSimulationParams) return;
    try {
      setDownloading(true);
      const res = await axios.post("http://127.0.0.1:8000/api/generate-report", {
        project_name: projectName || "WiFrost TVWS Project",
        simulation_params: activeSimulationParams,
        stats: stats,
        plain_english_result: plainEnglishResult,
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
    } catch (e) {
      console.error("Failed to download PDF report:", e);
      alert("Error generating PDF report. Please check backend connection.");
    } finally {
      setDownloading(false);
    }
  };

  const isSuccess = coveragePct >= 85.0;

  return (
    <div
      className={`p-4 rounded-xl border flex flex-col md:flex-row items-start md:items-center justify-between gap-4 transition-all duration-300 ${
        isSuccess
          ? "bg-emerald-950/30 border-emerald-500/20 text-emerald-300"
          : "bg-amber-950/30 border-amber-500/20 text-amber-300"
      }`}
    >
      <div className="flex items-start gap-3">
        <div className="mt-1">
          {isSuccess ? (
            <CheckCircle2 className="w-5 h-5 text-emerald-400" />
          ) : (
            <AlertTriangle className="w-5 h-5 text-amber-400" />
          )}
        </div>
        <div>
          <h3 className="font-semibold text-white">Simulation Outcome Summary</h3>
          <p className="text-sm opacity-90 mt-0.5">{plainEnglishResult}</p>
        </div>
      </div>

      <button
        onClick={handleDownloadPdf}
        disabled={downloading || !activeSimulationParams}
        className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-slate-800 disabled:text-slate-400 text-white rounded-lg font-medium text-sm transition shadow-lg shadow-blue-500/10 border border-blue-500/30 cursor-pointer"
      >
        {downloading ? (
          <>
            <Loader2 className="w-4 h-4 animate-spin" />
            Generating PDF...
          </>
        ) : (
          <>
            <FileText className="w-4 h-4" />
            Download PDF Report
          </>
        )}
      </button>
    </div>
  );
}
