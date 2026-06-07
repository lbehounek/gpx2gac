"""Tests for gpx2gac converter.

Expected values hand-verified against FlightContest's GPX2GAC.groovy semantics
and the reference output of "Flight Contest GPX GAC Converter 1.0".
"""
import sys
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from gpx2gac import (
    calculate_leg,
    convert,
    gac_altitude_str,
    gac_date_str,
    gac_groundspeed_str,
    gac_latitude_str,
    gac_longitude_str,
    gac_time_str,
    round_grad,
)

SAMPLE_GPX = """<?xml version="1.0" encoding="utf-8"?>
<gpx xmlns="http://www.topografix.com/GPX/1/1" creator="test" version="1.1">
<trk><name>Test</name><trkseg>
<trkpt lat="50.0" lon="13.0"><ele>304.8</ele><time>2026-06-07T10:00:00.00000Z</time></trkpt>
<trkpt lat="50.0" lon="13.001"><ele>304.8</ele><time>2026-06-07T10:00:01.00000Z</time></trkpt>
<trkpt lat="50.001" lon="13.001"><ele>152.4</ele><time>2026-06-07T10:00:03.00000Z</time></trkpt>
</trkseg></trk>
</gpx>
"""

EXPECTED_GAC = "\n".join([
    "ABHT000:000_1",
    "HFDTE070626",
    "HPPLTPILOT:UNKNOWN",
    "HPGTYAIRCRAFTTYPE:UNKNOWN",
    "HPGIDAIRCRAFTID:UNKNOWN",
    "HFDTM100GPSDATUM:WGS84",
    "HFRFWFIRMWAREVERSION:GPX2GAC CONVERTER 1.0",
    "HFRHWHARDWAREVERSION:UNKNOWN",
    "HFFTYFRTYPE:gpx2gac,GPX GAC Converter 1.0",
    "HFGPS:UNKNOWN" + " ",  # trailing space matches AFLOS output
    "I033639GSP4042TRT4346FXA",
    "B1000005000000N01300000EA999990100000000009999",
    "B1000015000000N01300060EA999990100013880909999",
    "B1000035000060N01300060EA999990050010800009999",
    "GGPX2GACNOSECURITY",
    "",
])


class TestFieldFormatters(unittest.TestCase):
    def test_time_str_with_fractional_seconds(self):
        self.assertEqual(gac_time_str("2026-06-07T08:40:37.00000Z"), "084037")

    def test_time_str_plain(self):
        self.assertEqual(gac_time_str("2010-08-28T09:39:32Z"), "093932")

    def test_date_str_ddmmyy(self):
        # matches AFLOS logger convention: HFDTE280810 = 28 Aug 2010
        self.assertEqual(gac_date_str("2010-08-28T09:39:32Z"), "280810")
        self.assertEqual(gac_date_str("2026-06-07T08:40:37.00000Z"), "070626")

    def test_latitude_north(self):
        # 50.09647613 deg -> 50 deg 5.789' -> 5005789N
        self.assertEqual(gac_latitude_str(Decimal("50.09647613065206")), "5005789N")

    def test_latitude_south(self):
        self.assertEqual(gac_latitude_str(Decimal("-50.09647613065206")), "5005789S")

    def test_longitude_east(self):
        # 13.69083297 deg -> 13 deg 41.450' -> 01341450E
        self.assertEqual(gac_longitude_str(Decimal("13.69083296645892")), "01341450E")

    def test_longitude_west(self):
        self.assertEqual(gac_longitude_str(Decimal("-13.69083296645892")), "01341450W")

    def test_minute_rollover_carries_into_degrees(self):
        # 49.9999999 deg -> minutes round to 60.000 -> must carry, not emit 4960000N
        self.assertEqual(gac_latitude_str(Decimal("49.9999999")), "5000000N")

    def test_altitude_meters_to_feet(self):
        # 384.1758 m * 3.2808 = 1260.48 ft
        self.assertEqual(gac_altitude_str(Decimal("384.1758224945515")), "01260")

    def test_altitude_uses_groovy_factor(self):
        # 304.8 m * 3.2808 = 999.988 -> 01000 (factor 3.2808, not 3.28084)
        self.assertEqual(gac_altitude_str(Decimal("304.8")), "01000")

    def test_groundspeed_tenths_of_knots(self):
        self.assertEqual(gac_groundspeed_str(19.97), "0200")
        self.assertEqual(gac_groundspeed_str(0), "0000")
        self.assertEqual(gac_groundspeed_str(999.9), "9999")


