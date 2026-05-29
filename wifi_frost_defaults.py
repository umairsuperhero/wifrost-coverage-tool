from dataclasses import dataclass, field

@dataclass
class WifrostBTS:
    manufacturer: str = "WiFrost"
    model_name: str = "LT100B"
    tx_power_dbm: float = 23.0
    antenna_gain_dbi: float = 13.0
    cable_loss_db: float = 1.5
    receiver_sensitivity_dbm: float = -104.0
    freq_min_mhz: float = 470.0
    freq_max_mhz: float = 670.0
    antenna_height_default_m: float = 30.0
    # 65° HPBW / 17° VPBW — typical WiFrost directional panel
    # NOTE: 65° × 3 sectors = 195° total, NOT full 360°
    # Use 90°+ HPBW for seamless 3-sector coverage
    beamwidth_h_deg: float = 65.0
    beamwidth_v_deg: float = 17.0
    # Sector configuration — single sector default
    default_sectors: int = 1
    sector_azimuths: list = field(default_factory=lambda: [0])
    horizontal_beamwidth: float = 65.0
    front_to_back_ratio: float = 25.0

@dataclass
class WifrostCPE:
    manufacturer: str = "WiFrost"
    model_name: str = "LT100C"
    tx_power_dbm: float = 23.0
    antenna_gain_dbi: float = 10.0
    cable_loss_db: float = 0.5
    receiver_sensitivity_dbm: float = -104.0
    freq_min_mhz: float = 470.0
    freq_max_mhz: float = 670.0
    antenna_height_default_m: float = 10.0
    beamwidth_h_deg: float = 60.0
    beamwidth_v_deg: float = 30.0
