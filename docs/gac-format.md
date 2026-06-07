# GAC Format — Reference & Decision Log

Source of truth for everything learned while building this converter.
README.md holds the user-facing format spec; this file holds the archaeology:
where the knowledge came from, why each decision was made, and how to
re-validate output against known-good files.

## What GAC is

Line-based GPS track format (IGC-family) consumed by FAI GAC (General
Aviation Commission) precision/rally flying scoring software. Produced
natively by BeHeTec **AFLOS** loggers used at competitions; produced
synthetically by GPX converters for training flights.

## Known consumers

| Software | Notes |
|----------|-------|
| FlightContest (flightcontest.de, Grails, GPL-3.0) | Parses B records; **ignores `HFDTE`** — flight date comes from the contest definition. Source contains zero `HFDTE` references. |
| PrecisWin / GPS7 / AFLOS Reader (BeHeTec, Windows VB-era) | The strict ones — CRLF and full AFLOS header sequence assumed. |

## Reference materials

| Source | What it is |
|--------|------------|
| FlightContest source: `GPX2GAC.groovy` | Original converter this is ported from (Thomas Weise, v1.0) |
| FlightContest source: `AviationMath.groovy` | `calculateLeg` — equirectangular distance/bearing math |
| FlightContest source: `FcMath.groovy` | `RoundGrad`/`GradStr` — HALF_EVEN rounding, 360→0 wrap |
| FlightContest `testdata/Crew_*.gac` | Real AFLOS logger files (2010) |
| airsportslivetracking test data `*-converted.gac` | Weise converter output — **LF endings are a Linux-server artifact, do not imitate** |
| A known-working AFLOS Reader 2.03 competition export (2026) | The byte-fidelity benchmark this output was verified against. Private competition flight — not redistributable, not in this repo. |
| `GPXGAC5.exe` | Original Windows converter binary (VB5, needs msvbvm50.dll), distributed with FlightContest tooling |

## Decision log

1. **B-record math = faithful Groovy port.** Equirectangular approximation
   (1′ lat = 1 NM, lon scaled by cos of mean lat), `HALF_EVEN` rounding
   everywhere (Java `DecimalFormat`/`BigDecimal.setScale` default), altitude
   in **feet** via factor `3.2808` (not 3.28084), ground speed in **tenths of
   knots**, true track integer degrees with 360→0 wrap.
2. **Time-delta-aware speed** (deviation): original does `dis × 3600`,
   silently assuming 1 Hz fixes. We divide by actual Δt. No-op at 1 Hz.
3. **Minute rollover guard** (deviation): minutes rounding to `60.000` carry
   into degrees; original would emit malformed `DD60000`.
4. **`HFDTE` date record added**: original omits it entirely, losing the
   flight date. AFLOS files carry it as line 2 (`HFDTEDDMMYY`).
5. **AFLOS header sequence** (`A`, `HFDTE`, `HPPLT`, `HPGTY`, `HPGID`,
   `HFDTM`, `HFRFW`, `HFRHW`, `HFFTY`, `HFGPS`, `I`): replaced the original's
   `AFCGPX`/`HINFO` header after byte-level comparison against the
   known-working sample. Includes the trailing space after `HFGPS:UNKNOWN`
   (byte-faithful to AFLOS).
6. **CRLF line endings**: the known-working sample is CRLF; the LF reference
   file was a Linux artifact. PrecisWin-era VB software is where bare LF breaks.
7. **`G` security record placeholder** (`GGPX2GACNOSECURITY`): real loggers
   end with a cryptographic signature a converter cannot produce. We write an
   openly-invalid placeholder for record-inventory parity (GPSBabel does the
   same). Can never pass enforced anti-tamper validation.
8. **FXA `9999`** sentinel (not real accuracy like loggers' `0001`): the
   converter convention for "not available". Parses as a number, fine.
9. **Honest identity**: `HFRFW`/`HFFTY` say `GPX2GAC CONVERTER`, never
   impersonate AFLOS hardware. `ABHT000:000_1` is deliberately synthetic.

## Validation procedure

```bash
# unit tests (expected values hand-verified against reference output)
python3 -m unittest discover tests

# every B record: 46 chars, strict field format, CRLF
LC_ALL=C grep -a '^B' out.gac | grep -cvE \
  '^B[0-9]{6}[0-9]{4}[0-9]{3}[NS][0-9]{5}[0-9]{3}[EW][AV][0-9]{5}[0-9]{5}[0-9]{4}[0-9]{3}[0-9]{4}\r$'
# must print 0

# record inventory must read: 1×A, N×B, 1×G, 9×H, 1×I
LC_ALL=C awk '{print substr($0,1,1)}' out.gac | sort | uniq -c

# line endings must say "with CRLF line terminators"
file out.gac
```

Gotchas hit during development: macOS `grep` treats the sample as binary
(0xE6 byte in its G record) — use `grep -a` + `LC_ALL=C`; BSD `awk` lacks
`{n}` regex intervals.

## Status

- **Confirmed working end-to-end with the scoring system** (07 Jun 2026):
  converted output was accepted and scored. The `ABHT000` synthetic logger ID,
  placeholder G record, and FXA `9999` sentinel are all tolerated in practice.
- GPX input so far tested only with myTracks (iPhone) exports: single `trk`,
  1 Hz, UTC times with fractional seconds.
