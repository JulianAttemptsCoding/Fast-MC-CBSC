# Quarantined validation-battery artifacts

Files in this directory are retained as failure evidence only. They must not be
compared, selected, promoted, or presented as valid checkpoint evaluations.
Each artifact requires an audit twin that states the exact failure and scope.

- `dicos-f-03_epoch111.mislabeled-checkpoint.json`: claimed epoch 111 but
  evaluated inherited B0 epoch 90; see
  `audit/v3_battery_f03_quarantine_20260815.{json,md}`.
- `dicos-f-02_epoch90.zero-truth-relative-error.json`: divided relative energy
  error by a numerical floor for zero-truth events, yielding RMSE 5.332e8; the
  report is quarantined as a whole and B0 is queued for a clean rerun under the
  corrected evaluator. See
  `audit/v3_battery_zero_truth_quarantine_20260815.{json,md}`.
- `v3-s1-axis_epoch19.zero-truth-relative-error.json`: an old-evaluator child
  survived the attempted `battery5` wrapper stop and completed later. The
  autonomous importer rejected it before acceptance; see the same zero-truth
  quarantine audit twins.
