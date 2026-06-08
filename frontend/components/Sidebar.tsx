"use client";

import React, { useState, useEffect, useRef } from "react";
import { Upload, Sliders, Play, Settings, AlertCircle, FileSpreadsheet, Compass, CheckCircle, Database, History, HelpCircle } from "lucide-react";
import axios from "axios";
import CompassRose from "./CompassRose";
import HistoryPanel from "./HistoryPanel";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

const SECTOR_COLORS = ["#3B82F6", "#22C55E", "#F59E0B"];

// Rx sensitivity from first principles:
//   sens(dBm) = -174 (kT/Hz) + 10·log10(BW_Hz) + NoiseFigure + RequiredSNR
// Defaults: 12 MHz channel (2 × 6 MHz TV channels), NF 6 dB, SNR 3 dB → -94.2 dBm.
const DEFAULT_NOISE_FIGURE_DB = 6;
const DEFAULT_REQUIRED_SNR_DB = 3;
function computeSensitivityDbm(bwMhz: number, nfDb: number, snrDb: number): number {
  if (!bwMhz || bwMhz <= 0) return -94;
  const thermal = -174 + 10 * Math.log10(bwMhz * 1e6);
  return Math.round((thermal + nfDb + snrDb) * 10) / 10;
}

interface TooltipProps {
  content: string;
}

const Tooltip: React.FC<TooltipProps> = ({ content }) => {
  return (
    <span className="relative group inline-flex items-center">
      <HelpCircle className="w-3 h-3 text-slate-500 hover:text-slate-300 cursor-help" />
      <span className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 w-64 p-2 bg-black/60 backdrop-blur-xl border border-white/10 text-xs text-slate-200 font-normal rounded-lg shadow-xl opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all duration-200 z-50 pointer-events-none text-center normal-case">
        {content}
      </span>
    </span>
  );
};

interface SidebarProps {
  onFileParsed: (data: any, fileName: string) => void;
  onSimulate: (params: any) => void;
  isLoading: boolean;
  parsedSites: any[];
  onSectorChange?: (azimuths: number[], hpbw: number) => void;
  onLoadHistoryRun: (id: string) => void;
  showToast?: (message: string, type?: "success" | "error" | "warning") => void;
}

