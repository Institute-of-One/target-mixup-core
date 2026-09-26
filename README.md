# target-mixup-core

[![CI](https://github.com/Institute-of-One/target-mixup-core/actions/workflows/ci.yml/badge.svg)](https://github.com/Institute-of-One/target-mixup-core/actions/workflows/ci.yml)
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.22978585.svg)](https://doi.org/10.5281/zenodo.22978585)

Code, derived results and pre-specification records for the study

> **Correctly Parsed, Wrong Lesion: Where Target Mix-Ups Arise When AI Binds Measurement Requests to Lung CT Nodules — A Staged Evaluation** (Shuji Yamamoto; manuscript under review).

The study asks where an AI pipeline that measures a lesion on request can end up measuring the wrong lesion, and
which safeguards stop which failures. It has three stages on public lung CT from The Cancer Imaging Archive (TCIA):

1. **Stratified audit** (the code calls it the census) of public DICOM Segmentation (SEG) series: header checks (source references, Frame of Reference, plane
   placement) and whether recorded semantics distinguish targets (`seg_census*.py`, `series_integrity.py`).
2. **Experiment A**: templated requests, gates G0–G3 (`expA_*.py`).
3. **Experiment B**: 60 expert-written requests in three sets, each written after the design for it was frozen with
   SHA-256 hashes (`expB_*.py`), plus a lobe adjudication.

This repository contains no images, no DICOM objects and no segmentation masks. It identifies public TCIA objects by
their UIDs and contains results derived from them.

## Layout

| Path | Contents |
|---|---|
| `core/` | Analysis code (flat modules, run from this directory) and unit tests |
| `core/imaging_tests/` | Tests of the DICOM checks on synthetic CT–SEG pairs |
| `core/paper/` | `manuscript_numbers.py` (every number the manuscript quotes) and `figures.py` (the audit, Experiment A and Experiment B figures; Figures 2–4 of the manuscript) |
| `results/seg_census/` | Audit records, summary, target-semantics analysis, visual spot-check answers |
| `results/expA/` | Experiment A requests, model responses, results, freeze records |
| `results/expB/` | Experiment B requests, author labels, model responses, lobes, positions, results, freeze records, lobe adjudication |
| `results/numbers.json` | All numbers quoted in the manuscript, with their source files |
| `protocol/` | Design documents and amendments whose hashes the freeze records contain |

## Reproduce the reported numbers

Python 3.12 is required (the pinned numpy needs it; Python 3.14 on Windows lacks a wheel for highdicom's pyjpegls).
From the repository root:

```bash
python -m venv .venv
.venv/bin/pip install -r requirements.txt        # Windows: .venv\Scripts\pip
cd core
python -m unittest discover -s . -q
python -m unittest discover -s imaging_tests -q
python verify_freezes.py --root ..
python expB_score_v3.py --expb ../results/expB --expa ../results/expA
python expB_paper_results.py --expb ../results/expB --expa ../results/expA
python expB_claims_check.py --expb ../results/expB --expa ../results/expA
python paper/manuscript_numbers.py --census ../results/seg_census --expa ../results/expA --expb ../results/expB --out ../results
python paper/figures.py --census ../results/seg_census --expa ../results/expA --expb ../results/expB --out ../figures
```

- `verify_freezes.py` checks every freeze record against the released code, protocol documents and data. Append-only
  files (later request sets were appended) pass when their first lines match the frozen bytes. The differences that
  the study itself documented are listed with their reasons in `results/freeze_exceptions.json`.
- `expB_claims_check.py` checks the qualitative statements the manuscript makes about Experiment B. For example, it
  checks that the model reader never returned a rank.
- CI runs all of the above and compares the regenerated JSON files with the released ones.

The following steps need data that this repository does not redistribute:

- **Downloading the TCIA objects:** `seg_census.py`, `seg_spot_fetch.py` and `seg_fetch_pairs.py` use the public
  NBIA API.
- **Recomputing lobes:** `expB_lobes.py` and `expB_regions*.py` use
  [TotalSegmentator](https://github.com/wasserth/TotalSegmentator); see `requirements-segmentation.txt`.
- **Figure 4:** it is an image rendering from the private viewer.

Visual judgements come from the author, recorded through a local viewer that is not part of this repository:
- the audit spot checks;
- the RIDER target review;
- the Experiment B lobe adjudication.

The comparison of RIDER segmentations with the lesion notes distributed with that collection was done by hand.

## The choice-constrained model

`expA_jev.py` and `expB_jev.py` send each request text once to Jev 1.13.0 (TypeSafe). All responses used in the study
are included, so no call is needed to reproduce the results. A new call needs a TypeSafe API key:
- the key is read from the clipboard, the environment or a hidden prompt;
- it is never written to disk or printed;
- API use may incur charges.

## Data and ethics

The images are de-identified public data:
- [LIDC-IDRI](https://doi.org/10.1118/1.3528204) and [RIDER Lung CT](https://doi.org/10.1148/radiol.2522081593),
  distributed by [TCIA](https://www.cancerimagingarchive.net/);
- the QIICR DICOM conversions of the LIDC annotations ([Fedorov et al. 2020](https://doi.org/10.1002/mp.14445)).

Their use is governed by the TCIA data usage policies. The Experiment B requests, intended-condition labels and
adjudication answers were written by the author of this study. They contain no patient information beyond public TCIA
UIDs.

## Licence

- Code (`core/`): MIT (see `LICENSE`).
- Results and protocol documents (`results/`, `protocol/`): CC BY 4.0.

## Citation

See `CITATION.cff`. All versions: https://doi.org/10.5281/zenodo.22978585 (concept DOI). The version used in the
manuscript: v0.1.2 (version DOI added at release). First release, v0.1.0: https://doi.org/10.5281/zenodo.22978586.
