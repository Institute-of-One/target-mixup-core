# Experiment A — amendment v1.1 (2026-09-25)

Applies to EXPERIMENT_A_DESIGN_v1_20260925.md (frozen, sha256 39e86f18…). Made before any request was
generated or any gate was run; only the target table (`expA/targets.json`) had been computed.

## Change

Side of a target is determined only when two independent midline estimates on the same CT slice agree:
(a) midpoint of the body extent (HU > −300) and (b) centroid of bone (HU > 200). A target is `left` or
`right` only if both estimates put it on the same side and it lies ≥ 10 mm from both; otherwise its side
is `midline` (indeterminate). A description that relies on the side of an indeterminate target is
ambiguous, and its correct action is deferral.

## Reason

The two estimates differed by > 10 mm in 15 of 59 series (median difference −0.7 mm, maximum 22.3 mm).
Four of 304 targets change side or lie within 10 mm under one estimate; for them "left/right" has no
reliable truth. Also noted, not changed: only two targets exceed 30 mm, so the nodule/mass size class
rarely distinguishes targets in this population.