export default function Sidebar({ onFileParsed, onSimulate, isLoading, parsedSites, onSectorChange, onLoadHistoryRun, showToast }: SidebarProps) {
  const [file, setFile] = useState<File | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [parsing, setParsing] = useState(false);
  const [btsDefaults, setBtsDefaults] = useState<any>(null);
  const [cpeDefaults, setCpeDefaults] = useState<any>(null);

  // History states
  const [activeTab, setActiveTab] = useState<"params" | "history">("params");
  const [historyRuns, setHistoryRuns] = useState<any[]>([]);
  const [loadingHistory, setLoadingHistory] = useState(false);

  const fetchHistory = () => {
    setLoadingHistory(true);
    axios
      .get(`${API_BASE}/api/history`)
      .then((res) => {
        setHistoryRuns(res.data.runs || []);
      })
      .catch((err) => {
        console.error("Failed to load simulation history:", err);
      })
      .finally(() => {
        setLoadingHistory(false);
      });
  };

  useEffect(() => {
    if (activeTab === "history") {
      fetchHistory();
    }
  }, [activeTab]);

  const handleDeleteHistoryRun = (runId: string) => {
    if (!confirm("Are you sure you want to delete this simulation from history?")) return;
    axios
      .delete(`${API_BASE}/api/history/${runId}`)
      .then(() => {
        fetchHistory();
      })
      .catch((err) => {
        console.error("Failed to delete history run:", err);
        alert("Failed to delete history run.");
      });
  };

  // Form Fields
  const [selectedBtsIndex, setSelectedBtsIndex] = useState<number>(0);
  const [frequencyMhz, setFrequencyMhz] = useState<number>(600.0);
  const [btsHeight, setBtsHeight] = useState<number>(30.0);
  const [cpeHeight, setCpeHeight] = useState<number>(10.0);
  const [txPowerDbm, setTxPowerDbm] = useState<number>(23.0);
  const [antennaGainDbi, setAntennaGainDbi] = useState<number>(13.0);
  const [cableLossDb, setCableLossDb] = useState<number>(0.0);
  
  // Channel bandwidth + NF + SNR → computed Rx sensitivity
  const [channelBwMhz, setChannelBwMhz] = useState<number>(12);
  const [noiseFigureDb, setNoiseFigureDb] = useState<number>(DEFAULT_NOISE_FIGURE_DB);
  const [requiredSnrDb, setRequiredSnrDb] = useState<number>(DEFAULT_REQUIRED_SNR_DB);
  const [cpeSensitivity, setCpeSensitivity] = useState<number>(
    computeSensitivityDbm(12, DEFAULT_NOISE_FIGURE_DB, DEFAULT_REQUIRED_SNR_DB)
  );
  const [cpeGainDbi, setCpeGainDbi] = useState<number>(10.0);
  const [cpeCableLossDb, setCpeCableLossDb] = useState<number>(0.0);

  const [systemMarginDb, setSystemMarginDb] = useState<number>(15.0);
  const [coverageProbability, setCoverageProbability] = useState<string>("90%");
  const [modelType, setModelType] = useState<string>("terrain_aware");
  const [srtmKey, setSrtmKey] = useState<string>("");
  const [environment, setEnvironment] = useState<string>("auto");

  const [rfPreset, setRfPreset] = useState<string>("manual");
  const [advancedMode, setAdvancedMode] = useState(() => {
    if (typeof window === 'undefined') return false;
    return localStorage.getItem('wifrost_advanced_mode') === 'true';
  });

  interface PresetConfig {
    name: string;
    frequency: number;
    btsHeight: number;
    cpeHeight: number;
    systemMargin: number;
    txPower: number;
    antennaGain: number;
    cableLoss: number;
  }

  const RF_PRESETS: Record<string, PresetConfig> = {
    macro_site: {
      name: "Macro Site (High Tower, Long Range)",
      frequency: 500.0,
      btsHeight: 45.0,
      cpeHeight: 12.0,
      systemMargin: 12.0,
      txPower: 23.0,
      antennaGain: 13.0,
      cableLoss: 0.0
    },
    standard_cell: {
      name: "Standard Cell (Typical Coverage)",
      frequency: 600.0,
      btsHeight: 30.0,
      cpeHeight: 10.0,
      systemMargin: 20.0,
      txPower: 23.0,
      antennaGain: 13.0,
      cableLoss: 0.0
    },
    small_cell: {
      name: "Small Cell (Low Profile)",
      frequency: 600.0,
      btsHeight: 20.0,
      cpeHeight: 8.0,
      systemMargin: 8.0,
      txPower: 23.0,
      antennaGain: 13.0,
      cableLoss: 0.0
    }
  };

  const applyRfPreset = (presetKey: string) => {
    setRfPreset(presetKey);
    if (presetKey === "manual") return;
    const p = RF_PRESETS[presetKey];
    if (!p) return;
    setFrequencyMhz(p.frequency);
    // Environment is purposefully NOT overridden so 'auto' landcover stays active!
    setBtsHeight(p.btsHeight);
    setCpeHeight(p.cpeHeight);
    // Sensitivity stays driven by channel BW / NF / SNR — presets no longer
    // hardcode it (that was overriding the 12 MHz value with -104).
    setSystemMarginDb(p.systemMargin);
    setTxPowerDbm(p.txPower);
    setAntennaGainDbi(p.antennaGain);
    setCableLossDb(p.cableLoss);
  };

  // Sector antenna state
  const [sectorCount, setSectorCount] = useState<1 | 2 | 3>(1);
  const [sectorAzimuths, setSectorAzimuths] = useState<number[]>([0]);
  const [hpbw, setHpbw] = useState<number>(65.0);
  const [vpbw, setVpbw] = useState<number>(17.0);
  const [mdtDeg, setMdtDeg] = useState<number>(6.0);
  const [ftb, setFtb] = useState<number>(25.0);

  const fileInputRef = useRef<HTMLInputElement>(null);

  // Fetch factory defaults on mount
  useEffect(() => {
    axios
      .get(`${API_BASE}/api/defaults`)
      .then((res) => {
        const { bts, cpe } = res.data;
        setBtsDefaults(bts);
        setCpeDefaults(cpe);

        // Apply defaults
        setFrequencyMhz((bts.freq_min_mhz + bts.freq_max_mhz) / 2 || 600.0);
        setBtsHeight(bts.antenna_height_default_m || 30.0);
        setCpeHeight(cpe.antenna_height_default_m || 10.0);
        setTxPowerDbm(bts.tx_power_dbm || 23.0);
        setAntennaGainDbi(bts.antenna_gain_dbi || 13.0);
        setCableLossDb(bts.cable_loss_db || 0.0);
        // Sensitivity is computed from channel BW / NF / SNR (see effect below),
        // not taken from the datasheet field — keeps it consistent with the BW.
        setCpeGainDbi(cpe.antenna_gain_dbi || 10.0);
        setCpeCableLossDb(cpe.cable_loss_db || 0.0);
        setHpbw(bts.beamwidth_h_deg || 65.0);
        setVpbw(bts.beamwidth_v_deg || 17.0);
        setFtb(bts.front_to_back_ratio || 25.0);
      })
      .catch((err) => {
        console.error("Failed to load WiFrost defaults:", err);
      });
  }, []);

  // Recompute sensitivity whenever bandwidth, noise figure, or required SNR change.
  useEffect(() => {
    setCpeSensitivity(computeSensitivityDbm(channelBwMhz, noiseFigureDb, requiredSnrDb));
  }, [channelBwMhz, noiseFigureDb, requiredSnrDb]);

  // Notify parent whenever live sector config changes (keeps map wedges in sync without re-sim)
  useEffect(() => {
    onSectorChange?.(sectorAzimuths.slice(0, sectorCount), hpbw);
  }, [sectorAzimuths, sectorCount, hpbw]);

  const btsCandidates = parsedSites.filter((s) => s.is_bts_candidate);

  // Reset BTS index selection when sites change
  useEffect(() => {
    setSelectedBtsIndex(0);
  }, [parsedSites]);

  // EIRP calculation
  const eirpDbm = Number(txPowerDbm) + Number(antennaGainDbi) - Number(cableLossDb);

  const handleFileChange = async (selectedFile: File) => {
    setFile(selectedFile);
    setUploadError(null);
    setParsing(true);

    const formData = new FormData();
    formData.append("file", selectedFile);

    try {
      const res = await axios.post(`${API_BASE}/api/parse-file`, formData, {
        headers: {
          "Content-Type": "multipart/form-data",
        },
      });
      onFileParsed(res.data, selectedFile.name);
    } catch (err: any) {
      console.error(err);
      setUploadError(err.response?.data?.detail || "Error parsing file. Ensure it is KMZ, KML, or Excel.");
      setFile(null);
    } finally {
      setParsing(false);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleFileChange(e.dataTransfer.files[0]);
    }
  };

  const handleSimulateClick = () => {
    onSimulate({
      site_index: selectedBtsIndex,
      frequency_mhz: frequencyMhz,
      eirp_dbm: eirpDbm,
      system_margin_db: systemMarginDb,
      coverage_probability: coverageProbability,
      model: modelType,
      srtm_key: srtmKey,
      bts_height: btsHeight,
      cpe_height: cpeHeight,
      cpe_sensitivity: cpeSensitivity,
      // Pass CPE detailed spec for CPE analysis
      environment: environment,
      tx_power_dbm: txPowerDbm,
      antenna_gain_dbi: antennaGainDbi,
      cable_loss_db: cableLossDb,
      rx_gain_dbi: cpeGainDbi,
      rx_cable_loss_db: cpeCableLossDb,
      rx_sensitivity_dbm: cpeSensitivity,
      // Sector antenna params
      sector_azimuths: sectorAzimuths.slice(0, sectorCount),
      hpbw_deg: hpbw,
      vpbw_deg: vpbw,
      mdt_deg: mdtDeg,
      front_to_back_db: ftb,
    });
  };

  const handleSectorCountChange = (n: 1 | 2 | 3) => {
    setSectorCount(n);
    if (n === 1) setSectorAzimuths([sectorAzimuths[0] ?? 0]);
    else if (n === 2) setSectorAzimuths([sectorAzimuths[0] ?? 0, sectorAzimuths[1] ?? 180]);
    else setSectorAzimuths([sectorAzimuths[0] ?? 0, sectorAzimuths[1] ?? 120, sectorAzimuths[2] ?? 240]);
  };

  const handleAzimuthChange = (idx: number, value: number) => {
    setSectorAzimuths((prev) => {
      const next = [...prev];
      next[idx] = ((value % 360) + 360) % 360;
      return next;
    });
  };

  const autoSpaceFrom0 = () => {
    const base = sectorAzimuths[0] ?? 0;
    setSectorAzimuths([base, (base + 120) % 360, (base + 240) % 360]);
  };

  return (
    <aside className="w-[320px] bg-black/40 backdrop-blur-3xl border border-white/10 rounded-[2.5rem] shadow-[0_0_40px_rgba(0,0,0,0.5)] flex flex-col h-full overflow-hidden">
      {/* Sidebar Tabs (Segmented Control) */}
      <div className="p-4 flex justify-center border-b border-white/5">
        <div className="flex bg-black/40 backdrop-blur-md rounded-full p-1 border border-white/10 w-full max-w-[300px]">
          <button
            onClick={() => setActiveTab("params")}
            className={`flex-1 py-2 text-xs font-semibold uppercase tracking-wider flex items-center justify-center gap-1.5 rounded-full transition-all duration-300 ${
              activeTab === "params"
                ? "bg-white/10 text-white shadow-sm"
                : "text-white/40 hover:text-white/70"
            }`}
          >
            <Sliders className="w-3.5 h-3.5" />
            Parameters
          </button>
          <button
            onClick={() => setActiveTab("history")}
            className={`flex-1 py-2 text-xs font-semibold uppercase tracking-wider flex items-center justify-center gap-1.5 rounded-full transition-all duration-300 ${
              activeTab === "history"
                ? "bg-white/10 text-white shadow-sm"
                : "text-white/40 hover:text-white/70"
            }`}
          >
            <History className="w-3.5 h-3.5" />
            History
          </button>
        </div>
      </div>

      {activeTab === "history" ? (
        <HistoryPanel
          runs={historyRuns}
          loading={loadingHistory}
          onSelectRun={(id) => {
            onLoadHistoryRun(id);
          }}
          onDeleteRun={handleDeleteHistoryRun}
          onRefresh={fetchHistory}
        />
      ) : (
        <>
          <div className="flex-1 overflow-y-auto">
            {/* File Upload Section */}
      <div className="p-5 border-b border-white/5 space-y-4">
        <h2 className="text-sm font-semibold text-slate-300 uppercase tracking-wider flex items-center gap-2">
          <Upload className="w-4 h-4 text-blue-500" />
          1. Import Network Layout
        </h2>

        <div
          onDragOver={(e) => e.preventDefault()}
          onDrop={handleDrop}
          onClick={() => fileInputRef.current?.click()}
          className="border-2 border-dashed border-white/20 bg-white/[0.02] hover:bg-white/[0.04] rounded-xl p-6 text-center cursor-pointer transition-all duration-300 group"
        >
          <input
            type="file"
            ref={fileInputRef}
            onChange={(e) => e.target.files?.[0] && handleFileChange(e.target.files[0])}
            accept=".kmz,.kml,.xlsx"
            className="hidden"
          />
          {parsing ? (
            <div className="flex flex-col items-center space-y-2">
              <span className="w-8 h-8 rounded-full border-2 border-blue-500 border-t-transparent animate-spin" />
              <span className="text-sm text-slate-400">Parsing layout...</span>
            </div>
          ) : file ? (
            <div className="flex flex-col items-center space-y-1">
              <FileSpreadsheet className="w-8 h-8 text-emerald-400 group-hover:scale-110 transition duration-300" />
              <span className="text-sm text-white font-medium truncate max-w-[200px] mt-1">{file.name}</span>
              <span className="text-xs text-slate-400 flex items-center gap-1"><CheckCircle className="w-3 h-3 text-emerald-400" /> Loaded</span>
            </div>
          ) : (
            <div className="flex flex-col items-center space-y-1">
              <Upload className="w-8 h-8 text-slate-500 group-hover:text-blue-400 group-hover:scale-115 transition duration-300" />
              <span className="text-sm text-slate-300 font-medium mt-1">Upload KML, KMZ or Excel</span>
              <span className="text-xs text-slate-500">Drag &amp; drop file here</span>
            </div>
          )}
        </div>

        {uploadError && (
          <div className="p-3 bg-red-950/20 border border-red-500/20 rounded-lg text-xs text-red-400 flex items-start gap-2">
            <AlertCircle className="w-4 h-4 flex-shrink-0 mt-0.5" />
            <p>{uploadError}</p>
          </div>
        )}
      </div>

      {/* Simulation Parameters Section */}
      <div className="p-5 flex-1 space-y-5">
        <h2 className="text-sm font-semibold text-slate-300 uppercase tracking-wider flex items-center gap-2">
          <Sliders className="w-4 h-4 text-blue-500" />
          2. Simulation Parameters
        </h2>

        <div className="space-y-4">


          {/* Active BTS site */}
          <div className="space-y-1.5">
            <label className="text-[10px] uppercase tracking-widest font-semibold text-white/40">Active BTS Site</label>
            <select
              value={selectedBtsIndex}
              onChange={(e) => setSelectedBtsIndex(Number(e.target.value))}
              disabled={btsCandidates.length === 0}
              className="w-full px-3 py-2 bg-white/5 border border-white/10 rounded-xl text-sm text-white focus:outline-none focus:border-blue-500 disabled:opacity-50"
            >
              {btsCandidates.length === 0 ? (
                <option value={0}>No BTS candidates found</option>
              ) : (
                <>
                  <option value={-1}>All Towers (Consolidated)</option>
                  {btsCandidates.map((site, index) => (
                    <option key={index} value={index}>
                      {site.name}
                    </option>
                  ))}
                </>
              )}
            </select>
          </div>

          <div className="flex justify-end">
            <button
              type="button"
              onClick={() => {
                const next = !advancedMode;
                setAdvancedMode(next);
                localStorage.setItem('wifrost_advanced_mode', String(next));
              }}
              className="text-xs text-blue-400 hover:text-blue-300 font-medium"
            >
              {advancedMode ? "Advanced ▴" : "Advanced ▾"}
            </button>
          </div>

          {/* RF Parameter Preset (Advanced) */}
          {advancedMode && (
            <div className="space-y-1.5">
              <label className="text-[10px] uppercase tracking-widest font-semibold text-white/40 flex items-center gap-1.5">
                RF Deployment Profile
                <Tooltip content="Quick presets to pre-fill standard hardware parameters, or choose Manual to custom tune." />
              </label>
              <select
                value={rfPreset}
                onChange={(e) => applyRfPreset(e.target.value)}
                className="w-full bg-white/5 border border-white/10 rounded-xl px-3 py-2 text-sm text-white focus:outline-none focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500 transition-colors"
              >
                <option value="manual">✓ Manual (Custom)</option>
                <option value="macro_site">Macro Site (High Tower, Long Range)</option>
                <option value="standard_cell">Standard Cell (Typical Coverage)</option>
                <option value="small_cell">Small Cell (Low Profile)</option>
              </select>
            </div>
          )}

          {/* Model Type */}
          {advancedMode && (
            <div className="space-y-1.5">
              <label className="text-[10px] uppercase tracking-widest font-semibold text-white/40 flex items-center gap-1.5">
                Propagation Model
                <Tooltip content="Terrain-Aware: Okumura-Hata propagation calculated over real elevation data from SRTM. Flat Hata: Standard Hata formula assuming a flat plain." />
              </label>
              <div className="grid grid-cols-2 gap-2">
                <button
                  type="button"
                  onClick={() => setModelType("terrain_aware")}
                  className={`py-2 text-xs font-medium rounded-lg border transition ${
                    modelType === "terrain_aware"
                      ? "bg-blue-600/10 border-blue-500 text-blue-400 font-semibold"
                      : "bg-slate-950/40 border-slate-850 text-slate-400 hover:text-slate-200"
                  }`}
                >
                  Terrain-Aware
                </button>
                <button
                  type="button"
                  onClick={() => setModelType("flat")}
                  className={`py-2 text-xs font-medium rounded-lg border transition ${
                    modelType === "flat"
                      ? "bg-blue-600/10 border-blue-500 text-blue-400 font-semibold"
                      : "bg-slate-950/40 border-slate-850 text-slate-400 hover:text-slate-200"
                  }`}
                >
                  Flat Hata
                </button>
              </div>
            </div>
          )}

          {/* Clutter Environment */}
          {advancedMode && (
            <div className="space-y-1.5">
              <label className="text-[10px] uppercase tracking-widest font-semibold text-white/40 flex items-center gap-1.5">
                Clutter Environment
                <Tooltip content="Auto derives the environment from ESA WorldCover land cover for the area — recommended, avoids biasing results with a wrong manual pick. Per-pixel clutter is always applied from land cover when available; this setting controls the Hata correction type. Manual: Open (3 dB), Open Water (0 dB), Suburban (8 dB), Light Vegetation (6 dB), Dense Vegetation (15 dB), Port/Industrial (12 dB), Urban (18 dB)." />
              </label>
              <select
                value={environment}
                onChange={(e) => {
                  setEnvironment(e.target.value);
                  setRfPreset("manual");
                }}
                className="w-full px-3 py-2 bg-white/5 border border-white/10 rounded-xl text-sm text-white focus:outline-none focus:border-blue-500"
              >
                <option value="auto">Auto (from land cover) — recommended</option>
                <option value="open">Open / Rural Flat</option>
                <option value="open_water">Open Water / Sea</option>
                <option value="suburban">Suburban / Trees & Houses</option>
                <option value="vegetation_light">Light Vegetation / Forest Edge</option>
                <option value="vegetation_dense">Dense Vegetation / Deep Jungle</option>
                <option value="port_industrial">Port / Industrial</option>
                <option value="urban">Urban / Tall Structures</option>
              </select>
              {environment === "auto" && (
                <p className="text-[9px] text-slate-600">
                  The model picks the dominant land-cover environment for the area at run time.
                </p>
              )}
            </div>
          )}

          {/* Frequency & Heights */}
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <label className="text-[10px] uppercase tracking-widest font-semibold text-white/40 flex items-center gap-1.5">
                Frequency (MHz)
                <Tooltip content="TVWS frequencies operate between 470-670 MHz. Lower frequencies propagate further and penetrate obstacles better." />
              </label>
              <input
                type="number"
                value={frequencyMhz}
                onChange={(e) => {
                  setFrequencyMhz(Number(e.target.value));
                  setRfPreset("manual");
                }}
                min={470}
                max={670}
                className="w-full px-3 py-2 bg-white/5 border border-white/10 rounded-xl text-sm text-white focus:outline-none focus:border-blue-500"
              />
            </div>
            <div className="space-y-1.5">
              <label className="text-[10px] uppercase tracking-widest font-semibold text-white/40 flex items-center gap-1.5">
                BTS Height (m)
                <Tooltip content="Height of the base station antenna above ground level. Higher placement improves line-of-sight and clearance over obstacles." />
              </label>
              <input
                type="number"
                value={btsHeight}
                onChange={(e) => {
                  setBtsHeight(Number(e.target.value));
                  setRfPreset("manual");
                }}
                className="w-full px-3 py-2 bg-white/5 border border-white/10 rounded-xl text-sm text-white focus:outline-none focus:border-blue-500"
              />
            </div>
          </div>

          {/* Transmitter Power specs */}
          {advancedMode && (
            <details className="group border border-white/10 rounded-xl bg-white/[0.02] overflow-hidden">
              <summary className="px-3 py-2 text-[10px] uppercase tracking-widest font-semibold text-white/40 cursor-pointer flex justify-between items-center hover:bg-slate-950/40 transition">
                <span>BTS Equipment Config</span>
                <Settings className="w-3.5 h-3.5 text-slate-500 group-open:rotate-90 transition duration-300" />
              </summary>
              <div className="p-3 border-t border-slate-850 space-y-3 bg-slate-950/10">
                <div className="grid grid-cols-3 gap-2">
                  <div className="space-y-1">
                    <label className="text-[10px] text-slate-500 uppercase">Power (dBm)</label>
                    <input
                      type="number"
                      value={txPowerDbm}
                      onChange={(e) => {
                        setTxPowerDbm(Number(e.target.value));
                        setRfPreset("manual");
                      }}
                      className="w-full px-2 py-1 bg-slate-950 border border-slate-850 rounded text-xs text-white"
                    />
                  </div>
                  <div className="space-y-1">
                    <label className="text-[10px] text-slate-500 uppercase">Gain (dBi)</label>
                    <input
                      type="number"
                      value={antennaGainDbi}
                      onChange={(e) => {
                        setAntennaGainDbi(Number(e.target.value));
                        setRfPreset("manual");
                      }}
                      className="w-full px-2 py-1 bg-slate-950 border border-slate-850 rounded text-xs text-white"
                    />
                  </div>
                  <div className="space-y-1">
                    <label className="text-[10px] text-slate-500 uppercase">Loss (dB)</label>
                    <input
                      type="number"
                      value={cableLossDb}
                      onChange={(e) => {
                        setCableLossDb(Number(e.target.value));
                        setRfPreset("manual");
                      }}
                      className="w-full px-2 py-1 bg-slate-950 border border-slate-850 rounded text-xs text-white"
                    />
                  </div>
                </div>
                <div className="text-[10px] text-slate-400 text-right">
                  Calculated EIRP: <span className="text-blue-400 font-bold">{eirpDbm.toFixed(1)} dBm</span>
                </div>
              </div>
            </details>
          )}

          {/* ── ANTENNA SECTORS ─────────────────────────────── */}
          <div className="border border-slate-700 rounded-lg bg-slate-950/20 overflow-hidden">
            <div className="px-3 py-2 border-b border-white/5 flex items-center gap-2">
              <Compass className="w-3.5 h-3.5 text-blue-400" />
              <span className="text-xs font-semibold text-slate-300 uppercase tracking-wider">Antenna Sectors</span>
            </div>
            <div className="p-3 space-y-3">

              {/* Sector count selector */}
              <div className="space-y-1.5">
                <label className="text-[10px] text-slate-500 uppercase">Number of sectors</label>
                <div className="grid grid-cols-3 gap-1">
                  {([1, 2, 3] as const).map((n) => (
                    <button
                      key={n}
                      type="button"
                      onClick={() => handleSectorCountChange(n)}
                      className={`py-1.5 text-xs font-semibold rounded-md border transition ${
                        sectorCount === n
                          ? "bg-blue-600/20 border-blue-500 text-blue-300"
                          : "bg-slate-950/40 border-slate-800 text-slate-400 hover:text-slate-200"
                      }`}
                    >
                      {n}
                    </button>
                  ))}
                </div>
              </div>

              {/* Live compass rose */}
              <div className="flex justify-center py-1">
                <CompassRose
                  sectors={sectorAzimuths.slice(0, sectorCount).map((az, i) => ({
                    azimuth: az,
                    color: SECTOR_COLORS[i],
                  }))}
                  hpbw={hpbw}
                  size={140}
                  onAzimuthChange={handleAzimuthChange}
                />
              </div>

              {/* Azimuth inputs */}
              <div className="space-y-2">
                {sectorAzimuths.slice(0, sectorCount).map((az, i) => (
                  <div key={i} className="flex items-center gap-2">
                    <span className="w-2 h-2 rounded-full flex-shrink-0" style={{ background: SECTOR_COLORS[i] }} />
                    <label className="text-[10px] text-slate-400 w-16 flex-shrink-0">
                      {sectorCount === 1 ? "Azimuth" : `Sector ${i + 1}`}
                    </label>
                    <input
                      type="number"
                      min={0}
                      max={359}
                      value={az}
                      onChange={(e) => handleAzimuthChange(i, Number(e.target.value))}
                      className="w-16 px-2 py-1 bg-slate-950 border border-slate-800 rounded text-xs text-white text-right"
                    />
                    <span className="text-[10px] text-slate-500">°</span>
                  </div>
                ))}
                {sectorCount === 1 && (
                  <p className="text-[10px] text-slate-600 leading-tight">
                    0° = North · 90° = East · 180° = South · 270° = West
                  </p>
                )}
                {sectorCount === 3 && (
                  <button
                    type="button"
                    onClick={autoSpaceFrom0}
                    className="w-full py-1.5 text-[10px] text-slate-400 border border-slate-800 rounded-lg hover:text-slate-200 hover:border-slate-600 transition"
                  >
                    ↺ Equal spacing from Sector 1
                  </button>
                )}
              </div>

              {/* Antenna pattern — collapsed by default */}
              <details className="group">
                <summary className="text-[10px] text-slate-500 uppercase cursor-pointer hover:text-slate-300 transition flex items-center gap-1">
                  <span className="group-open:rotate-90 inline-block transition-transform">▶</span>
                  Antenna Pattern
                </summary>
                <div className="mt-2 space-y-2 pl-3 border-l border-slate-800">
                  <p className="text-[9px] text-slate-600">WiFrost panel defaults</p>
                  {[
                    { label: "H-plane HPBW (°)", val: hpbw, set: setHpbw },
                    { label: "V-plane VPBW (°)", val: vpbw, set: setVpbw },
                    { label: "Mech. Downtilt (°)", val: mdtDeg, set: setMdtDeg },
                    { label: "Front/Back (dB)",  val: ftb,  set: setFtb  },
                  ].map(({ label, val, set }) => (
                    <div key={label} className="flex items-center justify-between gap-2">
                      <label className="text-[10px] text-slate-400 flex-1">{label}</label>
                      <input
                        type="number"
                        value={val}
                        onChange={(e) => set(Number(e.target.value))}
                        className="w-16 px-2 py-1 bg-slate-950 border border-slate-800 rounded text-xs text-white text-right"
                      />
                    </div>
                  ))}
                </div>
              </details>

            </div>
          </div>

          {/* CPE specs */}
          {advancedMode && (
            <details className="group border border-white/10 rounded-xl bg-white/[0.02] overflow-hidden">
              <summary className="px-3 py-2 text-[10px] uppercase tracking-widest font-semibold text-white/40 cursor-pointer flex justify-between items-center hover:bg-slate-950/40 transition">
                <span>CPE client Config</span>
                <Settings className="w-3.5 h-3.5 text-slate-500 group-open:rotate-90 transition duration-300" />
              </summary>
              <div className="p-3 border-t border-slate-850 space-y-3 bg-slate-950/10">
                {/* Channel bandwidth → auto-computes Rx sensitivity */}
                <div className="space-y-1.5">
                  <label className="text-[10px] text-slate-500 uppercase">Channel Bandwidth</label>
                  <div className="grid grid-cols-4 gap-1">
                    {[6, 12, 18, 24].map((bw) => (
                      <button
                        key={bw}
                        type="button"
                        onClick={() => {
                          setChannelBwMhz(bw);
                          setRfPreset("manual");
                        }}
                        className={`py-1 text-[10px] font-semibold rounded border transition ${
                          channelBwMhz === bw
                            ? "bg-blue-600/20 border-blue-500 text-blue-300"
                            : "bg-slate-950/40 border-slate-800 text-slate-400 hover:text-slate-200"
                        }`}
                      >
                        {bw} MHz
                      </button>
                    ))}
                  </div>
                  <p className="text-[9px] text-slate-600">
                    Computed Rx sensitivity: <span className="text-blue-400 font-semibold">{cpeSensitivity} dBm</span>
                    {" "}· −174 + 10·log₁₀(BW) + {noiseFigureDb} dB NF + {requiredSnrDb} dB SNR
                  </p>
                </div>
                <div className="grid grid-cols-3 gap-3">
                  <div className="space-y-1">
                    <label className="text-[10px] text-slate-500 uppercase">CPE Height (m)</label>
                    <input
                      type="number"
                      value={cpeHeight}
                      onChange={(e) => {
                        setCpeHeight(Number(e.target.value));
                        setRfPreset("manual");
                      }}
                      className="w-full px-2 py-1 bg-slate-950 border border-slate-850 rounded text-xs text-white"
                    />
                  </div>
                  <div className="space-y-1">
                    <label className="text-[10px] text-slate-500 uppercase">Noise Fig (dB)</label>
                    <input
                      type="number"
                      value={noiseFigureDb}
                      onChange={(e) => {
                        setNoiseFigureDb(Number(e.target.value));
                        setRfPreset("manual");
                      }}
                      className="w-full px-2 py-1 bg-slate-950 border border-slate-850 rounded text-xs text-white"
                    />
                  </div>
                  <div className="space-y-1">
                    <label className="text-[10px] text-slate-500 uppercase">Req. SNR (dB)</label>
                    <input
                      type="number"
                      value={requiredSnrDb}
                      onChange={(e) => {
                        setRequiredSnrDb(Number(e.target.value));
                        setRfPreset("manual");
                      }}
                      className="w-full px-2 py-1 bg-slate-950 border border-slate-850 rounded text-xs text-white"
                    />
                  </div>
                </div>
                <div className="flex items-center justify-between px-2 py-1.5 bg-slate-950/40 border border-slate-850 rounded">
                  <span className="text-[10px] text-slate-500 uppercase">Rx Sensitivity</span>
                  <span className="text-xs font-bold text-white">{cpeSensitivity} dBm</span>
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div className="space-y-1">
                    <label className="text-[10px] text-slate-500 uppercase">Ant. Gain (dBi)</label>
                    <input
                      type="number"
                      value={cpeGainDbi}
                      onChange={(e) => {
                        setCpeGainDbi(Number(e.target.value));
                        setRfPreset("manual");
                      }}
                      className="w-full px-2 py-1 bg-slate-950 border border-slate-850 rounded text-xs text-white"
                    />
                  </div>
                  <div className="space-y-1">
                    <label className="text-[10px] text-slate-500 uppercase">Cable Loss (dB)</label>
                    <input
                      type="number"
                      value={cpeCableLossDb}
                      onChange={(e) => {
                        setCpeCableLossDb(Number(e.target.value));
                        setRfPreset("manual");
                      }}
                      className="w-full px-2 py-1 bg-slate-950 border border-slate-850 rounded text-xs text-white"
                    />
                  </div>
                </div>
              </div>
            </details>
          )}

          {/* System Margin — always visible */}
          <div className="space-y-1.5">
            <label className="text-[10px] uppercase tracking-widest font-semibold text-white/40 flex items-center gap-1.5">
              System Margin (dB)
              <Tooltip content="Fading and reliability safety margin in dB. Higher values require stronger signal thresholds to declare coverage (Conservative vs Realistic)." />
            </label>
            <input
              type="number"
              value={systemMarginDb}
              onChange={(e) => {
                setSystemMarginDb(Number(e.target.value));
                setRfPreset("manual");
              }}
              min={0}
              className="w-full px-3 py-2 bg-white/5 border border-white/10 rounded-xl text-sm text-white focus:outline-none focus:border-blue-500"
            />
          </div>

          {/* Simple-mode summary */}
          {!advancedMode && (
            <p className="text-xs text-slate-500 truncate">
              Model: {modelType} · {environment} · Gain {antennaGainDbi} dBi · Margin {systemMarginDb} dB
            </p>
          )}

          {/* Coverage Probability — advanced only */}
          {advancedMode && (
            <div className="space-y-1.5">
              <label className="text-[10px] uppercase tracking-widest font-semibold text-white/40 flex items-center gap-1.5">
                Coverage Prob.
                <Tooltip content="The probability that the required signal strength is achieved at any given location. 90% is industry standard." />
              </label>
              <select
                value={coverageProbability}
                onChange={(e) => setCoverageProbability(e.target.value)}
                className="w-full px-3 py-2 bg-white/5 border border-white/10 rounded-xl text-sm text-white focus:outline-none focus:border-blue-500"
              >
                <option value="50%">50% (Median)</option>
                <option value="75%">75%</option>
                <option value="90%">90% (Standard)</option>
                <option value="95%">95% (High Reliability)</option>
                <option value="99%">99% (Pessimistic)</option>
              </select>
            </div>
          )}

          {/* OpenTopography Key */}
          {advancedMode && (
            <div className="space-y-1.5">
              <label className="text-[10px] uppercase tracking-widest font-semibold text-white/40 flex items-center gap-1.5">
                OpenTopography Key
                <Tooltip content="Your personal OpenTopography key to query terrain elevations. Leave empty to use the server's shared key." />
              </label>
              <input
                type="password"
                placeholder="Uses server defaults if blank"
                value={srtmKey}
                onChange={(e) => setSrtmKey(e.target.value)}
                className="w-full px-3 py-2 bg-white/5 border border-white/10 rounded-xl text-sm text-white placeholder-slate-600 focus:outline-none focus:border-blue-500"
              />
            </div>
          )}
        </div>
      </div>

          </div>

          {/* Rerun simulation button */}
          <div className="p-6 bg-transparent flex justify-center">
            <button
              onClick={handleSimulateClick}
              disabled={isLoading || parsedSites.length === 0}
              className="w-[90%] py-3.5 bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 disabled:opacity-50 text-white rounded-full font-bold flex items-center justify-center gap-2 transition-all duration-300 shadow-[0_0_20px_rgba(79,70,229,0.4)] disabled:shadow-none border border-white/20 cursor-pointer text-[13px] tracking-wide"
            >
              {isLoading ? (
                <>
                  <span className="w-4 h-4 rounded-full border-2 border-white border-t-transparent animate-spin" />
                  Running Simulation...
                </>
              ) : (
                <>
                  <Play className="fill-current w-4 h-4" />
                  Run Simulation
                </>
              )}
            </button>
          </div>
        </>
      )}
    </aside>
  );
}
