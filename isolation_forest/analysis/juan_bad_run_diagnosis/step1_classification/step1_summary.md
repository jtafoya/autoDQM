# Step 1 — authoritative subrun/run classification

## A. Exact artifacts used

- Authoritative combined channel-level log: `/afs/cern.ch/user/p/pengy/autoDQM/isolation_forest/logs/juan_reproduction_digi_z8_if0001_train20_seed42_noTrigger_noLVDS_ignoreTriggerConfig.csv`
- Authoritative successful processed sequence: `/afs/cern.ch/user/p/pengy/autoDQM/isolation_forest/logs/juan_reproduction_digi_z8_if0001_train20_seed42_noTrigger_noLVDS_ignoreTriggerConfig_paths.txt`
- Original frozen selection TSV: `/afs/cern.ch/user/p/pengy/autoDQM/isolation_forest/condor/apply_good_training_sampled_paths_seed42_frac40.tsv`
- Successful per-run apply outputs/path caches: `/afs/cern.ch/user/p/pengy/autoDQM/isolation_forest/logs/juan_reproduction_digi_z8_if0001_train20_seed42_noTrigger_noLVDS_ignoreTriggerConfig/`
- Exact model directory/tag: `/afs/cern.ch/user/p/pengy/autoDQM/isolation_forest/models/juan_reproduction_digi_z8_if0001_train20_seed42_noTrigger_noLVDS_ignoreTriggerConfig`
- Model config snapshot: `/afs/cern.ch/user/p/pengy/autoDQM/isolation_forest/models/juan_reproduction_digi_z8_if0001_train20_seed42_noTrigger_noLVDS_ignoreTriggerConfig/config.yaml`
- Effective training provenance: `/afs/cern.ch/user/p/pengy/autoDQM/isolation_forest/models/juan_reproduction_digi_z8_if0001_train20_seed42_noTrigger_noLVDS_ignoreTriggerConfig/training_metadata.json`
- Existing evaluation counts: `/afs/cern.ch/user/p/pengy/autoDQM/isolation_forest/reports/juan_reproduction_digi_z8_if0001_train20_seed42_noTrigger_noLVDS_ignoreTriggerConfig/eval_confusion_data.json`
- Existing evaluation summary: `/afs/cern.ch/user/p/pengy/autoDQM/isolation_forest/reports/juan_reproduction_digi_z8_if0001_train20_seed42_noTrigger_noLVDS_ignoreTriggerConfig/eval_summary.txt`

The strict status comes directly from `src.plot._compute_persistence_status`,
which is the canonical helper imported by `src.evaluate.step_evaluate`.
The detail replay in `build_classification.py` mirrors that helper and
`src.monitor.process_file` to expose channel sets and individual alert flags;
every row was required to agree with the canonical helper.

## B. Number of sampled subruns analyzed

Analyzed **13432** successfully processed sampled subruns across
**96** runs.

The original frozen TSV contains 13620 paths across
97 runs. Run 1635 (188 selected paths) did
not publish a successful per-run output because sampled subrun 470 had no
events; the validation job rejected 187 logged filenames versus 188 expected.
Therefore the successful reproduction's combined log/cache contains 13,432
paths and excludes run 1635. No successfully processed path is absent from the
original TSV, and each of the other 96 per-run caches matches its TSV slice
exactly and in order.

## C. Strict replay versus previous evaluation

Yes. The strict replay totals exactly reproduce the existing evaluation:
**OK=12882, WARN=77,
PEND=0, ALERT=473**.

Thresholds were verified exactly: 2 persistent channels, 5 processed files,
5 bulk channels, and anomalous-channel max_z >= 15.

## D. Runs that are all_raw_bad

`[1710, 1711, 2013]`

## E. Runs that are all_strict_ALERT

`[1710, 1711, 2013]`

## F. Requested run comparison

| run | n_sampled_subruns | raw_bad_fraction | strict_alert_fraction | n_OK | n_WARN | n_PEND | n_ALERT | all_raw_bad | all_strict_ALERT |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1601 | 57 | 0.035088 | 0.070175 | 53 | 0 | 0 | 4 | False | False |
| 1710 | 1 | 1.000000 | 1.000000 | 0 | 0 | 0 | 1 | True | True |
| 1711 | 4 | 1.000000 | 1.000000 | 0 | 0 | 0 | 4 | True | True |
| 2013 | 1 | 1.000000 | 1.000000 | 0 | 0 | 0 | 1 | True | True |
| 2014 | 361 | 0.667590 | 0.196676 | 213 | 77 | 0 | 71 | False | False |
| 2085 | 82 | 0.024390 | 0.024390 | 80 | 0 | 0 | 2 | False | False |
| 2086 | 46 | 0.043478 | 0.000000 | 46 | 0 | 0 | 0 | False | False |
| 2087 | 107 | 0.084112 | 0.046729 | 102 | 0 | 0 | 5 | False | False |
| 2088 | 203 | 0.152709 | 0.113300 | 180 | 0 | 0 | 23 | False | False |
| 2089 | 369 | 0.317073 | 0.138211 | 318 | 0 | 0 | 51 | False | False |

## G. Is report.py “bad run” equivalent to strict ALERT?

**No.** `report.py` labels a subrun raw bad whenever it has at least 2
anomalous channels in that file. Strict ALERT instead requires at least one of:
2 channels persistent across 5 processed files, at least 5 anomalous channels
in one file, or anomalous-channel max_z >= 15. The unequal per-subrun
fractions above provide direct evidence that the labels are not interchangeable
(for example, run 2014 is 0.667590 raw bad versus 0.196676 strict ALERT, while
run 2086 is 0.043478 raw bad versus 0 strict ALERT). The all-run lists happen
to coincide for this sample, but that does not make the subrun definitions
equivalent.

## Sanity checks

- Required channel-log columns present: yes.
- One subrun row per successful processed path: yes (13432).
- Duplicate filename/channel log rows: none.
- Duplicate filenames in subrun table: none.
- Duplicate run/subrun pairs: none.
- Combined log order equals successful combined path cache: yes.
- Each successful per-run path cache equals its frozen TSV slice: yes.
- Combined cache equals concatenated successful per-run caches: yes.
- Persistence state reset at all 96 run boundaries: yes.
- Detail replay agrees row-by-row with canonical helper: yes.
- Strict totals agree with existing evaluation output: yes.
