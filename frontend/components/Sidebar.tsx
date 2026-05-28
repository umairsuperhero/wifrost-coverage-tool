"use client";

import React, { useState, useEffect, useRef } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";
import { Upload, Sliders, Play, Settings, AlertCircle, FileSpreadsheet, Compass, CheckCircle } from "lucide-react";
import axios from "axios";

interface SidebarProps {
  onFileParsed: (data: { sites: any[]; polygons: any[]; lines: any[] }, fileName: string) => void;
  onSimulate: (params: any) => void;
  isLoading: boolean;
  parsedSites: any[];
}

export default function Sidebar({ onFileParsed, onSimulate, isLoading, parsedSites }: SidebarProps) {
  const [file, setFile] = useState<File | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [parsing, setParsing] = useState(false);
  const [btsDefaults, setBtsDefaults] = useState<any>(null);
  const [cpeDefaults, setCpeDefaults] = useState<any>(null);

  // Form Fields
  const [selectedBtsIndex, setSelectedBtsIndex] = useState<number>(0);
  const [frequencyMhz, setFrequencyMhz] = useState<number>(600.0);
  const [btsHeight, setBtsHeight] = useState<number>(30.0);
  const [cpeHeight, setCpeHeight] = useState<number>(10.0);
  const [txPowerDbm, setTxPowerDbm] = useState<number>(23.0);
  const [antennaGainDbi, setAntennaGainDbi] = useState<number>(13.0);
  const [cableLossDb, setCableLossDb] = useState<number>(0.0);
  
  // CPE Receiver sensitivity
  const [cpeSensitivity, setCpeSensitivity] = useState<number>(-104.0);
  const [cpeGainDbi, setCpeGainDbi] = useState<number>(10.0);
  const [cpeCableLossDb, setCpeCableLossDb] = useState<number>(0.0);

  const [systemMarginDb, setSystemMarginDb] = useState<number>(15.0);
  const [coverageProbability, setCoverageProbability] = useState<string>("90%");
  const [modelType, setModelType] = useState<string>("terrain_aware");
  const [srtmKey, setSrtmKey] = useState<string>("");

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
        setCpeSensitivity(cpe.receiver_sensitivity_dbm || -104.0);
        setCpeGainDbi(cpe.antenna_gain_dbi || 10.0);
        setCpeCableLossDb(cpe.cable_loss_db || 0.0);
      })
      .catch((err) => {
        console.error("Failed to load WiFrost defaults:", err);
      });
  }, []);

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
      environment: "suburban",
      tx_power_dbm: txPowerDbm,
      antenna_gain_dbi: antennaGainDbi,
      cable_loss_db: cableLossDb,
      rx_gain_dbi: cpeGainDbi,
      rx_cable_loss_db: cpeCableLossDb,
      rx_sensitivity_dbm: cpeSensitivity,
    });
  };

  return (
    <aside className="w-[380px] bg-slate-900/40 border-r border-slate-800 flex flex-col h-full overflow-y-auto">
      {/* File Upload Section */}
      <div className="p-5 border-b border-slate-800 space-y-4">
        <h2 className="text-sm font-semibold text-slate-300 uppercase tracking-wider flex items-center gap-2">
          <Upload className="w-4 h-4 text-blue-500" />
          1. Import Network Layout
        </h2>

        <div
          onDragOver={(e) => e.preventDefault()}
          onDrop={handleDrop}
          onClick={() => fileInputRef.current?.click()}
          className="border-2 border-dashed border-slate-750 hover:border-blue-500/50 hover:bg-blue-600/5 rounded-xl p-6 text-center cursor-pointer transition-all duration-300 group"
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
            <label className="text-xs font-semibold text-slate-400 uppercase">Active BTS Site</label>
            <select
              value={selectedBtsIndex}
              onChange={(e) => setSelectedBtsIndex(Number(e.target.value))}
              disabled={btsCandidates.length === 0}
              className="w-full px-3 py-2 bg-slate-950/60 border border-slate-850 rounded-lg text-sm text-white focus:outline-none focus:border-blue-500 disabled:opacity-50"
            >
              {btsCandidates.length === 0 ? (
                <option value={0}>No BTS candidates found</option>
              ) : (
                btsCandidates.map((site, index) => (
                  <option key={index} value={index}>
                    {site.name}
                  </option>
                ))
              )}
            </select>
          </div>

          {/* Model Type */}
          <div className="space-y-1.5">
            <label className="text-xs font-semibold text-slate-400 uppercase">Propagation Model</label>
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

          {/* Frequency & Heights */}
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <label className="text-xs font-semibold text-slate-400 uppercase">Frequency (MHz)</label>
              <input
                type="number"
                value={frequencyMhz}
                onChange={(e) => setFrequencyMhz(Number(e.target.value))}
                min={470}
                max={670}
                className="w-full px-3 py-2 bg-slate-950/60 border border-slate-850 rounded-lg text-sm text-white focus:outline-none focus:border-blue-500"
              />
            </div>
            <div className="space-y-1.5">
              <label className="text-xs font-semibold text-slate-400 uppercase">BTS Height (m)</label>
              <input
                type="number"
                value={btsHeight}
                onChange={(e) => setBtsHeight(Number(e.target.value))}
                className="w-full px-3 py-2 bg-slate-950/60 border border-slate-850 rounded-lg text-sm text-white focus:outline-none focus:border-blue-500"
              />
            </div>
          </div>

          {/* Transmitter Power specs */}
          <details className="group border border-slate-850 rounded-lg bg-slate-950/20 overflow-hidden">
            <summary className="px-3 py-2 text-xs font-semibold text-slate-400 uppercase cursor-pointer flex justify-between items-center hover:bg-slate-950/40 transition">
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
                    onChange={(e) => setTxPowerDbm(Number(e.target.value))}
                    className="w-full px-2 py-1 bg-slate-950 border border-slate-850 rounded text-xs text-white"
                  />
                </div>
                <div className="space-y-1">
                  <label className="text-[10px] text-slate-500 uppercase">Gain (dBi)</label>
                  <input
                    type="number"
                    value={antennaGainDbi}
                    onChange={(e) => setAntennaGainDbi(Number(e.target.value))}
                    className="w-full px-2 py-1 bg-slate-950 border border-slate-850 rounded text-xs text-white"
                  />
                </div>
                <div className="space-y-1">
                  <label className="text-[10px] text-slate-500 uppercase">Loss (dB)</label>
                  <input
                    type="number"
                    value={cableLossDb}
                    onChange={(e) => setCableLossDb(Number(e.target.value))}
                    className="w-full px-2 py-1 bg-slate-950 border border-slate-850 rounded text-xs text-white"
                  />
                </div>
              </div>
              <div className="text-[10px] text-slate-400 text-right">
                Calculated EIRP: <span className="text-blue-400 font-bold">{eirpDbm.toFixed(1)} dBm</span>
              </div>
            </div>
          </details>

          {/* CPE specs */}
          <details className="group border border-slate-850 rounded-lg bg-slate-950/20 overflow-hidden">
            <summary className="px-3 py-2 text-xs font-semibold text-slate-400 uppercase cursor-pointer flex justify-between items-center hover:bg-slate-950/40 transition">
              <span>CPE client Config</span>
              <Settings className="w-3.5 h-3.5 text-slate-500 group-open:rotate-90 transition duration-300" />
            </summary>
            <div className="p-3 border-t border-slate-850 space-y-3 bg-slate-950/10">
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1">
                  <label className="text-[10px] text-slate-500 uppercase">CPE Height (m)</label>
                  <input
                    type="number"
                    value={cpeHeight}
                    onChange={(e) => setCpeHeight(Number(e.target.value))}
                    className="w-full px-2 py-1 bg-slate-950 border border-slate-850 rounded text-xs text-white"
                  />
                </div>
                <div className="space-y-1">
                  <label className="text-[10px] text-slate-500 uppercase">Rx Sens. (dBm)</label>
                  <input
                    type="number"
                    value={cpeSensitivity}
                    onChange={(e) => setCpeSensitivity(Number(e.target.value))}
                    className="w-full px-2 py-1 bg-slate-950 border border-slate-850 rounded text-xs text-white"
                  />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1">
                  <label className="text-[10px] text-slate-500 uppercase">Ant. Gain (dBi)</label>
                  <input
                    type="number"
                    value={cpeGainDbi}
                    onChange={(e) => setCpeGainDbi(Number(e.target.value))}
                    className="w-full px-2 py-1 bg-slate-950 border border-slate-850 rounded text-xs text-white"
                  />
                </div>
                <div className="space-y-1">
                  <label className="text-[10px] text-slate-500 uppercase">Cable Loss (dB)</label>
                  <input
                    type="number"
                    value={cpeCableLossDb}
                    onChange={(e) => setCpeCableLossDb(Number(e.target.value))}
                    className="w-full px-2 py-1 bg-slate-950 border border-slate-850 rounded text-xs text-white"
                  />
                </div>
              </div>
            </div>
          </details>

          {/* System Margin */}
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <label className="text-xs font-semibold text-slate-400 uppercase">System Margin (dB)</label>
              <input
                type="number"
                value={systemMarginDb}
                onChange={(e) => setSystemMarginDb(Number(e.target.value))}
                min={0}
                className="w-full px-3 py-2 bg-slate-950/60 border border-slate-850 rounded-lg text-sm text-white focus:outline-none focus:border-blue-500"
              />
            </div>
            <div className="space-y-1.5">
              <label className="text-xs font-semibold text-slate-400 uppercase">Coverage Prob.</label>
              <select
                value={coverageProbability}
                onChange={(e) => setCoverageProbability(e.target.value)}
                className="w-full px-3 py-2 bg-slate-950/60 border border-slate-850 rounded-lg text-sm text-white focus:outline-none focus:border-blue-500"
              >
                <option value="50%">50% (Median)</option>
                <option value="75%">75%</option>
                <option value="90%">90% (Standard)</option>
                <option value="95%">95% (High Reliability)</option>
                <option value="99%">99% (Pessimistic)</option>
              </select>
            </div>
          </div>

          {/* OpenTopography Key */}
          <div className="space-y-1.5">
            <label className="text-xs font-semibold text-slate-400 uppercase">OpenTopography API Key</label>
            <input
              type="password"
              placeholder="Uses server defaults if blank"
              value={srtmKey}
              onChange={(e) => setSrtmKey(e.target.value)}
              className="w-full px-3 py-2 bg-slate-950/60 border border-slate-850 rounded-lg text-sm text-white placeholder-slate-600 focus:outline-none focus:border-blue-500"
            />
          </div>
        </div>
      </div>

      {/* Rerun simulation button */}
      <div className="p-5 border-t border-slate-800 bg-slate-950/20">
        <button
          onClick={handleSimulateClick}
          disabled={isLoading || parsedSites.length === 0}
          className="w-full py-3 bg-blue-600 hover:bg-blue-700 disabled:bg-slate-800 disabled:text-slate-500 text-white rounded-xl font-semibold flex items-center justify-center gap-2 transition duration-300 shadow-lg shadow-blue-500/10 border border-blue-500/20 cursor-pointer text-sm"
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
    </aside>
  );
}
