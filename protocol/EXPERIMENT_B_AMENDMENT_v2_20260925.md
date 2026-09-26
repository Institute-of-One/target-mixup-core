# Experiment B — Amendment v2 (frozen before set 2)

Date: 2026-09-25. Design v1: `EXPERIMENT_B_DESIGN_v1_20260925.md` (unchanged; its readers stay frozen in
`expB_readers.py` and are scored on every request).

## Why an amendment

Set 1 (20 expert requests, one per series) was written against the v1 design. Reading it showed that the
v1 readers did not match how an expert actually identifies a nodule. Set 1 is therefore reclassified as
the **development set**. The v2 readers were designed on it, and a new **evaluation set** (set 2, 20
requests, the second slot of each series, a different nodule from set 1) is written only after this
amendment and the file hashes in `work/expB/FREEZE_v2_before_set2.json` were fixed.

## What set 1 showed (all 20 requests)

1. **Position within the lung is the main identifier.** Examples are 背側, 前方, 外側, 肺尖, 肺底 and
   椎体に隣接. v1 read only side, lobe, rank and size.
2. **Measurement is not a rank.** "最大径の計測" means "measure the longest diameter of the chosen
   nodule". The frozen v1 rules read 最大径 as "the largest nodule". This produced **2 inappropriate
   authorizations** (the nearest other target authorized). This is a reader error, reported as such. The
   author was not instructed to choose the largest or the most caudal nodule. The v1 model never made this
   error (ordinal = none in 20/20).
3. **Experts point at the image.** 19/20 requests said "マーキングした結節". This came partly from the
   authoring screen's highlight, which is a design fault of the screen and not of the author. A text-only
   pipeline cannot receive a marking.
4. **The v1 model deferred on all 20** (0 correct, 0 inappropriate), because any low-confidence answer
   discarded the whole specification.

## v2 readers (`expB_readers_v2.py`)

- Regions: anterior/posterior (ap < 0.5 / ≥ 0.5), medial/lateral (ml < 0.5 / ≥ 0.5) and apex/base (cc < 1/3
  / > 2/3). These fractions are measured inside the TotalSegmentator lung of the target's side
  (`expB_regions.py`, `regions.json`). "Next to the vertebra" = posterior + medial.
- The measurement type is a separate field. 最大径, 長径 and "longest diameter" are never a rank.
- Marking references are detected and reported; they do not bind a target.
- Model: a low-confidence "unspecified" answer leaves that field unspecified. A specific value still needs
  confidence ≥ 0.8; otherwise the specification is unresolvable and the gate defers.
- Gate: filter by side, lobe, size (±1 class), regions, then rank. Authorize only a unique survivor.

### Model wording, two development runs on set 1 (both kept)

| run | file | R2 correct / inappropriate | M2 correct / inappropriate | issue found |
|---|---|---|---|---|
| v2a | `model_responses_v2.jsonl` | 7 / 0 | 6 / 0 | lobe inferred from position (肺底 → LLL at 1.0; 肺尖 → RUL at 0.69); a marking counted as unverifiable in 15/20 |
| v2b | `model_responses_v2b.jsonl` | 7 / 0 | 7 / 0 | none. Lobe agreement with R2 is 20/20 and unverifiable agreement 18/20 |

The v2b wording is frozen. Set-2 model calls append to `model_responses_v2b.jsonl` (v2) and to
`model_responses.jsonl` (v1).

## Set 2 protocol

- Authoring screen: the recipient receives **only the text**; no marking or arrow. The author identifies
  the nodule in words, in the usual way. The click records ground truth only. Records carry `set: 2`.
- One request per series, for a nodule different from that series' set-1 nodule (enforced by the service).
- After all 40 requests, the author labels the intended conditions of every request: side, lobe, rank,
  size, front/back, inner/outer, apex/base, reliance on a marking, and other information. This labelling
  happens without seeing any reader output.

## Scoring (`expB_score_v2.py`, frozen)

- Readers: R1, M1 (frozen v1); R2, M2 (v2); A2 (the author's labels through the v2 gate; reference).
- Episodes: the intended target offered, and the nearest other target offered.
- Outcomes: correct authorization and inappropriate authorization, with bootstrap intervals over series.
- Strata: requests relying on a marking, and requests using unverifiable information (from the author's
  labels).
- **Set 1 and set 2 are always reported separately.** Set 1 under v2 is post hoc (v2 was designed on it).
  Set 2 is the evaluation.
- The primary safety outcome is inappropriate authorization on set 2. A correct-authorization rate below
  set 1's is reported as it is.

## Amendment v2.1 (after set 2 was written; before any set-2 score was computed or any reader output was read)

At this point the set-2 model calls (v1 and v2b, 20 each) had already been run by the author. Their files
were counted but not opened or scored. No author label existed.

The author pointed out that the planned label "relied on an image marking" cannot discriminate. Every
nodule was chosen among the outlined annotations, so the author would answer yes for all 40 requests.
The author was never told that marks could be ignored or that an unmarked lesion could be chosen. The label
is removed from the labelling screen and from the scorer. The marking condition is carried by the set
instead: set 1 was written assuming the recipient sees the marking, and set 2 was text only by
instruction. The stratum "used other (unverifiable) information" stays, and marks are explicitly excluded
from it. Gates, readers and outcomes are unchanged. Frozen in `FREEZE_v2_1_labels.json`.

## Known limit stated in advance

The gate resolves among **annotated** targets. The expert found unannotated nodules during the spot checks,
so a unique annotated survivor does not prove it is the nodule the expert meant. Inappropriate
authorization is measured only against the nearest annotated alternative.
