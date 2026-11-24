# LSR-2027 Task 3 evaluation preview

Dependency-free Python 3 development preview for per-specimen 3D trabecular bone volume fraction (BV/TV) on **ex vivo vertebral specimens**. This is a candidate metric implementation, not the official frozen challenge evaluator. Reference qualification, ROI definition, segmentation, uncertainty assessment, and the final ranking protocol must be established separately before challenge evaluation.

From the repository root:

```sh
python3 evaluation/score_bvtv.py --reference evaluation/examples/reference.csv --predictions evaluation/examples/predictions.csv
```

The two CSV files are synthetic examples. Expected output:

```json
{
  "specimen_count": 2,
  "mae_percentage_points": 2.0,
  "bias_percentage_points": -1.0
}
```

Both inputs must have the exact ordered header `specimen_id,bvtv_percent`, followed by one row per specimen. Values are percentages from 0 to 100: `20` means 20%, not `0.20`. Surrounding identifier whitespace is stripped; identifiers are case-sensitive. Every reference identifier must appear exactly once in predictions, with no additional identifiers. Rows are joined by identifier, so row order does not affect results.

The scorer rejects empty datasets, blank or duplicate identifiers, malformed rows, nonnumeric/nonfinite/out-of-range percentages, and mismatched specimen sets. Errors go to stderr with exit code 2; successful JSON results go to stdout. MAE is the mean absolute prediction-minus-reference error; signed bias is the mean prediction-minus-reference error. Both use equal specimen weights and report **percentage points**, not relative percentage errors. This tool evaluates supplied scalar values; it does not extract BV/TV from images or validate reference measurements.

Run regression checks with `python3 -m unittest discover -s evaluation -p 'test_*.py'`.
