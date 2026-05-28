"use client";

import React, { useState, useEffect } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";
import Layout from "../components/Layout";
import Sidebar from "../components/Sidebar";
import MapView from "../components/MapView";
import ResultsBanner from "../components/ResultsBanner";
import MetricsRow from "../components/MetricsRow";
import CpeTable from "../components/CpeTable";
import TerrainChart from "../components/TerrainChart";
import ModelInfoPanel from "../components/ModelInfoPanel";
import { Compass, HelpCircle, AlertCircle, Signal } from "lucide-react";
import axios from "axios";

export default function Home() {
  // Layout file data
  const [parsedData, setParsedData] = useState<{
    sites: any[];
    polygons: any[];
    lines: any[];
  }>({
    sites: [],
    polygons: [],
    lines: [],
  });
  const [fileName, setFileName] = useState<string>("");

  // Selection states
  const [selectedBtsIndex, setSelectedBtsIndex] = useState<number>(0);
  const [selectedCpe, setSelectedCpe] = useState<any | null>(null);

  // Simulation parameters & results
  const [activeSimulationParams, setActiveSimulationParams] = useState<any | null>(null);
  const [simulationResults, setSimulationResults] = useState<any | null>(null);
  const [cpeResults, setCpeResults] = useState<any[]>([]);
  const [terrainProfile, setTerrainProfile] = useState<any | null>(null);

  // View States
  const [activeScenario, setActiveScenario] = useState<"best" | "realistic" | "conservative">("realistic");
  const [activeTab, setActiveTab] = useState<"analysis" | "model">("analysis");

  // Loading States
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [isProfileLoading, setIsProfileLoading] = useState<boolean>(false);

  const handleFileParsed = (data: { sites: any[]; polygons: any[]; lines: any[] }, name: string) => {
    setParsedData(data);
    setFileName(name);
    setSimulationResults(null);
    setCpeResults([]);
    setSelectedCpe(null);
    setTerrainProfile(null);
  };

  const handleSimulate = async (params: any) => {
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
        handleSelectCpe(
          firstCpe,
          params.site_index,
          params.bts_height,
          params.cpe_height,
          params.frequency_mhz,
          params.model
        );
      }
    } catch (err) {
      console.error("Simulation failed:", err);
      alert("Error running simulation. Please verify backend connection.");
    } finally {
      setIsLoading(false);
    }
  };

  const handleSelectCpe = async (
    cpe: any,
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
    if (!activeBts) return;

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
  };

  const handleSelectBtsMap = (index: number) => {
    setSelectedBtsIndex(index);
    // If we have active simulation params, re-run with new BTS
    if (activeSimulationParams) {
      handleSimulate({
        ...activeSimulationParams,
        site_index: index,
      });
    }
  };

  return (
    <Layout>
      {/* Sidebar - controls & parameters */}
      <Sidebar
        onFileParsed={handleFileParsed}
        onSimulate={handleSimulate}
        isLoading={isLoading}
        parsedSites={parsedData.sites}
      />

      {/* Right Dashboard Area */}
      <main className="flex-1 flex flex-col h-full overflow-hidden bg-[#0A0D14]">
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
            {/* Top half: Map View */}
            <div className="h-[45%] w-full border-b border-slate-800 relative min-h-[300px]">
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
                  />

                  {/* Scenarios comparative Row */}
                  <MetricsRow
                    threeScenarios={simulationResults.three_scenarios}
                    activeScenarioName={activeScenario}
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
    </Layout>
  );
}
