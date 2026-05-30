"use client";

import React, { useState, useEffect, useCallback } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";
import Layout from "../components/Layout";
import Sidebar from "../components/Sidebar";
import MapView from "../components/MapView";
import ResultsBanner from "../components/ResultsBanner";
import MetricsRow from "../components/MetricsRow";
import CpeTable, { CpeResult } from "../components/CpeTable";
import TerrainChart from "../components/TerrainChart";
import ModelInfoPanel from "../components/ModelInfoPanel";
import { Compass, HelpCircle, AlertCircle, Signal, CheckCircle, AlertTriangle } from "lucide-react";
import axios from "axios";

export interface Site {
  name: string;
  latitude: number;
  longitude: number;
  description?: string;
  is_bts_candidate: boolean;
  height_m?: number;
  site_type?: string;
}

export interface ParsedData {
  sites: Site[];
  polygons: any[];
  lines: any[];
}

export interface SimulationStats {
  coverage_pct: number;
  good_pct: number;
  excellent_pct: number;
  avg_rssi: number;
  max_range_km: number;
  total_area_km2: number;
}

export interface ScenarioStats {
  coverage_pct: number;
  good_pct: number;
  avg_rssi: number;
}

export interface SimulationResults {
  stats: SimulationStats;
  plain_english_result: string;
  coverage_geojson: any;
  three_scenarios: {
    best: ScenarioStats;
    realistic: ScenarioStats;
    conservative: ScenarioStats;
  };
}

export interface ProfilePoint {
  distance_km: number;
  terrain_m: number;
  los_m: number;
  fresnel_lower_m: number;
  fresnel_upper_m: number;
}

export interface TerrainProfileData {
  profile: ProfilePoint[];
  label: string;
  is_flat: boolean;
  bts_elevation?: number;
  cpe_elevation?: number;
  bts_total_height?: number;
  cpe_total_height?: number;
}

export interface SimulationParams {
  site_index: number;
  frequency_mhz: number;
  eirp_dbm: number;
  system_margin_db: number;
  coverage_probability: string;
  model: string;
  environment: string;
  srtm_key: string | null;
  sites: Site[];
  polygons: any[];
  lines: any[];
  bts_height: number;
  cpe_height: number;
  cpe_sensitivity: number;
  tx_power_dbm?: number;
  antenna_gain_dbi?: number;
  cable_loss_db?: number;
  rx_gain_dbi?: number;
  rx_cable_loss_db?: number;
  rx_sensitivity_dbm?: number;
  sector_azimuths?: number[];
  hpbw_deg?: number;
  front_to_back_db?: number;
}

