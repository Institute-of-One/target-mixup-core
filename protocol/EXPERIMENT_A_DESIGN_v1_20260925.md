# Experiment A — request-bound execution gate on real multi-target CT (design v1, 2026-09-25)

Status: DRAFT for the author's approval. Nothing below has been run. Once approved, the items marked
FROZEN are fixed before any evaluation output is seen; later changes create a new version and the
change and its reason are reported.

## Question

When a request names one of several real targets on the same CT and the pipeline is handed a SEG, how
often does each gate release a measurement of the wrong target, how often does it complete the correct
measurement, and how often does it defer? What does a language model add when it only converts the
request text into a structured target specification that a deterministic gate checks?

## Population (FROZEN)

- LIDC-IDRI CT series from the census with ≥ 2 geometric targets (59 series; targets = geometric groups of
  QIICR segments, `targets.json`). Target identity comes from the published annotations, not from a reviewer.
- Development-exposed patients excluded from evaluation: LIDC-IDRI-0325, 0314 (earlier development),
  0510 (spot check 01 and its findings match). A development split of 10 further CT series (seeded draw)
  is used to write templates and rules; evaluation uses the remaining series. Split and seed recorded.
- RIDER 2357766186 / 5195703382 are reported separately as the natural case (documented lesion vs. a
  different real nodule), not pooled.

## Target attributes (computed, FROZEN definitions)

Per target: centroid (LPS), longest axial diameter (as in the GUI size reference), side (left/right of
the body midline, midline = centre of the body mask on one mid-series CT slice), and ordinal relations
among the targets on the same series: most cranial / most caudal, largest / smallest, per side and overall.
Requires one CT image per series (about 30 MB total).

Clarification added before freezing (no outputs seen): targets are formed from QIICR segments only; a
target's centroid is the mean of its annotations' centroids and its size is the median over its
annotations of each annotation's longest axial diameter. The midline slice is the CT image nearest to
the median z of all targets on that series. Ordinal descriptions compare target centroids (z for
cranial/caudal) and sizes; ties within 2 mm (position) or 1 mm (size) make a description ambiguous.

## Requests (FROZEN templates)

- Each request describes one target by side, ordinal and size class (≤ 3 cm nodule / > 3 cm mass), e.g.
  "右側で最も大きい結節の体積を測って" / "Measure the volume of the most caudal nodule in the left lung".
- A description is *unique* if exactly one target satisfies it, otherwise *ambiguous* (correct action:
  defer). Ambiguous descriptions are included deliberately.
- Japanese and English; paraphrase families written in advance; families used for development are not
  used for evaluation.

## Offered SEG (FROZEN)

For each request the pipeline is handed one QIICR SEG of that series: the intended target or a different
target, by a seeded coin (p = 0.5). All offered SEGs pass the structural checks.

## Conditions

- G0 header-only: `series_integrity` checks; release if structurally consistent.
- G1 rules: a rule parser extracts {side, ordinal, size class, or unresolvable}; the gate releases only if
  the offered SEG is the unique target matching the specification, else defers.
- G2 choice model: the same specification is obtained from a choice-constrained model (Jev; fixed choice
  sets, confidence recorded, low confidence = unresolvable); the same gate as G1. Named in Methods only.
- G3 oracle specification: the true specification (upper bound of the gate itself).

## Outcomes

- Wrong release: a measurement released for a SEG that is not the intended target (denominator: all requests).
- Correct completion: released with the intended SEG (denominator: unique requests offered the intended SEG).
- Deferral, split into ambiguity-appropriate and unnecessary.
- Specification accuracy per field (G1, G2); latency; API cost; API failures counted, never retried silently.
- Intervals: bootstrap over patients (clustered).

## Expected-but-not-assumed behaviour

G0 should release about half of the requests with the wrong SEG, by construction. G1–G3 differences
depend on paraphrase coverage. No threshold of "success" is set; every result, including no advantage of
G2 over G1, is reported.

## Human review

None added. Truth comes from published annotations and computed attributes.

## Budget (to approve before any paid call)

Evaluation size is set after the development split is drawn: expected on the order of 150–250 requests,
one G2 call each. A cost estimate will be presented before running; no paid call without approval.
