# LSR-2027 evaluation preview

The scoring code runs on Python 3.9 or later with the standard library. See the [evaluation protocol](protocol.md) for the clinical rationale, track-specific endpoints, ranking, and validation plan.

## T1 and T2 image reconstruction

[score_sr.py](score_sr.py) scores registered NIfTI-1 crops on the organizer's evaluation mask. The same code serves both tasks. Each task and phase supplies its own reference manifest, masks, and fixed intensity range.

```sh
python3 evaluation/score_sr.py --reference path/to/reference \
  --predictions path/to/predictions --output scores.json
```

`reference/manifest.json` describes the intensity range and expected cases. Each case links its target image and a binary 3D evaluation mask in the reference directory. The predictions directory contains one `<case_id>.nii.gz` or `<case_id>.nii` per case.

```json
{
  "range": [-1000, 2000],
  "cases": [
    {
      "case_id": "example_01",
      "specimen_id": "example",
      "protocol": "soft",
      "reference": "reference.nii.gz",
      "mask": "voi.nii.gz"
    }
  ]
}
```

Output JSON fields are `mae`, `rmse`, `bias`, `psnr`, `ssim`, and `n_specimens`. The intensity errors use the supplied NIfTI's scaled intensity units. PSNR uses the fixed manifest range and reports dB. SSIM uses fully masked three-dimensional windows. Each metric is averaged over the required protocol volumes within a specimen and then across specimens. The code rejects invalid files, missing or additional cases, nonbinary or insufficient masks, nonfinite values, and mismatched reference grids. It evaluates crops up to 4,194,304 voxels with at least seven voxels per dimension. Prediction images must already use the target grid. The scorer checks dimensions, NIfTI spatial unit codes, and the voxel-to-world affine from sform or qform.

## T3 bone volume fraction

[score_bvtv.py](score_bvtv.py) evaluates per-specimen 3D trabecular bone volume fraction (BV/TV) on **ex vivo vertebral specimens**. The scalar reference is produced by the organizer's independently qualified VOI and segmentation pipeline.

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

Both inputs must have the exact ordered header `specimen_id,bvtv_percent`, followed by one row per specimen. Use percentages from 0 to 100. For example, submit 20 for a BV/TV of 20%. Surrounding identifier whitespace is stripped. Identifiers are case-sensitive. Every reference identifier must appear exactly once in predictions. Rows are joined by identifier.

The scorer rejects empty datasets, blank or duplicate identifiers, malformed rows, nonnumeric, nonfinite or out-of-range percentages, and mismatched specimen sets. Errors go to stderr with exit code 2. Successful JSON results go to stdout. MAE averages the absolute prediction-minus-reference error. Signed bias averages the prediction-minus-reference error. Both use equal specimen weights and report **percentage points**.

## Tests

Run the three tracks' scoring regression checks with `python3 -m unittest discover -s evaluation -p 'test_*.py'`.
