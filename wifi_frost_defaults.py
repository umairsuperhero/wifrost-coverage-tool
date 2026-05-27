from dataclasses import dataclass

@dataclass
class WifrostBTS:
    manufacturer: str = "WiFrost"  # Source: Page 1, Page 2 footer "©2022 WIFROST INC"
    model_name: str = "LT100B"  # Source: Page 1 header "PRODUCT BRIEF LT100B / LT100C", Page 2 "LT100B Basestation Specifications"
    tx_power_dbm: float = 23.0  # Source: Page 2 "Radio: 23dBm RF power per antenna"
    antenna_gain_dbi: float = 13.0  # Source: Page 2 "Radio: 36dBM EIRP (with external 13dBi panel antenna)"
    cable_loss_db: float = 0.0  # Source: Page 2 "Calculated from 36dBm EIRP - 23dBm TX power - 13dBi antenna gain = 0dB loss"
    receiver_sensitivity_dbm: float = -104.0  # Source: Page 2 "Radio: -104dBm Sensitivity"
    freq_min_mhz: float = 470.0  # Source: Page 2 "Operation: Operating Band: TV White Space band; 470 - 670MHz"
    freq_max_mhz: float = 670.0  # Source: Page 2 "Operation: Operating Band: TV White Space band; 470 - 670MHz"
    antenna_height_default_m: float = 30.0  # Source: Industry default for TVWS base station towers (not explicitly in PDF)
    beamwidth_h_deg: float = 90.0  # Source: Industry default for TVWS sector panel antennas (not explicitly in PDF)
    beamwidth_v_deg: float = 15.0  # Source: Industry default for TVWS sector panel antennas (not explicitly in PDF)

@dataclass
class WifrostCPE:
    manufacturer: str = "WiFrost"  # Source: Page 1, Page 2 footer "©2022 WIFROST INC"
    model_name: str = "LT100C"  # Source: Page 1 header "PRODUCT BRIEF LT100B / LT100C", Page 2 "LT100C Client Specifications"
    tx_power_dbm: float = 23.0  # Source: Page 2 "Radio: 23dBm RF power per antenna"
    antenna_gain_dbi: float = 10.0  # Source: Page 2 "Radio: 33dBm EIRP (with integrated 10dBi antenna)"
    cable_loss_db: float = 0.0  # Source: Page 2 "Calculated from 33dBm EIRP - 23dBm TX power - 10dBi antenna gain = 0dB loss (integrated)"
    receiver_sensitivity_dbm: float = -104.0  # Source: Page 2 "Radio: -104dBm Sensitivity"
    freq_min_mhz: float = 470.0  # Source: Page 2 "Operation: Operating Band: TV White Space band; 470 - 670MHz"
    freq_max_mhz: float = 670.0  # Source: Page 2 "Operation: Operating Band: TV White Space band; 470 - 670MHz"
    antenna_height_default_m: float = 10.0  # Source: Industry default for TVWS CPE customer premises poles (not explicitly in PDF)
    beamwidth_h_deg: float = 60.0  # Source: Industry default for CPE integrated patch directional antennas (not explicitly in PDF)
    beamwidth_v_deg: float = 30.0  # Source: Industry default for CPE integrated patch directional antennas (not explicitly in PDF)