export default function Home() {
  // Layout file data
  const [parsedData, setParsedData] = useState<ParsedData>({
    sites: [],
    polygons: [],
    lines: [],
  });
  const [fileName, setFileName] = useState<string>("");

  // Selection states
  const [selectedBtsIndex, setSelectedBtsIndex] = useState<number>(0);
  const [selectedCpe, setSelectedCpe] = useState<CpeResult | null>(null);

  // Simulation parameters & results
  const [activeSimulationParams, setActiveSimulationParams] = useState<SimulationParams | null>(null);
  const [simulationResults, setSimulationResults] = useState<SimulationResults | null>(null);
  const [cpeResults, setCpeResults] = useState<CpeResult[]>([]);
  const [terrainProfile, setTerrainProfile] = useState<TerrainProfileData | null>(null);

  // View States
  const [activeScenario, setActiveScenario] = useState<"best" | "realistic" | "conservative">("realistic");
  const [activeTab, setActiveTab] = useState<"analysis" | "model">("analysis");

  // Loading States
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [isProfileLoading, setIsProfileLoading] = useState<boolean>(false);

  // Live sector state — updated immediately when user adjusts compass rose (no re-sim needed)
  const [liveSector, setLiveSector] = useState<{ azimuths: number[]; hpbw: number }>({ azimuths: [0], hpbw: 65 });

  // Toast State
  const [toast, setToast] = useState<{ message: string; type: "success" | "error" | "warning" } | null>(null);

  const showToast = useCallback((message: string, type: "success" | "error" | "warning" = "success") => {
    setToast({ message, type });
  }, []);

  useEffect(() => {
    if (toast) {
      const timer = setTimeout(() => setToast(null), 4000);
      return () => clearTimeout(timer);
    }
  }, [toast]);

  const handleFileParsed = useCallback((data: ParsedData, name: string) => {
    setParsedData(data);
    setFileName(name);
    setSimulationResults(null);
    setCpeResults([]);
    setSelectedCpe(null);
    setTerrainProfile(null);
  }, []);

  const handleSelectCpe = useCallback(async (
    cpe: CpeResult,
    btsIndexOverride?: number,
    btsHeightOverride?: number,
    cpeHeightOverride?: number,
    frequencyOverride?: number,
    modelOverride?: string
  ) => {
    setSelectedCpe(cpe);
    setIsProfileLoading(true);

    const activeBtsIdx = btsIndexOverride !== undefined ? btsIndexOverride : selectedBtsIndex;
    const btsCandidates = parsedData.sites.filter((s) => s.is_bts_candidate);
    
    let activeBts = btsCandidates[activeBtsIdx];
    if (!activeBts && parsedData.sites.length > 0) {
      activeBts = parsedData.sites[0];
    }
    if (!activeBts) {
      setIsProfileLoading(false);
      return;
    }

    try {
      const res = await axios.post(`${API_BASE}/api/terrain-profile`, {
        bts_latitude: activeBts.latitude,
        bts_longitude: activeBts.longitude,
        bts_height: btsHeightOverride !== undefined ? btsHeightOverride : (activeSimulationParams?.bts_height || 30.0),
        cpe_latitude: cpe.latitude,
        cpe_longitude: cpe.longitude,
        cpe_height: cpeHeightOverride !== undefined ? cpeHeightOverride : (activeSimulationParams?.cpe_height || 10.0),
        frequency_mhz: frequencyOverride !== undefined ? frequencyOverride : (activeSimulationParams?.frequency_mhz || 600.0),
        cpe_name: cpe.name,
        sites: parsedData.sites,
      });
      setTerrainProfile(res.data);
    } catch (err) {
      console.error("Failed to fetch terrain profile:", err);
    } finally {
      setIsProfileLoading(false);
    }
  }, [selectedBtsIndex, parsedData.sites, activeSimulationParams]);

  const handleSimulate = useCallback(async (params: any) => {
    setIsLoading(true);
    setTerrainProfile(null);
    setSelectedCpe(null);
    try {
      // 1. Run simulation
      const simRes = await axios.post(`${API_BASE}/api/simulate`, {
        site_index: params.site_index,
        frequency_mhz: params.frequency_mhz,
        eirp_dbm: params.eirp_dbm,
        system_margin_db: params.system_margin_db,
        coverage_probability: params.coverage_probability,
        model: params.model,
        environment: params.environment,
        srtm_key: params.srtm_key || null,
        sites: parsedData.sites,
        polygons: parsedData.polygons,
        lines: parsedData.lines,
        bts_height: params.bts_height,
        cpe_height: params.cpe_height,
        cpe_sensitivity: params.cpe_sensitivity,
      });

      // Save active simulation parameters for report generation
      const simulationParamsContext = {
        site_index: params.site_index,
        frequency_mhz: params.frequency_mhz,
        eirp_dbm: params.eirp_dbm,
        system_margin_db: params.system_margin_db,
        coverage_probability: params.coverage_probability,
        model: params.model,
        environment: params.environment,
        srtm_key: params.srtm_key || null,
        sites: parsedData.sites,
        polygons: parsedData.polygons,
        lines: parsedData.lines,
        bts_height: params.bts_height,
        cpe_height: params.cpe_height,
        cpe_sensitivity: params.cpe_sensitivity,
      };
      
      setActiveSimulationParams(simulationParamsContext);
      setSimulationResults(simRes.data);
      setSelectedBtsIndex(params.site_index);

      // 2. Run CPE Link Margin Analysis
      const cpeRes = await axios.post(`${API_BASE}/api/cpe-analysis`, {
        bts_index: params.site_index,
        sites: parsedData.sites,
        frequency_mhz: params.frequency_mhz,
        model: params.model,
        environment: params.environment,
        bts_height: params.bts_height,
        tx_power_dbm: params.tx_power_dbm,
        antenna_gain_dbi: params.antenna_gain_dbi,
        cable_loss_db: params.cable_loss_db,
        rx_gain_dbi: params.rx_gain_dbi,
        rx_cable_loss_db: params.rx_cable_loss_db,
        rx_sensitivity_dbm: params.rx_sensitivity_dbm,
      });

      setCpeResults(cpeRes.data.cpe_results);

      // 3. Automatically fetch the first CPE's terrain profile
      if (cpeRes.data.cpe_results.length > 0) {
        const firstCpe = cpeRes.data.cpe_results[0];
        setSelectedCpe(firstCpe);
        setIsProfileLoading(true);
        
        const activeBtsIdx = params.site_index;
        const btsCandidates = parsedData.sites.filter((s) => s.is_bts_candidate);
        let activeBts = btsCandidates[activeBtsIdx] || parsedData.sites[0];
        if (activeBts) {
          const profileRes = await axios.post(`${API_BASE}/api/terrain-profile`, {
            bts_latitude: activeBts.latitude,
            bts_longitude: activeBts.longitude,
            bts_height: params.bts_height,
            cpe_latitude: firstCpe.latitude,
            cpe_longitude: firstCpe.longitude,
            cpe_height: params.cpe_height,
            frequency_mhz: params.frequency_mhz,
            cpe_name: firstCpe.name,
            sites: parsedData.sites,
          });
          setTerrainProfile(profileRes.data);
        }
        setIsProfileLoading(false);
      }
    } catch (err) {
      console.error("Simulation failed:", err);
      showToast("Error running simulation. Please verify backend connection.", "error");
    } finally {
      setIsLoading(false);
    }
  }, [parsedData.sites, parsedData.polygons, parsedData.lines, showToast]);

  const handleSelectBtsMap = useCallback((index: number) => {
    setSelectedBtsIndex(index);
    // If we have active simulation params, re-run with new BTS
    if (activeSimulationParams) {
      handleSimulate({
        ...activeSimulationParams,
        site_index: index,
      });
    }
  }, [activeSimulationParams, handleSimulate]);

  const handleLoadHistoryRun = useCallback(async (runId: string) => {
    setIsLoading(true);
    setTerrainProfile(null);
    setSelectedCpe(null);
    try {
      const res = await axios.get(`${API_BASE}/api/history/${runId}`);
      const run = res.data;
      
      const params = run.params_json;
      const stats = run.stats_json;
      const result = run.result_json;
      const geojson = run.geojson;
      
      // Update parsed data from saved run
      setParsedData({
        sites: params.sites || [],
        polygons: params.polygons || [],
        lines: params.lines || [],
      });
      setFileName(run.project || "WiFrost Project");
      setSelectedBtsIndex(params.site_index || 0);
      setActiveSimulationParams(params);
      
      setSimulationResults({
        coverage_geojson: geojson,
        stats: stats,
        plain_english_result: result.plain_english_result,
        three_scenarios: result.three_scenarios
      });
      
      // Load CPE results on the fly
      try {
        const cpeRes = await axios.post(`${API_BASE}/api/cpe-analysis`, {
          bts_index: params.site_index,
          sites: params.sites,
          frequency_mhz: params.frequency_mhz,
          model: params.model,
          environment: params.environment,
          bts_height: params.bts_height,
          tx_power_dbm: params.tx_power_dbm ?? 23.0,
          antenna_gain_dbi: params.antenna_gain_dbi ?? 13.0,
          cable_loss_db: params.cable_loss_db ?? 1.5,
          rx_gain_dbi: params.rx_gain_dbi ?? 10.0,
          rx_cable_loss_db: params.rx_cable_loss_db ?? 0.5,
          rx_sensitivity_dbm: params.rx_sensitivity_dbm ?? -104.0,
          sector_azimuths: params.sector_azimuths ?? [0],
          hpbw_deg: params.hpbw_deg ?? 65.0,
          front_to_back_db: params.front_to_back_db ?? 25.0
        });
        setCpeResults(cpeRes.data.cpe_results);
        
        if (cpeRes.data.cpe_results.length > 0) {
          // Select the first CPE to display terrain profile
          const firstCpe = cpeRes.data.cpe_results[0];
          setSelectedCpe(firstCpe);
          setIsProfileLoading(true);
          
          const btsCandidates = (params.sites || []).filter((s: any) => s.is_bts_candidate);
          let activeBts = btsCandidates[params.site_index];
          if (!activeBts && (params.sites || []).length > 0) {
            activeBts = params.sites[0];
          }
          
          if (activeBts) {
            const profileRes = await axios.post(`${API_BASE}/api/terrain-profile`, {
              bts_latitude: activeBts.latitude,
              bts_longitude: activeBts.longitude,
              bts_height: params.bts_height,
              cpe_latitude: firstCpe.latitude,
              cpe_longitude: firstCpe.longitude,
              cpe_height: params.cpe_height,
              frequency_mhz: params.frequency_mhz,
              cpe_name: firstCpe.name,
              sites: params.sites,
            });
            setTerrainProfile(profileRes.data);
          }
          setIsProfileLoading(false);
        }
      } catch (cpeErr) {
        console.error("Failed to run CPE analysis for historical run:", cpeErr);
        setCpeResults([]);
        setIsProfileLoading(false);
      }
      showToast("Successfully loaded simulation: " + (run.project || "WiFrost Project"), "success");
    } catch (err) {
      console.error("Failed to load historical run:", err);
      showToast("Failed to load historical simulation.", "error");
    } finally {
      setIsLoading(false);
    }
  }, [showToast]);

  const margin_real = activeSimulationParams?.system_margin_db ?? 15.0;
  const margin_best = Math.max(0.0, margin_real - 5.0);
  const margin_cons = margin_real + 5.0;
  const sensitivity = activeSimulationParams?.cpe_sensitivity ?? -104.0;

  let activeThreshold = sensitivity + margin_real;
  if (activeScenario === "best") {
    activeThreshold = sensitivity + margin_best;
  } else if (activeScenario === "conservative") {
    activeThreshold = sensitivity + margin_cons;
  }

  return (
    <Layout>
      {/* Sidebar - controls & parameters */}
      <Sidebar
        onFileParsed={handleFileParsed}
        onSimulate={handleSimulate}
        isLoading={isLoading}
        parsedSites={parsedData.sites}
        onSectorChange={(azimuths, hpbw) => setLiveSector({ azimuths, hpbw })}
        onLoadHistoryRun={handleLoadHistoryRun}
        showToast={showToast}
      />

      {/* Right Dashboard Area */}
      <main className="flex-1 flex flex-col h-full overflow-hidden bg-[#0F1117]">
        {parsedData.sites.length === 0 ? (
          /* Empty State */
          <div className="flex-1 flex flex-col items-center justify-center p-8 text-center text-slate-400">
            <div className="p-4 bg-slate-900/60 border border-slate-800 rounded-2xl flex items-center justify-center mb-4">
              <Compass className="w-12 h-12 text-blue-500 animate-spin-slow" />
            </div>
            <h2 className="text-xl font-bold text-white mb-1">No Project Loaded</h2>
            <p className="text-sm text-slate-500 max-w-sm">
              Please upload a KMZ, KML, or Excel file on the sidebar to parse candidate tower locations and customer sites.
            </p>
          </div>
        ) : (
          /* Dashboard Layout */
          <div className="flex-1 flex flex-col overflow-hidden">
            {/* Map View — 60% height, wedges update live from compass rose */}
            <div className="h-[60%] w-full border-b border-slate-800 relative min-h-[360px]">
              <MapView
                sites={parsedData.sites}
                polygons={parsedData.polygons}
                lines={parsedData.lines}
                coverageGeojson={simulationResults?.coverage_geojson}
                cpeResults={cpeResults}
                selectedBtsIndex={selectedBtsIndex}
                onSelectBts={handleSelectBtsMap}
                selectedCpeName={selectedCpe?.name || null}
                onSelectCpe={(cpe) => handleSelectCpe(cpe)}
                activeScenario={activeScenario}
                activeThreshold={activeThreshold}
                sectorInfo={
                  simulationResults
                    ? {
                        azimuths: liveSector.azimuths,
                        hpbw: liveSector.hpbw,
                        radiusKm: simulationResults.stats.max_range_km ?? 2.0,
                      }
                    : null
                }
              />
            </div>

            {/* Bottom half: Results & Configuration Details */}
            <div className="flex-1 overflow-y-auto p-6 space-y-6">
              {simulationResults ? (
                <>
                  {/* Results summary banner */}
                  <ResultsBanner
                    plainEnglishResult={simulationResults.plain_english_result}
                    coveragePct={simulationResults.stats.coverage_pct}
                    projectName={fileName.replace(/\.[^/.]+$/, "")}
                    activeSimulationParams={activeSimulationParams}
                    stats={simulationResults.stats}
                    threeScenarios={simulationResults.three_scenarios}
                    cpeResults={cpeResults}
                    showToast={showToast}
                  />

                  {/* Scenarios comparative Row */}
                  <MetricsRow
                    threeScenarios={simulationResults.three_scenarios}
                    activeScenarioName={activeScenario}
                    onScenarioChange={setActiveScenario}
                  />

                  {/* Details Tabs */}
                  <div className="space-y-4">
                    <div className="flex border-b border-slate-800 pb-px gap-6">
                      <button
                        onClick={() => setActiveTab("analysis")}
                        className={`pb-2.5 text-sm font-semibold border-b-2 transition ${
                          activeTab === "analysis"
                            ? "border-blue-500 text-blue-400 font-bold"
                            : "border-transparent text-slate-400 hover:text-slate-200"
                        }`}
                      >
                        Client Analysis &amp; Elevation Profile
                      </button>
                      <button
                        onClick={() => setActiveTab("model")}
                        className={`pb-2.5 text-sm font-semibold border-b-2 transition ${
                          activeTab === "model"
                            ? "border-blue-500 text-blue-400 font-bold"
                            : "border-transparent text-slate-400 hover:text-slate-200"
                        }`}
                      >
                        Propagation Theory &amp; Formulas
                      </button>
                    </div>

                    {activeTab === "analysis" ? (
                      <div className="grid grid-cols-1 xl:grid-cols-2 gap-6 items-start">
                        {/* CPE Table */}
                        <CpeTable
                          cpeResults={cpeResults}
                          selectedCpeName={selectedCpe?.name || null}
                          onSelectCpe={(cpe) => handleSelectCpe(cpe)}
                          sectorCount={activeSimulationParams?.sector_azimuths?.length ?? 1}
                        />

                        {/* Elevation profile chart */}
                        {isProfileLoading ? (
                          <div className="bg-slate-900/60 rounded-xl border border-slate-800 p-5 flex flex-col items-center justify-center h-[340px] text-slate-400">
                            <span className="w-8 h-8 rounded-full border-2 border-blue-500 border-t-transparent animate-spin mb-2" />
                            <p className="text-sm">Generating terrain profile...</p>
                          </div>
                        ) : (
                          <TerrainChart
                            profileData={terrainProfile?.profile || []}
                            label={terrainProfile?.label || ""}
                            isFlat={terrainProfile?.is_flat || false}
                            cpeName={selectedCpe?.name || "CPE"}
                            btsElevation={terrainProfile?.bts_elevation}
                            cpeElevation={terrainProfile?.cpe_elevation}
                            btsTotalHeight={terrainProfile?.bts_total_height}
                            cpeTotalHeight={terrainProfile?.cpe_total_height}
                          />
                        )}
                      </div>
                    ) : (
                      /* Model Panel */
                      <ModelInfoPanel
                        modelType={activeSimulationParams?.model || "terrain_aware"}
                        frequencyMhz={activeSimulationParams?.frequency_mhz || 600.0}
                      />
                    )}
                  </div>
                </>
              ) : (
                /* Post-load, Pre-simulation Help Message */
                <div className="p-6 bg-slate-900/40 border border-slate-800 rounded-xl flex items-start gap-4">
                  <div className="p-3 bg-blue-600/10 border border-blue-500/20 text-blue-400 rounded-lg">
                    <Signal className="w-6 h-6 animate-pulse" />
                  </div>
                  <div className="space-y-1">
                    <h3 className="font-semibold text-white">Layout loaded successfully</h3>
                    <p className="text-sm text-slate-400 leading-relaxed">
                      Your layout file <b>{fileName}</b> contains <b>{parsedData.sites.length} sites</b> and{" "}
                      <b>{parsedData.polygons.length} boundary polygons</b>.
                    </p>
                    <p className="text-sm text-slate-500 leading-relaxed mt-2">
                      Choose an active BTS tower in the dropdown list, adjust equipment specifications, and click <b>Run Simulation</b> on the sidebar to compute coverage maps, path loss, and link budgets.
                    </p>
                  </div>
                </div>
              )}
            </div>
          </div>
        )}
      </main>

      {/* Slide-in Toast Notification */}
      {toast && (
        <div className={`fixed bottom-6 right-6 z-[9999] flex items-center gap-3 px-4 py-3 rounded-xl border shadow-2xl backdrop-blur-md transition-all duration-300 animate-fade-in-up ${
          toast.type === "success"
            ? "bg-emerald-950/95 border-emerald-500/30 text-emerald-200"
            : toast.type === "error"
            ? "bg-red-950/95 border-red-500/30 text-red-200"
            : "bg-amber-950/95 border-amber-500/30 text-amber-200"
        }`}>
          {toast.type === "success" && <CheckCircle className="w-5 h-5 text-emerald-400" />}
          {toast.type === "error" && <AlertCircle className="w-5 h-5 text-red-400" />}
          {toast.type === "warning" && <AlertTriangle className="w-5 h-5 text-amber-400" />}
          <span className="text-sm font-semibold text-white">{toast.message}</span>
        </div>
      )}
    </Layout>
  );
}
