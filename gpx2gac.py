#!/usr/bin/env python3
"""GPX -> GAC converter for FlightContest / PrecisWin precision flying scoring.

B-record math is a faithful Python port of FlightContest's GPX2GAC.groovy
(Thomas Weise, Deutscher Praezisionsflug-Verein e.V., converter version 1.0).
The header mirrors the record sequence of real AFLOS logger files
(A, HFDTE, HPPLT, HPGTY, HPGID, HFDTM, HFRFW, HFRHW, HFFTY, HFGPS, I),
which strict parsers expect.

B record: B HHMMSS DDMMmmm[NS] DDDMMmmm[EW] A 99999 AAAAA(ft) GGGG(0.1kt) TTT(deg) 9999

Usage: python3 gpx2gac.py [--pilot NAME] input.gpx [output.gac]

Derivative work of FlightContest (https://flightcontest.de),
Copyright Thomas Weise, Deutscher Praezisionsflug-Verein e.V., GPL-3.0.
This port: Copyright 2026 Lukas Behounek. Licensed under GPL-3.0-or-later.
"""
import argparse
import math
import sys
from decimal import Decimal, ROUND_HALF_EVEN

try:
    # Hardened against XXE / entity-expansion bombs ("billion laughs") when
    # available: pip install defusedxml (or: pip install 'gpx2gac[secure]')
    from defusedxml.ElementTree import parse as xml_parse
except ImportError:
    # Stdlib fallback keeps the script zero-dependency. Acceptable when
    # converting your own logger's GPX output; install defusedxml if you
    # process GPX files from untrusted sources.
    from xml.etree.ElementTree import parse as xml_parse  # nosemgrep: python.lang.security.use-defused-xml.use-defused-xml

CONVERTER_VERSION = "1.0"
GACFORMAT_DEF = "I033639GSP4042TRT4346FXA"
FT_PER_METER = Decimal("3.2808")  # matches GPX2GAC.groovy, not 3.28084


def localname(tag):
    return tag.rsplit("}", 1)[-1]


def find_child_text(elem, name):
    for child in elem:
        if localname(child.tag) == name:
            return child.text or ""
    return None


def gac_time_str(gpx_time):
    # yyyy-mm-ddThh:mm:ss[.frac]Z -> hhmmss (substring, like the original)
    return gpx_time[11:13] + gpx_time[14:16] + gpx_time[17:19]


def gac_date_str(gpx_time):
    # yyyy-mm-ddThh:mm:ss[.frac]Z -> DDMMYY for the HFDTE record
    return gpx_time[8:10] + gpx_time[5:7] + gpx_time[2:4]


def _coord_str(value, deg_width):
    # DecimalFormat("00.000") semantics: HALF_EVEN rounding of minutes,
    # decimal separator stripped.
    negative = value < 0
    if negative:
        value = -value
    grad = int(value)
    minute = (value - grad) * 60
    minute_q = minute.quantize(Decimal("0.001"), rounding=ROUND_HALF_EVEN)
    if minute_q >= 60:  # carry (original would emit 60000; guard instead)
        minute_q -= 60
        grad += 1
    minute_str = f"{minute_q:06.3f}".replace(".", "")
    return negative, f"{grad:0{deg_width}d}{minute_str}"


def gac_latitude_str(lat):
    neg, body = _coord_str(lat, 2)
    return body + ("S" if neg else "N")


def gac_longitude_str(lon):
    neg, body = _coord_str(lon, 3)
    return body + ("W" if neg else "E")


def gac_altitude_str(altitude_meter):
    feet = (FT_PER_METER * altitude_meter).quantize(Decimal("1"), rounding=ROUND_HALF_EVEN)
    return f"{int(feet):05d}"


def gac_groundspeed_str(groundspeed_kt):
    tenth = (Decimal(groundspeed_kt) * 10).quantize(Decimal("1"), rounding=ROUND_HALF_EVEN)
    return f"{int(tenth):04d}"


def calculate_leg(dest_lat, dest_lon, src_lat, src_lon):
    # Equirectangular approximation, dis in NM, dir 0..359.999 (AviationMath.calculateLeg)
    lat_dist = 60 * (dest_lat - src_lat)
    lon_dist = 60 * (dest_lon - src_lon) * math.cos(math.radians((dest_lat + src_lat) / 2))
    dis = math.sqrt(lat_dist * lat_dist + lon_dist * lon_dist)
    direction = math.degrees(math.atan2(lon_dist, lat_dist)) % 360
    return dis, direction


