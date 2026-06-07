# gpx2gac

GPX → GAC converter for FAI precision/rally flying scoring software
(FlightContest, PrecisWin/AFLOS ecosystem). Single stdlib-only Python script.

## Read first

- `docs/gac-format.md` — **the knowledge base**: format archaeology, reference
  file paths, full decision log, validation procedure, open questions.
  Read it before changing any output formatting.
- `README.md` — user-facing usage + format spec.

## Core rules

1. **Never break byte fidelity.** Output is verified structurally identical to
   a known-working AFLOS logger file. Invariants: CRLF line endings, 46-char
   B records, AFLOS header record sequence, `HALF_EVEN` rounding, altitude in
   feet (× `3.2808`), speed in tenths of knots, trailing space in
   `HFGPS:UNKNOWN `, terminal `G` record.
2. **Run tests before committing**: `python3 -m unittest discover tests` —
   expected values are hand-verified against the reference converter; if a
   test fails, the code is wrong, not the test.
3. **Stay honest in identity records.** Never make `HFRFW`/`HFFTY`/`A` records
   impersonate real AFLOS hardware, and never fabricate a "valid-looking" G
   security signature — converted tracks must remain distinguishable from
   sealed logger recordings.
4. After format changes, re-run the validation procedure in
   `docs/gac-format.md` against a known-good AFLOS logger file (kept locally;
   real competition flights are never committed to this repo).

## Commands

```bash
python3 gpx2gac.py flight.gpx                          # convert
python3 gpx2gac.py --pilot "Name" flight.gpx out.gac   # with metadata
python3 -m unittest discover tests                     # test
```

## Repo conventions

Personal tool repo: direct-to-main commits OK. GitHub: lbehounek/gpx2gac.
CI: tag-on-merge only. License: GPL-3.0 (derivative of FlightContest's
GPX2GAC.groovy, GPL-3.0, © Thomas Weise / Deutscher Präzisionsflug-Verein e.V.).
