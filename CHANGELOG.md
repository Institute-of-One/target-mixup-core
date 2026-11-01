# Changelog

## 0.1.3

The revision requested by the reviewers of the accompanying manuscript. No frozen code or data changed, and every
previously released result file is byte for byte what it was.

- `paper/labels.py` is now released. `paper/figures.py` and `paper/manuscript_numbers.py` both import it, and it was
  missing from the export of this repository, so neither the figures nor the numbers could be regenerated from the
  archive. Nothing else about them changed.
- New analysis, each writing one released result, for the tables the reviewers asked for:
  - `expB_contingency.py` - the five-cell outcomes contingency and the per-request table (Table S1);
  - `expB_decision.py` - what consensus costs: correct authorizations lost per wrong one removed, with a paired
    cluster bootstrap over the CT series;
  - `expB_adjudication_table.py` - the lobe adjudication, one row per item, with the CT series, the coordinates and
    the time each answer was saved, so the view can be reconstructed from the public images;
  - `expB_timeline.py` - the order the design was fixed in, read from the dated freeze records;
  - `seg_census_population.py` - the listing each stratum was sampled from, so the sampling fraction can be stated;
  - `seg_census_coded_fields.py` - the coded fields of every audited SEG and the per-pair table (Table S2);
  - `seg_census_spot_detail.py` - the acquisition each visual judgement was made on, and how the case was chosen;
  - `rider_documented_lesion.py` - where each RIDER segment lies relative to the lesion the collection documents
    (Table S3);
  - `record_environment.py` - the TotalSegmentator and torch versions, read from the environment that computed the
    lobe masks and recorded in `results/expB/environment.json`, so the reproducibility table can be regenerated
    from the archive rather than only on that machine.
- `expB_score_v3.py` additionally records, per row, the case, the patient, the resolved target and the nearest other
  target, and writes `results/expB/per_request_v3.json`. The two scored fields are unchanged and `results_v3.json`
  is byte for byte what v0.1.2 released; the difference from the set-3 freeze record is documented, with that
  evidence, in `results/freeze_exceptions.json`.
- CI now regenerates every released result that a released script can write from the archive, and compares all of
  them, JSON parsed and CSV row by row. It had regenerated five scripts and compared four files. `check_reproduced.py`
  reads CSV, so the two supplementary tables are compared, and takes `--ignore` for a field that records when a step
  ran.
- The README states the current title, which failures each measure prevented rather than which safeguards stop
  which failures, and which scripts cannot run from the archive because their inputs are not redistributed.

## 0.1.2

- Manuscript retitled; terminology aligned with it: the request-reading components are "parsers" and their agreement is "consensus". `paper/figures.py` labels the consensus gates accordingly. No analysis, frozen code or data changed.

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
