# Experiment B — expert-written requests bound to lesions (design v1, 2026-09-25)

Status: to be frozen (sha256 recorded) together with the rule parser and the model request BEFORE the
author writes any request. Experiment A and its post hoc analyses are unchanged and reported separately.

## Question

When a domain expert writes measurement requests in his own reporting language for lesions on real
multi-nodule CT, how often can the request be bound to exactly one lesion, what does each way of reading
the request (rules; a choice-constrained language model) achieve, and what fraction of requests uses
information that the pipeline cannot verify?

## Population (FROZEN)

Twenty LIDC-IDRI CT series drawn with a fixed seed from the Experiment A evaluation split, restricted to
series with ≥ 3 geometric targets. Development series of Experiment A and patients 0314, 0325, 0510 are
excluded. Targets and their attributes are those of `expA/targets.json`, plus the lung lobe of each
target from TotalSegmentator (task `total`, lobe classes; the lobe containing the target centroid, else
the lobe with most target voxels, else `outside`).

## Requests (written by the author after the freeze)

In a dedicated GUI view the author opens each series, sees the CT with all annotated nodules outlined,
selects one nodule by clicking it, and writes the request he would give in practice to have that nodule
measured (volume/diameter), in Japanese or English, freely. Two requests per series, for different
nodules chosen by the author; 40 in total. The clicked point is matched to a target by
`seg_point_match` (inside an annotation of that target); a click on no target is recorded and excluded.
The author does not see the rules, the model request or any parser output before all 40 are saved.

## Specification (both readers produce the same structure; FROZEN)

side {right, left, unspecified}; lobe {RUL, RML, RLL, LUL, LLL, unspecified}; ordinal {largest, smallest,
most_cranial, most_caudal, none}; size_class {<5 mm, 5–10, 10–20, 20–30, >30 mm, unspecified};
plus flags: `unverifiable` (the request relies on information the pipeline cannot check, e.g. segment
S1–S10, subpleural, relation to vessels, prior examination, lesion number) and `unclear`.

- R (rules): regular expressions for the vocabulary listed below, which contains every term used in
  the model's option descriptions (vocabulary-matched by construction).
- M (model): Jev 1.13.0, request text only, one choice question per field; confidence < 0.8 or
  `unclear` → unresolvable. Each request sent once, no retry.

## Gate (FROZEN)

Filter the series' targets by every verifiable field (side, lobe, size class with a ±1-class tolerance,
then ordinal among the remainder, ties as in Experiment A). Authorize only if exactly one target remains.
If `unverifiable` is set, the episode is still gated on the verifiable fields but reported in its own
stratum. The gate is offered the SEG of the intended target and, in a second pass, of the nearest other
target (both passes reported), so every request contributes one appropriate and one inappropriate offer.

## Outcomes

Per reader: correct authorization of the intended target; inappropriate authorization of the other
target; deferral; specification agreement with the author's own specification (see below). Strata:
requests that are unique on verifiable fields vs not; with vs without unverifiable content. Counts with
intervals clustered by series.

After all outputs are recorded, the author labels each of his requests with the specification he
intended (same fields), without seeing the parsers' outputs, to measure reading accuracy per field.
This labelling is part of the design, not post hoc.

## Honesty rules

No change to rules, prompt or gate after the first request is written. If the readers do not differ,
that is reported. The gate uses the model only to structure text; decisions are deterministic.
