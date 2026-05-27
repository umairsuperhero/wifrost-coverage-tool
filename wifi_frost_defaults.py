from dataclasses import dataclass, field

@dataclass
class WifrostBTS:
    manufacturer: str = "WiFrost"
    model_name: str = "LT100B"
    tx_power_dbm: float = 23.0
    antenna_gain_dbi: float = 13.0
    cable_loss_db: float = 0.0
    receiver_sensitivity_dbm: float = -104.0
    freq_min_mhz: float = 470.0
    freq_max_mhz: float = 670.0
    antenna_height_default_m: float = 30.0
    beamwidth_h_deg: float = 90.0
    beamwidth_v_deg: float = 15.0
    # Sector configuration
    default_sectors: int = 3
    sector_azimuths: list = field(default_factory=lambda: [0, 120, 240])
    horizontal_beamwidth: float = 90.0
    front_to_back_ratio: float = 25.0

@dataclass
class WifrostCPE:
    manufacturer: str = "WiFrost"
    model_name: str = "LT100C"
    tx_power_dbm: float = 23.0
    antenna_gain_dbi: float = 10.0
    cable_loss_db: float = 0.0
    receiver_sensitivity_dbm: float = -104.0
    freq_min_mhz: float = 470.0
    freq_max_mhz: float = 670.0
    antenna_height_default_m: float = 10.0
    beamwidth_h_deg: float = 60.0
    beamwidth_v_deg: float = 30.0