def round_grad(grad_value):
    g = int(Decimal(grad_value).quantize(Decimal("1"), rounding=ROUND_HALF_EVEN))
    return g % 360


def parse_time_seconds(gpx_time):
    return int(gpx_time[11:13]) * 3600 + int(gpx_time[14:16]) * 60 + int(gpx_time[17:19])


def convert(gpx_path, gac_path, pilot="UNKNOWN", aircraft_type="UNKNOWN", aircraft_id="UNKNOWN"):
    root = xml_parse(gpx_path).getroot()  # nosemgrep: python.lang.security.use-defused-xml-parse.use-defused-xml-parse
    tracks = [e for e in root if localname(e.tag) == "trk"]
    if len(tracks) != 1:
        raise SystemExit(f"Error: expected exactly 1 track, found {len(tracks)}")
    trk = tracks[0]

    track_points = [
        pt
        for seg in trk
        if localname(seg.tag) == "trkseg"
        for pt in seg
        if localname(pt.tag) == "trkpt"
    ]

    # Header mirrors the record sequence of real AFLOS logger files, which
    # strict parsers expect. Identity values stay honest: this is a converted
    # GPX track, not a sealed logger recording.
    lines = ["ABHT000:000_1"]
    if track_points:
        first_time = find_child_text(track_points[0], "time")
        lines.append(f"HFDTE{gac_date_str(first_time)}")
    lines += [
        f"HPPLTPILOT:{pilot}",
        f"HPGTYAIRCRAFTTYPE:{aircraft_type}",
        f"HPGIDAIRCRAFTID:{aircraft_id}",
        "HFDTM100GPSDATUM:WGS84",
        f"HFRFWFIRMWAREVERSION:GPX2GAC CONVERTER {CONVERTER_VERSION}",
        "HFRHWHARDWAREVERSION:UNKNOWN",
        f"HFFTYFRTYPE:gpx2gac,GPX GAC Converter {CONVERTER_VERSION}",
        "HFGPS:UNKNOWN ",  # trailing space matches AFLOS output byte-for-byte
        GACFORMAT_DEF,
    ]

    last_lat = last_lon = last_secs = None
    for pt in track_points:
        time_text = find_child_text(pt, "time")
        utc = gac_time_str(time_text)
        lat = Decimal(pt.get("lat"))
        lon = Decimal(pt.get("lon"))
        ele = Decimal(find_child_text(pt, "ele") or "0")
        secs = parse_time_seconds(time_text)

        truetrack = "000"
        groundspeed = 0.0
        if last_lat is not None:
            dis, direction = calculate_leg(float(lat), float(lon), float(last_lat), float(last_lon))
            truetrack = f"{round_grad(direction):03d}"
            # original assumes 1 Hz fixes (dis * 3600); divide by actual dt for robustness
            dt = secs - last_secs
            if dt <= 0:
                dt = 1
            groundspeed = min(dis * 3600 / dt, 999.9)

        lines.append(
            f"B{utc}{gac_latitude_str(lat)}{gac_longitude_str(lon)}"
            f"A99999{gac_altitude_str(ele)}{gac_groundspeed_str(groundspeed)}{truetrack}9999"
        )
        last_lat, last_lon, last_secs = lat, lon, secs

    # G security record: real loggers sign the track cryptographically; a
    # converter can't, so write an openly-invalid placeholder for structural
    # parity (same approach as GPSBabel)
    lines.append("GGPX2GACNOSECURITY")

    # CRLF: matches real logger files (AFLOS) and the Windows-native original
    # converter; PrecisWin-era software may not tolerate bare LF
    with open(gac_path, "w", newline="") as f:
        f.write("\r\n".join(lines) + "\r\n")
    return len(track_points)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Convert a GPX track to GAC for precision/rally flying scoring software."
    )
    parser.add_argument("gpx_file", help="input GPX file")
    parser.add_argument("gac_file", nargs="?", help="output GAC file (default: <input>.gac)")
    parser.add_argument("--pilot", default="UNKNOWN", help="pilot name for the HPPLT record")
    parser.add_argument("--aircraft-type", default="UNKNOWN", help="aircraft type for the HPGTY record")
    parser.add_argument("--aircraft-id", default="UNKNOWN", help="aircraft registration for the HPGID record")
    args = parser.parse_args(argv)

    gac_file = args.gac_file or args.gpx_file.rsplit(".", 1)[0] + ".gac"
    n = convert(args.gpx_file, gac_file, args.pilot, args.aircraft_type, args.aircraft_id)
    print(f"Converted {n} track points -> {gac_file}")


if __name__ == "__main__":
    main()
