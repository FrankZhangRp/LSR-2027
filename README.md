# LSR-2027

Proposed MICCAI 2027 challenge for lumbar CT super-resolution and quantitative bone biomarker estimation. All three tracks use ex vivo vertebral specimens.

| Track | Input | Reference and output |
| --- | --- | --- |
| 1. Micro-PCCT super-resolution | One routine CT volume | Reconstruct on the 105 μm Micro-PCCT grid. Fixed and cross-protocol evaluation share one leaderboard. |
| 2. Clinical-grade PCCT super-resolution | Coarser clinical-grade PCCT of a vertebral specimen | Reconstruct to the finer PCCT sampling of the same specimen. The proposed track targets a smaller sampling change. |
| 3. Bone biomarker estimation | Original routine CT | Submit 3D trabecular BV/TV per vertebra as a percentage. Score mean absolute error in percentage points against qualified Micro-PCCT measurements. |

The proposed split for the Micro-PCCT-based tracks is 30 public specimens for development, 10 private specimens for feedback, and 10 separate private specimens for final blind scoring. The clinical-grade PCCT pairs, geometry and split counts are pending verification. Scans from the same specimen stay in the same split across tracks.

## Published LumbarSR resources

The source release includes paired routine CT and 105 μm Micro-PCCT for 30 specimens. Its registration, reconstruction and morphometry baselines document the published benchmark that underpins the LSR-2027 proposal.

- [Scientific Data descriptor](https://doi.org/10.1038/s41597-026-07748-5)
- [Public dataset on Zenodo](https://doi.org/10.5281/zenodo.19404387)
- [Published LumbarSR baselines](https://github.com/FrankZhangRp/LumbarSR-Challenge)

## Task 3 scoring preview

Run the dependency-free scalar BV/TV evaluator on the bundled synthetic data. See the [evaluation guide](evaluation/README.md) for input checks, scoring and regression tests. The official ranking and reference workflow will be specified with the challenge design.

```sh
python3 evaluation/score_bvtv.py --reference evaluation/examples/reference.csv --predictions evaluation/examples/predictions.csv
```

## Website

The static site lives in `docs/` and publishes from the `main` branch's `/docs` folder. Preview it with `python3 -m http.server --directory docs 8000` and open `http://localhost:8000/`. [LSR-2027 challenge site](https://frankzhangrp.github.io/LSR-2027/)

The six comparison images are public ex vivo images. The Micro-PCCT reference has 105 μm isotropic sampling. The paired routine CT uses 586 μm in-plane sampling, 1,000 μm slices and a soft-tissue kernel. [Original LumbarSR viewer](https://frankzhangrp.github.io/LumbarSR-Challenge/compare.html)
