# gpx2gac

GPX → GAC track converter for precision flying / rally flying scoring software
(FlightContest, PrecisWin).

Converts a GPX track log (e.g. from the myTracks iPhone app or any GPS logger)
into the GAC format consumed by [FlightContest](https://flightcontest.de) and
similar FAI GAC competition scoring tools.

## Usage

```bash
python3 gpx2gac.py flight.gpx              # writes flight.gac
python3 gpx2gac.py flight.gpx output.gac   # explicit output path
python3 gpx2gac.py --pilot "Novak Jan" --aircraft-type C152 --aircraft-id OK-ABC flight.gpx
```

No dependencies — Python 3 stdlib only.

## Output format

The header mirrors the record sequence of real **AFLOS** logger files (the
BeHeTec loggers used at FAI GAC competitions), which strict parsers expect;
the B-record math is a faithful port of **Flight Contest GPX GAC Converter
1.0** (Thomas Weise, Deutscher Präzisionsflug-Verein e.V. — `GPXGAC5.exe`):

```
ABHT000:000_1
HFDTE070626
HPPLTPILOT:UNKNOWN
HPGTYAIRCRAFTTYPE:UNKNOWN
HPGIDAIRCRAFTID:UNKNOWN
HFDTM100GPSDATUM:WGS84
HFRFWFIRMWAREVERSION:GPX2GAC CONVERTER 1.0
HFRHWHARDWAREVERSION:UNKNOWN
HFFTYFRTYPE:gpx2gac,GPX GAC Converter 1.0
HFGPS:UNKNOWN
I033639GSP4042TRT4346FXA
B1000015000000N01300060EA999990100013880909999
...
```

Real logger files end with a cryptographic `G` security record proving the
track wasn't tampered with. A converter cannot produce a valid signature, so
the file ends with an openly-invalid placeholder (`GGPX2GACNOSECURITY`, same
approach as GPSBabel) to keep the record structure complete. Converted tracks
are for training and analysis; they can't pass anti-tamper validation if an
organizer enforces it.

B record layout (46 chars), per the `I` record extension definition:

| Bytes | Field | Content |
|-------|-------|---------|
| 1 | `B` | record type |
| 2–7 | time | `HHMMSS` UTC |
| 8–15 | latitude | `DDMMmmm[NS]` (thousandths of minutes) |
| 16–24 | longitude | `DDDMMmmm[EW]` |
| 25 | fix validity | `A` |
| 26–30 | pressure altitude | `99999` (no baro sensor) |
| 31–35 | GPS altitude | **feet** (meters × 3.2808) |
| 36–39 | GSP | ground speed, tenths of **knots** |
| 40–42 | TRT | true track, degrees |
| 43–46 | FXA | fix accuracy, `9999` (n/a) |

Ground speed and true track are computed from consecutive fixes using the same
equirectangular approximation as the original (1′ = 1 NM), with `HALF_EVEN`
rounding matching Java's `DecimalFormat`.

Output uses **CRLF** line endings, matching real logger files (AFLOS) and the
Windows-native original converter — PrecisWin-era software may reject bare LF.

Each B record carries the fix time as `HHMMSS` **UTC** in bytes 2–7
(`B084037…` = 08:40:37 UTC). The flight date lives in the `HFDTE` header
record (`HFDTE070626` = 07 Jun 2026, IGC `DDMMYY` convention).

## Differences from the original

Three deliberate improvements:

- **AFLOS-style header** — the original writes a minimal `AFCGPX`/`HINFO`
  header with no date at all (FlightContest takes it from the contest
  definition). This port mirrors the full AFLOS record sequence instead,
  including the `HFDTEDDMMYY` date derived from the first track point's
  timestamp, so strict parsers and standalone consumers get a complete file.
  Pilot/aircraft fields are settable via `--pilot`, `--aircraft-type`,
  `--aircraft-id` (default `UNKNOWN`, like AFLOS writes when unconfigured).
- **Time-delta aware speed** — the Groovy original computes `distance × 3600`,
  silently assuming 1 Hz fixes; this port divides by the actual time delta, so
  recordings with gaps don't get understated speeds.
- **Minute rollover** — coordinates whose minutes round to `60.000` carry into
  the degrees field instead of emitting a malformed `DD60000` coordinate.

## Attribution

Python port of `GPX2GAC.groovy` from the
[FlightContest](https://flightcontest.de) scoring software by Thomas Weise,
Deutscher Präzisionsflug-Verein e.V. All format decisions follow that
implementation.

## Tests

```bash
python3 -m unittest discover tests -v
```

## License

**GPL-3.0-or-later.** The B-record conversion math is a derivative work of
[FlightContest](https://flightcontest.de)'s `GPX2GAC.groovy` (GPL-3.0,
© 2009–2025 Thomas Weise, Deutscher Präzisionsflug-Verein e.V.), so this
port carries the same license. See `LICENSE`.

## Development docs

`docs/gac-format.md` — format archaeology, reference-file locations, decision
log, and the validation procedure used to verify output against a
known-working AFLOS logger file. `CLAUDE.md` — rules for AI agents working on
this repo.
