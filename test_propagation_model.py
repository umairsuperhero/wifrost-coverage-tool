import unittest
import numpy as np
import math
from propagation import (
    bearing,
    sector_gain,
    shadowing_margin,
    water_path_loss,
    okumura_hata,
    deygout_loss,
    PathLossResult
)

class TestPropagationModel(unittest.TestCase):
    def test_bearing(self):
        # 0 degrees: due North
        self.assertAlmostEqual(bearing(0, 0, 1, 0), 0.0, places=1)
        # 90 degrees: due East
        self.assertAlmostEqual(bearing(0, 0, 0, 1), 90.0, places=1)
        # 180 degrees: due South
        self.assertAlmostEqual(bearing(1, 0, 0, 0), 180.0, places=1)
        # 270 degrees: due West
        self.assertAlmostEqual(bearing(0, 1, 0, 0), 270.0, places=1)

    def test_sector_gain(self):
        # On-axis gain: no loss
        self.assertAlmostEqual(sector_gain(45.0, 45.0, 65.0, 25.0), 0.0, places=2)
        # HPBW boundary: gain drop should be around 3 dB (specifically -3 dB)
        self.assertAlmostEqual(sector_gain(45.0, 45.0 + 32.5, 65.0, 25.0), -3.0, places=2)
        # Off-axis back-lobe boundary should clamp to front-to-back ratio
        self.assertEqual(sector_gain(0.0, 180.0, 65.0, 25.0), -25.0)

    def test_shadowing_margin(self):
        # For 50% probability, shadowing margin is 0 dB
        self.assertAlmostEqual(shadowing_margin(0.50, 6.0), 0.0, places=2)
        # For 90% probability, margin should be positive
        self.assertGreater(shadowing_margin(0.90, 6.0), 0.0)
        # For probability below 50%, it should return 0.0 (no margin)
        self.assertEqual(shadowing_margin(0.40, 6.0), 0.0)

    def test_water_path_loss(self):
        # Distance = 1 km, freq = 600 MHz, hb = 30m, hm = 3m
        loss_2ray = water_path_loss(1.0, 600.0, 30.0, 3.0)
        fspl = 20.0 * math.log10(1.0) + 20.0 * math.log10(600.0) + 32.44
        self.assertGreaterEqual(loss_2ray, fspl)

    def test_okumura_hata(self):
        # Test basic limits and environments
        loss_open = okumura_hata(2.0, 500.0, 30.0, 2.0, 'open')
        loss_suburban = okumura_hata(2.0, 500.0, 30.0, 2.0, 'suburban')
        loss_urban = okumura_hata(2.0, 500.0, 30.0, 2.0, 'urban')
        
        # Urban should have more loss than suburban, and suburban more than open
        self.assertGreater(loss_urban, loss_suburban)
        self.assertGreater(loss_suburban, loss_open)

    def test_path_loss_result(self):
        res = PathLossResult(base_db=100.0, diffraction_db=15.0, clutter_db=8.0, effective_hb_m=30.0, environment='suburban')
        # Check backward-compatible unpacking
        tot, base, diff = res
        self.assertEqual(tot, 123.0)
        self.assertEqual(base, 100.0)
        self.assertEqual(diff, 15.0)
        self.assertEqual(res.total_db, 123.0)

        # Check planning scenario loss (including clutter and 90% shadowing)
        loss_planned = res.scenario_loss(system_margin_db=10.0, coverage_probability=0.90, include_clutter=True)
        # Base (100) + Diffraction (15) + Clutter (8) + System Margin (10) + Shadowing (~1.282 * 6.0 = ~7.69)
        expected_min = 135.0
        expected_max = 145.0
        self.assertTrue(expected_min <= loss_planned <= expected_max)

    def test_deygout_loss(self):
        # A simple profile: TX at 0km, RX at 4km, peak at 2km
        profile = [
            (0.0, 100.0),
            (1.0, 100.0),
            (2.0, 200.0),  # dominant peak
            (3.0, 100.0),
            (4.0, 100.0)
        ]
        # Transmitter at 100m + 30m antenna, Receiver at 100m + 10m antenna
        h_tx_asl = 100.0 + 30.0
        h_rx_asl = 100.0 + 10.0
        loss = deygout_loss(profile, h_tx_asl, h_rx_asl, 500.0)
        self.assertGreater(loss, 0.0)
        # Verify it is capped at 30 dB
        self.assertLessEqual(loss, 30.0)

if __name__ == '__main__':
    unittest.main()
