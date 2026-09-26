# Experiment B — Amendment v3 (frozen before set 3)

Date: 2026-09-26. Earlier documents stay valid:
- `EXPERIMENT_B_DESIGN_v1_20260925.md`
- `EXPERIMENT_B_AMENDMENT_v2_20260925.md` (including v2.1)
- `EXPERIMENT_B_RESULTS_20260926.md`

v1 and v2 code is unchanged and is scored on every set.

## Why

Set 2 (the evaluation of v2) produced three findings that v3 turns into pre-specified tests:

1. **Double reading.** The frozen v1 rules made 5 wrong-target authorizations across sets 1–2, and all 24 of
   their correct authorizations came from the same misreading (最大径 read as "largest").
   - Requiring the v1 rule reader and the v1 model reader to agree on the target removed all 5.
   - The two readers disagreed on the rank field in 39/40 requests.
   - This was a post hoc finding.
2. **Position words are judged on the image slice and are vague (B15).**
   - The author called a nodule lateral that lies at 0.443 of the whole-lung inner-to-outer extent
     (0.394 on its own slice).
   - Because the intended nodule was excluded, the nearest other nodule became the unique survivor and was
     authorized.
3. **The model reader deferred on 17/20.**
   - The v2 rule discards the whole specification when any specific value has low confidence.
   - The model often added unstated values with low confidence, for example "base" inferred from 下葉.

## v3 (code: `core/expB_readers_v3.py`, `core/expB_regions_v3.py`, `core/expB_score_v3.py`)

- **Slice-local positions.**
  - Front/back and inner/outer are measured within the TotalSegmentator lung of the target's side, on the
    axial slice nearest the target centroid (`regions_v3.json`). All 121 targets had a lung slice.
  - Apex/base stays whole-lung.
- **Tolerance band.** A position word excludes a candidate only when the candidate lies clearly on the other
  side, more than 0.15 beyond the cut (0.5 for front/back and inner/outer; 1/3 and 2/3 for apex/base).
  Borderline candidates are kept, which makes the gate defer rather than exclude on weak evidence.
- **Model as second reader** (`read_model_v3`): the same frozen v2b model answers are used. No new model
  request and no new calls are made for sets 1–2. A value below confidence 0.8 leaves only that field
  unspecified.
- **Dual-reader gates:**
  - D3t: the rule reader (R3) and the model reader (M3) each resolve to the same single target.
  - D3r: D3t, and both readers state the same identifying conditions (side, lobe, rank, size class,
    regions).

Readers are unchanged: the v2 rules and the v2b model request. v3 changes only how their outputs are gated.

## Development evidence (post hoc on sets 1–2; the v3 choices were made while seeing these numbers)

Each cell gives correct / wrong-target authorizations, out of 20 requests.

| reader | set 1 | set 2 |
|---|---|---|
| D3t | 5 / 0 | 9 / 0 |
| D3r | 5 / 0 | 6 / 0 |
| D1 (v1 double reading) | 0 / 0 | 6 / 0 |
| R3 | 5 / 0 | 10 / 0 |
| M3 | 5 / 0 | 9 / 0 |
| A3 (author's intent, v3 gate) | 4 / 0 | 9 / 0 |
| R1 (frozen v1 rules) | 11 / 2 | 13 / 3 |
| A2 (author's intent, v2 gate) | 7 / 0 | 8 / 1 |

Only the band was evaluated as a single setting (0.15). No other band value was tried.

## Set 3 protocol (confirmatory)

- In each of the 20 series, the author writes one request for a nodule not used in sets 1 or 2. Nodules
  already used are shown in gray and cannot be chosen.
- The instruction is the same as for set 2: the recipient receives only the text, and the nodule is
  identified in words in the usual way. Records carry `set: 3`.
- Model calls use the frozen v1 and v2b requests, one call each per request, with the same safeguards.
- The author labels the intended conditions of each set-3 request before any set-3 reader output or score
  is seen. The labelling screen shows no reader output.

## Pre-specified outcomes for set 3 (`expB_score_v3.py`)

- **Primary safety:** wrong-target authorizations of D3t and D3r.
- **Primary utility:** correct authorizations of D3t and D3r.
- **Secondary:**
  - A3 versus A2 (slice-local positions with the band, versus whole-lung positions, under the author's
    intent);
  - D1 versus R1 (does double reading remove the v1 rank misreading on new requests);
  - all single readers.
- Counts are reported with bootstrap intervals over series; there is no hypothesis test. A zero count is
  reported with its interval: the one-sided 95% upper bound for 0/20 is about 14%. Any wrong-target
  authorization is described case by case.

## Stated in advance

- The author has seen the set 1–2 results, including the 最大径 misreading and the B15 discussion.
  - Set-3 requests may therefore be written differently; for example, the author may avoid 最大径.
  - This is reported as a limitation.
  - The instruction to write as in practice is unchanged.
- The universe is annotated nodules only; see amendment v2.
- The three sets come from one expert, who is the author of this study; this is the IoO single-author
  design. Independence comes from the procedure:
  - requests are written before any reader output exists;
  - designs are frozen with hashes before each set;
  - labels are recorded before any score is seen;
  - label corrections are reported in both versions.
