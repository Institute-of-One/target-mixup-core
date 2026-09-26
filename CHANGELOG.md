# Changelog

## 0.1.1

Additions requested by an independent review of the manuscript. No frozen code or data changed.

- `expB_rank_ablation.py` and `results/expB/rank_ablation.json` (post hoc):
  - the frozen v1 rule reader with only its rank constraint removed;
  - whether the v1 consensus removed exactly the rank-dependent wrong resolutions;
  - the author-intent readers with the first and with the latest version of each label.
- `expB_paper_results.py` also records the wrong-resolution cases per reader and set, and classifies the set-3
  consensus-gate errors by the lobe adjudication.
- `expB_claims_check.py` checks the statements the manuscript makes about both consensus gates at once and about the
  ablation.
- `protocol/ERRATA.md` records an error in a frozen protocol document (121 vs 123 targets).
- The release metadata follow the other Institute of One repositories:
  - canonical affiliation;
  - the IORN-015 identifier;
  - concept and version DOIs.

## 0.1.0

First public release, accompanying the manuscript submission. Contains the analysis code for the census and for
Experiments A and B, the derived results and freeze records, and the protocol documents.
