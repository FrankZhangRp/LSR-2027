from array import array
import gzip
import json
import math
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest

import score_sr


SHAPE = (8, 9, 10)
AFFINE = (0.2, 0, 0, 1, 0, 0.2, 0, 2, 0, 0, 0.3, 3)


def write_nifti(path, values, *, affine=AFFINE, endian="<", slope=1.0, intercept=0.0):
    header = bytearray(352)
    struct.pack_into(endian+"i", header, 0, 348)
    struct.pack_into(endian+"8h", header, 40, 3, *SHAPE, 1, 1, 1, 1)
    struct.pack_into(endian+"2h", header, 70, 16, 32)
    struct.pack_into(endian+"3f", header, 108, 352, slope, intercept)
    header[123] = 2
    struct.pack_into(endian+"h", header, 254, 1)
    struct.pack_into(endian+"12f", header, 280, *affine)
    header[344:348] = b"n+1\0"
    count = math.prod(SHAPE)
    if isinstance(values, (int, float)):
        values = [values] * count
    payload = bytes(header) + struct.pack(f"{endian}{count}f", *values)
    if path.name.endswith(".gz"):
        path.write_bytes(gzip.compress(payload, mtime=0))
    else:
        path.write_bytes(payload)


class ScorerTest(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.ref = self.root / "ref"
        self.pred = self.root / "pred"
        self.ref.mkdir()
        self.pred.mkdir()
        write_nifti(self.ref / "reference.nii.gz", 100.0)
        write_nifti(self.ref / "mask.nii", 1)
        self.cases = []

    def case(self, identifier, specimen, protocol, prediction):
        self.cases.append({
            "case_id": identifier, "specimen_id": specimen, "protocol": protocol,
            "reference": "reference.nii.gz", "mask": "mask.nii",
        })
        write_nifti(self.pred / f"{identifier}.nii.gz", prediction)
        (self.ref / "manifest.json").write_text(
            json.dumps({"range": [-1000, 2000], "cases": self.cases}), encoding="utf-8"
        )

    def test_exact_match_and_named_json_keys(self):
        self.case("test1", "sample1", "protocol1", 100.0)
        path = self.root / "scores.json"
        result = subprocess.run(
            [sys.executable, score_sr.__file__, "--reference", str(self.ref),
             "--predictions", str(self.pred), "--output", str(path)],
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(path.read_text()), {
            "mae": 0.0, "rmse": 0.0, "bias": 0.0, "psnr": 120.0,
            "ssim": 1.0, "n_specimens": 1,
        })

    def test_fixed_range_and_subject_level_weights(self):
        self.case("test1", "sample1", "protocol1", 80.0)
        self.case("test2", "sample1", "protocol2", 110.0)
        self.case("test3", "sample2", "protocol1", 150.0)
        scores = score_sr.evaluate(self.ref, self.pred)
        self.assertEqual(scores["n_specimens"], 2)
        self.assertAlmostEqual(scores["bias"], 22.5)
        self.assertAlmostEqual(scores["mae"], 32.5)
        self.assertAlmostEqual(scores["rmse"], 32.5)
        self.assertAlmostEqual(
            scores["psnr"], 5*math.log10(3000/20) + 5*math.log10(3000/10) + 10*math.log10(3000/50)
        )
        c1 = 30**2
        expected_ssim = (
            (2 * 1100 * 1080 + c1)/(1100**2 + 1080**2 + c1)/4
            + (2 * 1100 * 1110 + c1)/(1100**2 + 1110**2 + c1)/4
            + (2 * 1100 * 1150 + c1)/(1100**2 + 1150**2 + c1)/2
        )
        self.assertAlmostEqual(scores["ssim"], expected_ssim)

    def test_mask_excludes_outside_values_from_both_metrics(self):
        nx, ny, nz = SHAPE
        mask = [int(x < 7 and y < 7 and z < 7) for z in range(nz) for y in range(ny) for x in range(nx)]
        self.case("test1", "sample1", "protocol1", [100 if m else 1500 for m in mask])
        write_nifti(self.ref / "mask.nii", mask)
        scores = score_sr.evaluate(self.ref, self.pred)
        self.assertEqual(scores["mae"], 0.0)
        self.assertEqual(scores["ssim"], 1.0)

    def test_ssim_nonconstant_covariance_matches_direct_window(self):
        n = 7**3
        ref = array("d", [120 + i%34 for i in range(n)])
        pred = array("d", [95 + i%29 for i in range(n)])
        mean_ref = sum(ref)/n
        mean_pred = sum(pred)/n
        x = [v - mean_ref for v in ref]
        y = [v - mean_pred for v in pred]
        covariance = sum(a*b for a, b in zip(x, y))/(n - 1)
        variance_sum = (sum(a*a for a in x) + sum(b*b for b in y))/(n - 1)
        c1, c2 = 30**2, 90**2
        expected = (2*mean_ref*mean_pred + c1)/(mean_ref**2 + mean_pred**2 + c1)
        expected *= (2*covariance + c2)/(variance_sum + c2)
        estimate = score_sr.ssim_3d(ref, pred, array("B", [1]) * n, (7, 7, 7), (0, 3000))
        self.assertAlmostEqual(estimate, expected, places=12)

    def test_big_endian_scaled_input(self):
        self.case("test1", "sample1", "protocol1", 100.0)
        write_nifti(self.pred / "test1.nii.gz", 52.0, endian=">", slope=2.0, intercept=-4.0)
        self.assertEqual(score_sr.evaluate(self.ref, self.pred)["mae"], 0.0)

    def test_rejects_grid_mismatch_and_nan(self):
        self.case("test1", "sample1", "protocol1", 100.0)
        bad = self.pred / "test1.nii.gz"
        write_nifti(bad, 100.0, affine=(*AFFINE[:-1], 3.2))
        with self.assertRaisesRegex(ValueError, "match the reference grid"):
            score_sr.evaluate(self.ref, self.pred)
        write_nifti(bad, float("nan"))
        with self.assertRaisesRegex(ValueError, "nonfinite"):
            score_sr.evaluate(self.ref, self.pred)

    def test_rejects_incomplete_mask_and_extra_case(self):
        self.case("test1", "sample1", "protocol1", 100.0)
        mask = [1] + [0] * (math.prod(SHAPE) - 1)
        write_nifti(self.ref / "mask.nii", mask)
        with self.assertRaisesRegex(ValueError, "no complete 3D SSIM window"):
            score_sr.evaluate(self.ref, self.pred)
        write_nifti(self.pred / "extra.nii.gz", 100.0)
        with self.assertRaisesRegex(ValueError, "case set"):
            score_sr.evaluate(self.ref, self.pred)


if __name__ == "__main__":
    unittest.main()