class TestLegMath(unittest.TestCase):
    def test_due_east(self):
        dis, direction = calculate_leg(50.0, 13.001, 50.0, 13.0)
        self.assertEqual(round(direction), 90)
        # 0.06' of longitude at 50N = 0.06 * cos(50 deg) NM
        self.assertAlmostEqual(dis, 0.038567, places=5)

    def test_due_north(self):
        dis, direction = calculate_leg(50.001, 13.0, 50.0, 13.0)
        self.assertEqual(round(direction), 0)
        self.assertAlmostEqual(dis, 0.06, places=9)

    def test_round_grad_wraps_360_to_0(self):
        self.assertEqual(round_grad(359.5), 0)
        self.assertEqual(round_grad(0.4), 0)
        self.assertEqual(round_grad(89.6), 90)


class TestEndToEnd(unittest.TestCase):
    def test_convert_sample_track(self):
        with tempfile.TemporaryDirectory() as tmp:
            gpx_path = Path(tmp) / "sample.gpx"
            gac_path = Path(tmp) / "sample.gac"
            gpx_path.write_text(SAMPLE_GPX)

            n = convert(str(gpx_path), str(gac_path))

            self.assertEqual(n, 3)
            self.assertEqual(gac_path.read_text(), EXPECTED_GAC)

    def test_all_b_records_are_46_chars(self):
        with tempfile.TemporaryDirectory() as tmp:
            gpx_path = Path(tmp) / "sample.gpx"
            gac_path = Path(tmp) / "sample.gac"
            gpx_path.write_text(SAMPLE_GPX)
            convert(str(gpx_path), str(gac_path))
            for line in gac_path.read_text().splitlines():
                if line.startswith("B"):
                    self.assertEqual(len(line), 46, line)

    def test_header_record_sequence_matches_aflos(self):
        # strict parsers expect the AFLOS logger record sequence
        with tempfile.TemporaryDirectory() as tmp:
            gpx_path = Path(tmp) / "sample.gpx"
            gac_path = Path(tmp) / "sample.gac"
            gpx_path.write_text(SAMPLE_GPX)
            convert(str(gpx_path), str(gac_path), pilot="Novak Jan")
            lines = gac_path.read_text().splitlines()
            prefixes = ["A", "HFDTE", "HPPLT", "HPGTY", "HPGID", "HFDTM",
                        "HFRFW", "HFRHW", "HFFTY", "HFGPS", "I", "B"]
            for line, prefix in zip(lines, prefixes):
                self.assertTrue(line.startswith(prefix), f"{line!r} !~ {prefix}")
            self.assertEqual(lines[2], "HPPLTPILOT:Novak Jan")

    def test_output_uses_crlf_line_endings(self):
        # known-working AFLOS logger files are CRLF; PrecisWin is Windows software
        with tempfile.TemporaryDirectory() as tmp:
            gpx_path = Path(tmp) / "sample.gpx"
            gac_path = Path(tmp) / "sample.gac"
            gpx_path.write_text(SAMPLE_GPX)
            convert(str(gpx_path), str(gac_path))
            raw = gac_path.read_bytes()
            self.assertEqual(raw.count(b"\r\n"), raw.count(b"\n"))
            self.assertTrue(raw.endswith(b"\r\n"))

    def test_rejects_multiple_tracks(self):
        multi = SAMPLE_GPX.replace(
            "</trk>\n</gpx>", "</trk><trk><trkseg/></trk>\n</gpx>"
        )
        with tempfile.TemporaryDirectory() as tmp:
            gpx_path = Path(tmp) / "multi.gpx"
            gpx_path.write_text(multi)
            with self.assertRaises(SystemExit):
                convert(str(gpx_path), str(Path(tmp) / "multi.gac"))


if __name__ == "__main__":
    unittest.main()
