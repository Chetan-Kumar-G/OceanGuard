# Generated outputs

See `manifest.json` for row counts and column lists, and the top-level
`DATA_DICTIONARY.md` for field-by-field descriptions.

Integrity rules enforced by the generator:

1. `ground_truth_events.csv` is the answer key - do not join it into training features.
2. Train/val/test in every dataset is assigned at **event** level (`split` column
   on D1; propagate via `event_id`).
3. D2 rows with `state_type` in {INTERPOLATED, PREDICTED} and D4 `is_observed=False`
   rows are synthetic fill - never treat them as observations.
4. `evaluation_only/D8_evaluation.csv` is the only place future observations appear;
   it is for scoring forecasts, not for training them.
5. D5 relation labels come from the fixed residual thresholds in `config.used.yaml`
   (`evidence.support` / `evidence.contradict`).
