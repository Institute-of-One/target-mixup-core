# Errata to the frozen protocol documents

The protocol documents are hashed in the freeze records and are therefore never edited. Known errors are recorded
here instead.

- `EXPERIMENT_B_AMENDMENT_v3_20260926.md`, section "v3", slice-local positions: "All 121 targets had a lung slice"
  should read 123. The 20 series carry 123 targets. The figure 121 comes from the lobe freeze record
  (`results/expB/FREEZE_lobes.json`). That record counts the 121 targets whose body side could be decided from the
  midline, which agreed with their lobe side, and excludes the 2 targets with an indeterminate side.
  `results/expB/regions_v3.json` contains all 123.
