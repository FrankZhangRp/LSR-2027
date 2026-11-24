# LumbarSR 2027

Public website for the proposed MICCAI 2027 LumbarSR Challenge.

- [Challenge site](https://frankzhangrp.github.io/LumbarSR-2027/)
- [Scientific Data descriptor](https://doi.org/10.1038/s41597-026-07748-5)
- [Public dataset on Zenodo](https://doi.org/10.5281/zenodo.19404387)
- [Published LumbarSR baselines](https://github.com/FrankZhangRp/LumbarSR-Challenge)

The static site lives in `docs/` and publishes from `main:/docs` via GitHub Pages. Preview locally with `python3 -m http.server --directory docs 8000` and open `http://localhost:8000/`.

The six comparison images are the existing public ex vivo images from the [original LumbarSR viewer](https://frankzhangrp.github.io/LumbarSR-Challenge/compare.html). The reference images are 105 μm Micro-PCCT, and the companion clinical images use 586 μm in-plane sampling with 1,000 μm slices and a soft-tissue kernel. The paired views are for visual inspection. The published paper records the source dataset and its technical validation.
