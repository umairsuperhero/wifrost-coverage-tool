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
import LinkBudget from "../components/LinkBudget";
import CpeSummaryBar from "../components/CpeSummaryBar";
import RunSummaryBar from "../components/RunSummaryBar";
import { Compass, HelpCircle, AlertCircle, Signal, CheckCircle, AlertTriangle, X } from "lucide-react";
import axios from "axios";
import { cn } from "../lib/utils";

// One automatic retry on network/5xx errors — handles Cloud Run cold-start 503 (scales to zero)
async function axiosWithRetry(fn: () => Promise<any>, delayMs = 4000): Promise<any> {
  try {
    return await fn();
  } catch (err: any) {
    const status = err?.response?.status;
    if (!status || status === 503 || status === 502) {
      await new Promise((r) => setTimeout(r, delayMs));
      return await fn();
    }
    throw err;
  }
}

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
  terrain_loaded?: boolean;
  landcover_loaded?: boolean;
  landcover_summary?: Record<string, number>;
  environment_used?: string;
  environment_auto?: boolean;
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
  const [showResultsPanel, setShowResultsPanel] = useState<boolean>(false);
  const [isTerrainModalOpen, setIsTerrainModalOpen] = useState<boolean>(false);
  const [isLeftExpanded, setIsLeftExpanded] = useState<boolean>(true);
  const [resultsTab, setResultsTab] = useState<"overview" | "clients" | "link">("overview");

  // Loading States
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [isProfileLoading, setIsProfileLoading] = useState<boolean>(false);
  const [slowStart, setSlowStart] = useState(false);

  // Run tracking — lets the user see WHAT was run and WHEN it last re-ran.
  const [runCount, setRunCount] = useState<number>(0);
  const [lastRunAt, setLastRunAt] = useState<Date | null>(null);
  const [prevCoverage, setPrevCoverage] = useState<number | null>(null);

  // Live sector state — updated immediately when user adjusts compass rose (no re-sim needed)
  const [liveSector, setLiveSector] = useState<{ azimuths: number[]; hpbw: number }>({ azimuths: [0], hpbw: 65 });

  // Map Toolbar & Premium Controls States
  const [mapMode, setMapMode] = useState<"normal" | "measure" | "addcpe">("normal");
  const [manualCpeCount, setManualCpeCount] = useState<number>(0);
  const [hoverPoint, setHoverPoint] = useState<[number, number] | null>(null);
  const [mapOpacity, setMapOpacity] = useState<number>(0.45);
  const [mapTheme, setMapTheme] = useState<"dark" | "satellite" | "street">("dark");
  const [measurePoints, setMeasurePoints] = useState<[number, number][]>([]);

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
    setShowResultsPanel(true);
    setResultsTab("link");
    setIsProfileLoading(true);

    let activeBtsIdx = btsIndexOverride !== undefined ? btsIndexOverride : selectedBtsIndex;
    if (activeBtsIdx === -1 && cpe.serving_bts_index !== undefined) {
      activeBtsIdx = cpe.serving_bts_index;
    }
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
  }, [selectedBtsIndex, parsedData.sites, activeSimulationParams, setResultsTab, setShowResultsPanel]);

  const handleSimulate = useCallback(async (params: any, overrideSites?: any[]) => {
    setIsLoading(true);
    setSlowStart(false);
    setTerrainProfile(null);
    setSelectedCpe(null);
    const sitesToUse = overrideSites || parsedData.sites;
    const slowTimer = setTimeout(() => setSlowStart(true), 8000);
    try {
      // 1. Run simulation (retry once on cold-start 503/network error)
      const simRes = await axiosWithRetry(() => axios.post(`${API_BASE}/api/simulate`, {
        site_index: params.site_index,
        frequency_mhz: params.frequency_mhz,
        eirp_dbm: params.eirp_dbm,
        system_margin_db: params.system_margin_db,
        coverage_probability: params.coverage_probability,
        model: params.model,
        environment: params.environment,
        srtm_key: params.srtm_key || null,
        sites: sitesToUse,
        polygons: parsedData.polygons,
        lines: parsedData.lines,
        bts_height: params.bts_height,
        cpe_height: params.cpe_height,
        cpe_sensitivity: params.cpe_sensitivity,
        sector_azimuths: params.sector_azimuths,
        hpbw_deg: params.hpbw_deg,
        vpbw_deg: params.vpbw_deg,
        front_to_back_db: params.front_to_back_db,
      }));

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
        sites: sitesToUse,
        polygons: parsedData.polygons,
        lines: parsedData.lines,
        bts_height: params.bts_height,
        cpe_height: params.cpe_height,
        cpe_sensitivity: params.cpe_sensitivity,
        // Full RF params kept so ad-hoc CPE re-analysis (P2MP) uses identical inputs.
        tx_power_dbm: params.tx_power_dbm,
        antenna_gain_dbi: params.antenna_gain_dbi,
        cable_loss_db: params.cable_loss_db,
        rx_gain_dbi: params.rx_gain_dbi,
        rx_cable_loss_db: params.rx_cable_loss_db,
        rx_sensitivity_dbm: params.rx_sensitivity_dbm,
        sector_azimuths: params.sector_azimuths,
        hpbw_deg: params.hpbw_deg,
        vpbw_deg: params.vpbw_deg,
        front_to_back_db: params.front_to_back_db,
      };

      setActiveSimulationParams(simulationParamsContext);
      setSimulationResults(simRes.data);
      setShowResultsPanel(true);
      setResultsTab("overview");
      setSelectedBtsIndex(params.site_index);

      // Record this run so the UI can show what was run, when, and how it
      // changed from the previous run.
      const newCov = simRes.data?.stats?.coverage_pct;
      setRunCount((n) => {
        const next = n + 1;
        if (typeof newCov === "number") {
          if (n > 0 && prevCoverage !== null) {
            const delta = newCov - prevCoverage;
            const arrow = delta > 0.05 ? "▲" : delta < -0.05 ? "▼" : "→";
            showToast(
              `Re-run #${next} complete · ${newCov.toFixed(1)}% reliable ${arrow} ${delta >= 0 ? "+" : ""}${delta.toFixed(1)} pts`,
              "success"
            );
          } else {
            showToast(`Simulation complete · ${newCov.toFixed(1)}% reliable coverage`, "success");
          }
        }
        return next;
      });
      if (typeof newCov === "number") setPrevCoverage(newCov);
      setLastRunAt(new Date());

      // 2. Run CPE Link Margin Analysis (no retry needed — server already warm from step 1)
      const cpeRes = await axios.post(`${API_BASE}/api/cpe-analysis`, {
        bts_index: params.site_index,
        sites: sitesToUse,
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
        system_margin_db: params.system_margin_db,
        sector_azimuths: params.sector_azimuths,
        hpbw_deg: params.hpbw_deg,
        front_to_back_db: params.front_to_back_db,
      });

      setCpeResults(cpeRes.data.cpe_results);

      // 3. Automatically fetch the first CPE's terrain profile
      if (cpeRes.data.cpe_results.length > 0) {
        const firstCpe = cpeRes.data.cpe_results[0];
        setSelectedCpe(firstCpe);
        setIsProfileLoading(true);
        
        const activeBtsIdx = params.site_index;
        const btsCandidates = sitesToUse.filter((s) => s.is_bts_candidate);
        let activeBts = btsCandidates[activeBtsIdx] || sitesToUse[0];
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
            sites: sitesToUse,
          });
          setTerrainProfile(profileRes.data);
        }
        setIsProfileLoading(false);
      }
    } catch (err) {
      console.error("Simulation failed:", err);
      showToast("Error running simulation. Please verify backend connection.", "error");
    } finally {
      clearTimeout(slowTimer);
      setIsLoading(false);
      setSlowStart(false);
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

  const handleMoveBts = useCallback((index: number, lat: number, lng: number) => {
    const updatedSites = [...parsedData.sites];
    const btsCandidates = updatedSites.filter((s) => s.is_bts_candidate);
    if (index >= 0 && index < btsCandidates.length) {
      const actualIdx = updatedSites.indexOf(btsCandidates[index]);
      if (actualIdx !== -1) {
        updatedSites[actualIdx] = {
          ...updatedSites[actualIdx],
          latitude: Number(lat),
          longitude: Number(lng),
        };
      }
    }
    
    setParsedData((prev) => ({ ...prev, sites: updatedSites }));
    showToast("Tower relocated. Recalculating coverage...", "success");

    // Automatically trigger simulation recalculation on drag release
    if (activeSimulationParams) {
      handleSimulate({
        ...activeSimulationParams,
        site_index: index,
      }, updatedSites);
    }
  }, [parsedData.sites, activeSimulationParams, handleSimulate, showToast]);

  // Re-run ONLY the CPE link budget (the coverage grid depends on the BTS, which
  // is unchanged) for a given sites list — used for ad-hoc CPE drops (P2MP).
  const runCpeAnalysisOnly = useCallback(async (sitesForAnalysis: Site[]) => {
    const p = activeSimulationParams;
    if (!p) return;
    const cpeRes = await axios.post(`${API_BASE}/api/cpe-analysis`, {
      bts_index: p.site_index,
      sites: sitesForAnalysis,
      frequency_mhz: p.frequency_mhz,
      model: p.model,
      environment: p.environment,
      bts_height: p.bts_height,
      tx_power_dbm: p.tx_power_dbm ?? 23.0,
      antenna_gain_dbi: p.antenna_gain_dbi ?? 13.0,
      cable_loss_db: p.cable_loss_db ?? 1.5,
      rx_gain_dbi: p.rx_gain_dbi ?? 10.0,
      rx_cable_loss_db: p.rx_cable_loss_db ?? 0.5,
      rx_sensitivity_dbm: p.rx_sensitivity_dbm ?? p.cpe_sensitivity ?? -94.0,
      system_margin_db: p.system_margin_db,
      sector_azimuths: p.sector_azimuths ?? [0],
      hpbw_deg: p.hpbw_deg ?? 65.0,
      front_to_back_db: p.front_to_back_db ?? 25.0,
    });
    setCpeResults(cpeRes.data.cpe_results);
    return cpeRes.data.cpe_results as CpeResult[];
  }, [activeSimulationParams]);

  // Click-to-drop an ad-hoc CPE on the map, then re-run the P2MP link budget.
  const handleAddCpe = useCallback(async (lat: number, lng: number) => {
    if (!activeSimulationParams) {
      showToast("Run a simulation first, then drop CPE sites to analyze.", "warning");
      return;
    }
    const n = manualCpeCount + 1;
    setManualCpeCount(n);
    const newCpe: Site = {
      name: `Manual CPE ${n}`,
      latitude: Number(lat.toFixed(6)),
      longitude: Number(lng.toFixed(6)),
      is_bts_candidate: false,
      height_m: activeSimulationParams.cpe_height ?? 10.0,
      site_type: "CPE",
    };
    const updatedSites = [...parsedData.sites, newCpe];
    setParsedData((prev) => ({ ...prev, sites: updatedSites }));
    try {
      const results = await runCpeAnalysisOnly(updatedSites);
      const added = results?.find((c) => c.name === newCpe.name);
      if (added) {
        await handleSelectCpe(added);
        showToast(`${newCpe.name}: ${added.status} (${added.rssi_dbm} dBm)`, "success");
      }
    } catch (err) {
      console.error("Failed to analyze dropped CPE:", err);
      showToast("Failed to analyze the dropped CPE.", "error");
    }
  }, [activeSimulationParams, manualCpeCount, parsedData.sites, runCpeAnalysisOnly, handleSelectCpe, showToast]);

  // Remove all ad-hoc (manually dropped) CPEs and re-run the link budget.
  const handleClearManualCpes = useCallback(async () => {
    const cleaned = parsedData.sites.filter((s) => !/^Manual CPE /.test(s.name));
    setParsedData((prev) => ({ ...prev, sites: cleaned }));
    setManualCpeCount(0);
    try {
      await runCpeAnalysisOnly(cleaned);
      showToast("Cleared manually-added CPE sites.", "success");
    } catch {
      /* non-fatal */
    }
  }, [parsedData.sites, runCpeAnalysisOnly, showToast]);

  useEffect(() => {
    if (measurePoints.length === 2) {
      const fetchCustomMeasureProfile = async () => {
        setIsProfileLoading(true);
        try {
          const res = await axios.post(`${API_BASE}/api/terrain-profile`, {
            bts_latitude: measurePoints[0][0],
            bts_longitude: measurePoints[0][1],
            bts_height: activeSimulationParams?.bts_height || 30.0,
            cpe_latitude: measurePoints[1][0],
            cpe_longitude: measurePoints[1][1],
            cpe_height: activeSimulationParams?.cpe_height || 10.0,
            frequency_mhz: activeSimulationParams?.frequency_mhz || 600.0,
            cpe_name: "Measured Path",
            sites: parsedData.sites,
          });
          setTerrainProfile(res.data);
          setSelectedCpe({
            name: "Measured Path",
            distance_km: res.data.profile?.[res.data.profile.length - 1]?.distance_km || 0.0,
            elevation_m: res.data.cpe_elevation || 0.0,
            rssi_dbm: 0.0,
            margin_db: 0.0,
            status: res.data.label || "Clear line of sight",
            latitude: measurePoints[1][0],
            longitude: measurePoints[1][1],
          });
        } catch (err) {
          console.error("Failed to fetch custom terrain profile:", err);
          showToast("Failed to fetch terrain elevation profile for measured path.", "error");
        } finally {
          setIsProfileLoading(false);
        }
      };
      fetchCustomMeasureProfile();
    }
  }, [measurePoints, activeSimulationParams, parsedData.sites, showToast]);

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
      setShowResultsPanel(true);
      setResultsTab("overview");
      
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
          system_margin_db: params.system_margin_db ?? 18.0,
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
      <div className="absolute top-24 bottom-6 left-6 z-20 pointer-events-none">
        <Sidebar
          onFileParsed={handleFileParsed}
          onSimulate={handleSimulate}
          isLoading={isLoading}
          parsedSites={parsedData.sites}
          onSectorChange={(azimuths, hpbw) => setLiveSector({ azimuths, hpbw })}
          onLoadHistoryRun={handleLoadHistoryRun}
          showToast={showToast}
          isExpanded={isLeftExpanded}
          onToggleExpanded={setIsLeftExpanded}
          terrainLoaded={simulationResults?.stats?.terrain_loaded}
        />
      </div>

      {/* Edge-to-Edge Map Background */}
      <div className="fixed inset-0 z-0 pointer-events-auto">
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
            simulationResults && selectedBtsIndex !== -1
              ? {
                  azimuths: liveSector.azimuths,
                  hpbw: liveSector.hpbw,
                  radiusKm: simulationResults.stats.max_range_km ?? 2.0,
                }
              : null
          }
          onMoveBts={handleMoveBts}
          onAddCpe={handleAddCpe}
          mapMode={mapMode}
          setMapMode={setMapMode}
          hoverPoint={hoverPoint}
          opacity={mapOpacity}
          setOpacity={setMapOpacity}
          mapTheme={mapTheme}
          setMapTheme={setMapTheme}
          measurePoints={measurePoints}
          setMeasurePoints={setMeasurePoints}
          isSidebarExpanded={isLeftExpanded}
        />
      </div>

      {/* Right Dashboard Area (Overlays) */}
      <main className="absolute inset-0 pointer-events-none z-10 flex pt-24">
        {/* Spacer for sidebar */}
        <div className="w-[320px] shrink-0 ml-6" /> 
        
        <div className="flex-1 flex flex-col h-full relative">
          {parsedData.sites.length > 0 && (
            /* Results HUD (Right-Aligned Glass Panel) */
            <div className="absolute top-24 bottom-6 right-6 z-20 flex items-stretch gap-4 pointer-events-none">
              
              {/* The Panel */}
              <div
                className={`transition-all duration-500 ease-[cubic-bezier(0.16,1,0.3,1)] overflow-hidden h-full pointer-events-auto flex flex-col ${
                  showResultsPanel ? "w-[360px] opacity-100 scale-100" : "w-0 opacity-0 scale-95 origin-right"
                }`}
              >
                <aside className="w-[360px] glass-panel rounded-3xl flex flex-col h-full overflow-hidden shrink-0">
                  {/* Header */}
                  <div className="p-5 flex justify-between items-center border-b border-white/5 shrink-0 bg-transparent">
                    <h2 className="text-[13px] font-bold text-white uppercase tracking-wider flex items-center gap-2">
                      <Signal className="w-4 h-4 text-emerald-400" />
                      Simulation Results
                    </h2>
                    <button
                      onClick={() => setShowResultsPanel(false)}
                      className="p-1.5 rounded-full text-slate-400 hover:text-white hover:bg-white/10 transition-all duration-300"
                    >
                      <X className="w-5 h-5" />
                    </button>
                  </div>

                  {/* Tabs bar */}
                  {simulationResults && (
                    <div className="px-5 pt-4 shrink-0 bg-transparent">
                      <div className="flex glass-panel rounded-xl p-0.5 gap-0.5">
                        <button
                          onClick={() => setResultsTab("overview")}
                          className={`flex-1 py-1.5 text-xs font-semibold rounded-lg transition-all duration-300 cursor-pointer ${
                            resultsTab === "overview"
                              ? "bg-white/10 text-white shadow-sm"
                              : "text-slate-400 hover:text-white"
                          }`}
                        >
                          Overview
                        </button>
                        <button
                          onClick={() => setResultsTab("clients")}
                          className={`flex-1 py-1.5 text-xs font-semibold rounded-lg transition-all duration-300 cursor-pointer ${
                            resultsTab === "clients"
                              ? "bg-white/10 text-white shadow-sm"
                              : "text-slate-400 hover:text-white"
                          }`}
                        >
                          Clients
                        </button>
                        <button
                          onClick={() => setResultsTab("link")}
                          className={`flex-1 py-1.5 text-xs font-semibold rounded-lg transition-all duration-300 cursor-pointer ${
                            resultsTab === "link"
                              ? "bg-white/10 text-white shadow-sm"
                              : "text-slate-400 hover:text-white"
                          }`}
                        >
                          Path Link
                        </button>
                      </div>
                    </div>
                  )}

                  {/* Body */}
                  <div className="flex-1 overflow-y-auto overflow-x-hidden p-5 pb-10 space-y-5 custom-scrollbar">
                    {isLoading && slowStart && (
                      <div className="flex flex-col items-center gap-2 text-center bg-transparent rounded-2xl p-4 border border-white/10">
                        <p className="text-sm text-amber-400 font-medium drop-shadow-[0_0_8px_rgba(251,191,36,0.6)]">⏳ Still working…</p>
                        <p className="text-xs text-slate-300">
                          Large areas or many sites take longer to compute.
                        </p>
                      </div>
                    )}
                    
                    {simulationResults && (
                      <>
                        {/* Tab 1: Overview */}
                        {resultsTab === "overview" && (
                          <div className="space-y-5">
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
                            <MetricsRow
                              threeScenarios={simulationResults.three_scenarios}
                              activeScenarioName={activeScenario}
                              onScenarioChange={setActiveScenario}
                            />
                            <RunSummaryBar
                              runCount={runCount}
                              lastRunAt={lastRunAt}
                              isLoading={isLoading}
                              projectName={fileName.replace(/\.[^/.]+$/, "")}
                              btsName={
                                selectedBtsIndex === -1
                                  ? "All towers"
                                  : parsedData.sites.filter((s) => s.is_bts_candidate)[selectedBtsIndex]?.name
                              }
                              frequencyMhz={activeSimulationParams?.frequency_mhz}
                              model={activeSimulationParams?.model}
                              environment={simulationResults.stats.environment_used ?? activeSimulationParams?.environment}
                              environmentAuto={simulationResults.stats.environment_auto}
                              eirpDbm={activeSimulationParams?.eirp_dbm}
                              systemMarginDb={activeSimulationParams?.system_margin_db}
                              terrainLoaded={simulationResults.stats.terrain_loaded}
                              landcoverLoaded={simulationResults.stats.landcover_loaded}
                            />
                          </div>
                        )}

                        {/* Tab 2: Clients */}
                        {resultsTab === "clients" && (
                          <div className="space-y-5">
                            {/* P2MP / manual-CPE controls */}
                            <div className="flex items-center justify-between gap-3 flex-wrap">
                              <button
                                onClick={() => setMapMode(mapMode === "addcpe" ? "normal" : "addcpe")}
                                className={`inline-flex items-center gap-2 text-[11px] uppercase tracking-wider font-semibold px-4 py-1.5 rounded-full border transition-all duration-300 ${
                                  mapMode === "addcpe"
                                    ? "bg-blue-500/20 border-blue-500/50 text-blue-200 shadow-[0_0_12px_rgba(59,130,246,0.3)]"
                                    : "bg-white/5 border-white/10 text-white/70 hover:text-white hover:bg-white/10"
                                }`}
                                title="Toggle add-CPE mode, then click the map to drop client sites for point-to-multipoint analysis"
                              >
                                📍 {mapMode === "addcpe" ? "Click map to drop CPE…" : "Add CPE (P2MP)"}
                              </button>
                              {manualCpeCount > 0 && (
                                <button
                                  onClick={handleClearManualCpes}
                                  className="text-[11px] uppercase tracking-wider font-semibold px-4 py-1.5 rounded-full border border-white/10 bg-white/5 text-white/40 hover:text-red-300 hover:border-red-500/30 hover:bg-red-500/10 transition-all duration-300"
                                >
                                  Clear {manualCpeCount} manual CPE{manualCpeCount > 1 ? "s" : ""}
                                </button>
                              )}
                            </div>

                            {cpeResults.length === 0 && (
                              <div className="p-6 border border-white/5 bg-white/5 rounded-xl text-center text-white/50">
                                <p className="text-sm font-semibold">No clients loaded.</p>
                                <p className="text-xs mt-1 text-white/40">Import client sites via CSV/KMZ or use the Add CPE button above to drop points on the map.</p>
                              </div>
                            )}

                            {/* CPE Summary Bar — only when CPE results exist */}
                            {cpeResults.length > 0 && (
                              <CpeSummaryBar cpeResults={cpeResults} />
                            )}

                            {/* CPE Table — only when CPE results exist */}
                            {cpeResults.length > 0 && (
                              <CpeTable
                                cpeResults={cpeResults}
                                selectedCpeName={selectedCpe?.name || null}
                                onSelectCpe={(cpe) => handleSelectCpe(cpe)}
                                sectorCount={activeSimulationParams?.sector_azimuths?.length ?? 1}
                              />
                            )}
                          </div>
                        )}

                        {/* Tab 3: Path Link */}
                        {resultsTab === "link" && (
                          <div className="space-y-5">
                            {!selectedCpe && (
                              <div className="p-6 border border-white/5 bg-white/5 rounded-xl text-center text-white/50">
                                <p className="text-sm font-semibold">No active link.</p>
                                <p className="text-xs mt-1 text-white/40">Select a client on the map or in the Clients tab to view its detailed Path Link and Terrain Profile.</p>
                              </div>
                            )}

                            {selectedCpe && (
                              <div className="bg-white/[0.02] border border-white/10 rounded-2xl p-4 flex items-center justify-between text-xs">
                                <span className="font-semibold text-white">Active Link: {selectedCpe.name}</span>
                                <span className="text-[10px] text-slate-400 bg-white/5 border border-white/10 rounded-full px-2 py-0.5">
                                  Serving BTS: {selectedCpe.serving_bts_name || "Tower"}
                                </span>
                              </div>
                            )}

                            {/* Elevation profile chart */}
                            {isProfileLoading ? (
                              <div className="bg-black/40 backdrop-blur-3xl rounded-xl border border-white/5 p-5 flex flex-col items-center justify-center h-[340px] text-white/40">
                                <span className="w-8 h-8 rounded-full border-2 border-blue-500 border-t-transparent animate-spin mb-2 drop-shadow-[0_0_8px_rgba(59,130,246,0.6)]" />
                                <p className="text-[11px] uppercase tracking-wider font-semibold">Generating terrain profile...</p>
                              </div>
                            ) : (
                              (() => {
                                const btsCandidates = parsedData.sites.filter((s) => s.is_bts_candidate);
                                const activeBtsForProfile = selectedBtsIndex === -1 && selectedCpe?.serving_bts_index !== undefined
                                  ? btsCandidates[selectedCpe.serving_bts_index]
                                  : btsCandidates[selectedBtsIndex];

                                const btsLatForProfile = selectedCpe?.name === "Measured Path" && measurePoints.length > 0
                                  ? measurePoints[0][0]
                                  : activeBtsForProfile?.latitude;
                                const btsLonForProfile = selectedCpe?.name === "Measured Path" && measurePoints.length > 0
                                  ? measurePoints[0][1]
                                  : activeBtsForProfile?.longitude;

                                return (
                                  <TerrainChart
                                    profileData={terrainProfile?.profile || []}
                                    label={terrainProfile?.label || ""}
                                    isFlat={terrainProfile?.is_flat || false}
                                    cpeName={selectedCpe?.name || "CPE"}
                                    btsElevation={terrainProfile?.bts_elevation}
                                    cpeElevation={terrainProfile?.cpe_elevation}
                                    btsTotalHeight={terrainProfile?.bts_total_height}
                                    cpeTotalHeight={terrainProfile?.cpe_total_height}
                                    btsLat={btsLatForProfile}
                                    btsLon={btsLonForProfile}
                                    cpeLat={selectedCpe?.latitude}
                                    cpeLon={selectedCpe?.longitude}
                                    onHoverPoint={setHoverPoint}
                                    onMaximize={() => setIsTerrainModalOpen(true)}
                                  />
                                );
                              })()
                            )}

                            {/* Link Budget Panel */}
                            <LinkBudget
                              txPowerDbm={activeSimulationParams?.tx_power_dbm ?? 23.0}
                              antennaGainDbi={activeSimulationParams?.antenna_gain_dbi ?? 13.0}
                              cableLossDb={activeSimulationParams?.cable_loss_db ?? 1.5}
                              cpeGainDbi={activeSimulationParams?.rx_gain_dbi ?? 10.0}
                              cpeCableLossDb={activeSimulationParams?.rx_cable_loss_db ?? 0.5}
                              cpeSensitivityDbm={activeSimulationParams?.cpe_sensitivity ?? -92.0}
                              systemMarginDb={activeSimulationParams?.system_margin_db ?? 10.0}
                              frequencyMhz={activeSimulationParams?.frequency_mhz ?? 600.0}
                              maxRangeKm={simulationResults.stats.max_range_km ?? null}
                            />
                          </div>
                        )}
                      </>
                    )}
                  </div>
                </aside>
          </div>

          {/* Right Ornament (Toggle Button) */}
          {simulationResults && (
            <div className="flex flex-col items-center gap-4 glass-panel rounded-full p-2 py-4 pointer-events-auto shadow-[0_8px_32px_rgba(0,0,0,0.4)] transition-all duration-300">
              <button
                onClick={() => setShowResultsPanel(!showResultsPanel)}
                title="Toggle Results Panel"
                className={`p-3 rounded-full transition-all duration-300 ${
                  showResultsPanel ? "bg-emerald-600 shadow-[0_0_15px_rgba(16,185,129,0.5)] text-white" : "text-slate-400 hover:text-white hover:bg-white/10 animate-pulse"
                }`}
              >
                <Signal className="w-5 h-5" />
              </button>
            </div>
          )}
        </div>
      )}
    </div>
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

      {/* Maximize Terrain Chart Modal Overlay */}
      {isTerrainModalOpen && (
        <div className="fixed inset-0 z-[9999] bg-black/60 backdrop-blur-md flex items-center justify-center p-4 sm:p-6 md:p-8">
          <div className="bg-slate-950/90 border border-white/10 rounded-[2rem] p-6 shadow-[0_0_50px_rgba(0,0,0,0.6)] w-full max-w-4xl relative backdrop-blur-2xl animate-fade-in-up">
            <button
              onClick={() => setIsTerrainModalOpen(false)}
              className="absolute top-4 right-4 p-2 rounded-full text-slate-400 hover:text-white hover:bg-white/10 transition-all cursor-pointer"
            >
              <X className="w-5 h-5" />
            </button>
            <div className="mt-2">
              {(() => {
                const btsCandidates = parsedData.sites.filter((s) => s.is_bts_candidate);
                const activeBtsForProfile = selectedBtsIndex === -1 && selectedCpe?.serving_bts_index !== undefined
                  ? btsCandidates[selectedCpe.serving_bts_index]
                  : btsCandidates[selectedBtsIndex];

                const btsLatForProfile = selectedCpe?.name === "Measured Path" && measurePoints.length > 0
                  ? measurePoints[0][0]
                  : activeBtsForProfile?.latitude;
                const btsLonForProfile = selectedCpe?.name === "Measured Path" && measurePoints.length > 0
                  ? measurePoints[0][1]
                  : activeBtsForProfile?.longitude;

                return (
                  <TerrainChart
                    profileData={terrainProfile?.profile || []}
                    label={terrainProfile?.label || ""}
                    isFlat={terrainProfile?.is_flat || false}
                    cpeName={selectedCpe?.name || "CPE"}
                    btsElevation={terrainProfile?.bts_elevation}
                    cpeElevation={terrainProfile?.cpe_elevation}
                    btsTotalHeight={terrainProfile?.bts_total_height}
                    cpeTotalHeight={terrainProfile?.cpe_total_height}
                    btsLat={btsLatForProfile}
                    btsLon={btsLonForProfile}
                    cpeLat={selectedCpe?.latitude}
                    cpeLon={selectedCpe?.longitude}
                    onHoverPoint={setHoverPoint}
                  />
                );
              })()}
            </div>
          </div>
        </div>
      )}
    </Layout>
  );
}
