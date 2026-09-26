# Results

Derived results for the manuscript, licensed CC BY 4.0. No images, DICOM objects or masks are included; TCIA objects
are identified by their public UIDs.

- `seg_census/`
  - `records.jsonl`, `summary.json`, `sample_plan.json`, `study_for.json`, `release_dates.json`, `ambiguity.json`:
    the census.
  - `targets.json`, `targets_posthoc_20260925.json`: target semantics.
  - `spot_checks/reviews*.jsonl`: visual spot-check answers.
  - `spot_checks/match_01_findings.json`: automatic matching of the reviewer's marks against published
    annotations.
  - `target_checks/target_reviews.jsonl`: the RIDER target review.
- `expA/`: targets, generated requests (development and evaluation), model responses (including a first development
  attempt that failed with HTTP 400 on every call), results, the post hoc analysis and the freeze records.
- `expB/`
  - Request sets: selected series, `requests_expert.jsonl` (60 requests; `set` 1–3, absent = 1).
  - Author labels: `author_specs.jsonl` (all label versions; the latest per request is used).
  - Model responses: `model_responses.jsonl` (v1 request), `model_responses_v2.jsonl` (first v2 development run) and
    `model_responses_v2b.jsonl` (frozen v2 request).
  - Lobes and positions: `lobes.json`, `regions.json`, `regions_v3.json`.
  - Results: `results*.json`, `paper_results.json`, the diagnostic traces and `fissure.json`.
  - Freeze records: `FREEZE_*.json`.
  - Lobe adjudication: `lobe_review/`.
- `numbers.json`: every number the manuscript quotes, with its source file.
- `freeze_exceptions.json`: differences between a freeze record and the released files that the study documented,
  with the reason for each.
