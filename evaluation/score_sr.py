"""Score registered 3D LSR-2027 reconstruction crops on a fixed evaluation mask."""

import argparse
from array import array
from collections import defaultdict
from dataclasses import dataclass
import gzip
import json
import math
from pathlib import Path
import re
from statistics import fmean
import struct
import sys


WINDOW = 7
MAX_VOXELS = 2**22
MAX_CASES = 256
MAX_INTENSITY = 1e6
PSNR_CAP_DB = 120.0
NIFTI_TYPES = {2: "B", 4: "h", 8: "i", 16: "f", 64: "d", 256: "b", 512: "H", 768: "I"}
CASE_ID = re.compile(r"[A-Za-z0-9_-]{1,80}")


@dataclass(frozen=True)
class Volume:
    shape: tuple
    affine: tuple
    units: int
    values: array


def affine_from_header(header, endian):
    qform, sform = struct.unpack_from(endian + "2h", header, 252)
    if sform > 0:
        affine = struct.unpack_from(endian + "12f", header, 280)
    elif qform > 0:
        qfac, dx, dy, dz = struct.unpack_from(endian + "4f", header, 76)
        b, c, d, tx, ty, tz = struct.unpack_from(endian + "6f", header, 256)
        if not all(map(math.isfinite, (qfac, dx, dy, dz, b, c, d, tx, ty, tz))):
            raise ValueError("qform contains nonfinite values")
        if min(dx, dy, dz) <= 0 or qfac not in (-1, 0, 1):
            raise ValueError("invalid qform spacing or handedness")
        squared = b*b + c*c + d*d
        if squared > 1.000001:
            raise ValueError("invalid qform quaternion")
        if squared >= 1:
            norm = math.sqrt(squared)
            b, c, d = b/norm, c/norm, d/norm
        a = math.sqrt(max(0.0, 1-squared))
        dz *= -1 if qfac < 0 else 1
        affine = (
            (a*a+b*b-c*c-d*d)*dx, 2*(b*c-a*d)*dy, 2*(b*d+a*c)*dz, tx,
            2*(b*c+a*d)*dx, (a*a+c*c-b*b-d*d)*dy, 2*(c*d-a*b)*dz, ty,
            2*(b*d-a*c)*dx, 2*(c*d+a*b)*dy, (a*a+d*d-b*b-c*c)*dz, tz,
        )
    else:
        raise ValueError("NIfTI requires an sform or qform")
    if not all(map(math.isfinite, affine)):
        raise ValueError("affine contains nonfinite values")
    a, b, c, _, d, e, f, _, g, h, i, _ = affine
    determinant = a*(e*i-f*h) - b*(d*i-f*g) + c*(d*h-e*g)
    if determinant == 0:
        raise ValueError("singular affine")
    return affine


def is_nifti(name):
    return isinstance(name, str) and name.endswith((".nii", ".nii.gz"))


def read_volume(path):
    if not path.is_file() or path.is_symlink():
        raise ValueError("expected a regular NIfTI file")
    opener = gzip.open if path.name.endswith(".nii.gz") else open
    with opener(path, "rb") as stream:
        header = stream.read(348)
        if len(header) < 348 or header[344:348] != b"n+1\0":
            raise ValueError("expected NIfTI-1 single-file format")
        endian = "<" if header[:4] == struct.pack("<i", 348) else ">"
        if struct.unpack_from(endian + "i", header)[0] != 348:
            raise ValueError("invalid NIfTI header length")
        dimension_count, nx, ny, nz = struct.unpack_from(endian + "4h", header, 40)
        if dimension_count != 3 or min(nx, ny, nz) < WINDOW:
            raise ValueError(f"expected 3D NIfTI with each axis at least {WINDOW} voxels")
        shape = (nx, ny, nz)
        count = math.prod(shape)
        if count > MAX_VOXELS:
            raise ValueError(f"evaluation crop exceeds {MAX_VOXELS} voxels")
        datatype, bitpix = struct.unpack_from(endian + "2h", header, 70)
        if datatype not in NIFTI_TYPES:
            raise ValueError("unsupported NIfTI voxel datatype")
        values = array(NIFTI_TYPES[datatype])
        if bitpix != 8 * values.itemsize:
            raise ValueError("invalid NIfTI bit depth")
        offset, slope, intercept = struct.unpack_from(endian + "3f", header, 108)
        if not math.isfinite(offset) or not offset.is_integer() or not 352 <= offset <= 2**20:
            raise ValueError("invalid NIfTI voxel offset")
        units = header[123] & 7
        if units not in (0, 2):
            raise ValueError("expected NIfTI spatial units in mm or unspecified")
        affine = affine_from_header(header, endian)
        stream.read(int(offset) - 348)
        length = count * values.itemsize
        raw = stream.read(length + 1)
        if len(raw) != length:
            raise ValueError("NIfTI payload size does not match header")
        values.frombytes(raw)
    if (endian == "<") != (sys.byteorder == "little"):
        values.byteswap()
    if slope == 0:
        slope, intercept = 1.0, 0.0
    if not all(map(math.isfinite, (slope, intercept))):
        raise ValueError("invalid NIfTI intensity scaling")
    if (slope, intercept) != (1.0, 0.0):
        values = array("d", (value*slope + intercept for value in values))
    return Volume(shape, affine, units, values)


def aligned(ref, other):
    return (ref.shape == other.shape and ref.units == other.units
            and all(abs(a-b) <= 1e-4 for a, b in zip(ref.affine, other.affine)))


def sums_along(values, shape, axis):
    """Valid box sums along one axis of a flattened, x-fastest grid."""
    stride = math.prod(shape[:axis])
    width = shape[axis]
    output_width = width - WINDOW + 1
    step = stride * width
    output_step = stride * output_width
    sums = array("d", [0]) * (len(values) // step * output_step)
    for group, start in enumerate(range(0, len(values), step)):
        for offset in range(stride):
            first = start + offset
            current = sum(values[first:first+WINDOW*stride:stride])
            destination = group * output_step + offset
            sums[destination] = current
            for index in range(1, output_width):
                current += values[first+(index+WINDOW-1)*stride] - values[first+(index-1)*stride]
                sums[destination+index*stride] = current
    new_shape = shape[:axis] + (output_width,) + shape[axis+1:]
    return sums, new_shape


def window_sums(values, shape):
    for axis in range(3):
        values, shape = sums_along(values, shape, axis)
    return values


def ssim_3d(reference, prediction, mask, shape, bounds):
    """Mean SSIM across uniform 7×7×7 windows wholly within the mask."""
    count = WINDOW**3
    low, high = bounds
    dynamic_range = high - low
    c1, c2 = (0.01 * dynamic_range)**2, (0.03 * dynamic_range)**2
    eligible = window_sums(mask, shape)
    if count not in eligible:
        raise ValueError("mask has no complete 3D SSIM window")
    first = array("d", (min(high, max(low, value))-low for value in reference))
    second = array("d", (min(high, max(low, value))-low for value in prediction))
    sx = window_sums(first, shape)
    sy = window_sums(second, shape)
    sxx = window_sums(array("d", (value*value for value in first)), shape)
    syy = window_sums(array("d", (value*value for value in second)), shape)
    sxy = window_sums(array("d", (a*b for a, b in zip(first, second))), shape)
    total = 0.0
    windows = 0
    for size, x, y, xx, yy, xy in zip(eligible, sx, sy, sxx, syy, sxy):
        if size != count:
            continue
        mean_x, mean_y = x/count, y/count
        var_x = max(0.0, (xx - x*mean_x)/(count - 1))
        var_y = max(0.0, (yy - y*mean_y)/(count - 1))
        cov = (xy - x*mean_y)/(count - 1)
        luminance = (2*mean_x*mean_y + c1)/(mean_x**2 + mean_y**2 + c1)
        structure = (2*cov + c2)/(var_x + var_y + c2)
        total += max(-1.0, min(1.0, luminance*structure))
        windows += 1
    return total/windows


def measure(ref, pred, mask, bounds):
    if not aligned(ref, pred) or not aligned(ref, mask):
        raise ValueError("prediction and mask must match the reference grid")
    signed = absolute = squared = 0.0
    voxels = 0
    for r, p, m in zip(ref.values, pred.values, mask.values):
        if not -MAX_INTENSITY <= r <= MAX_INTENSITY or not -MAX_INTENSITY <= p <= MAX_INTENSITY:
            raise ValueError("nonfinite or out-of-range voxel value")
        if m not in (0, 1):
            raise ValueError("evaluation mask must contain only 0 and 1")
        if m:
            difference = p - r
            signed += difference
            absolute += abs(difference)
            squared += difference**2
            voxels += 1
    if not voxels:
        raise ValueError("evaluation mask is empty")
    rmse = math.sqrt(squared/voxels)
    dynamic_range = bounds[1] - bounds[0]
    psnr = PSNR_CAP_DB if rmse == 0 else min(PSNR_CAP_DB, 20*math.log10(dynamic_range/rmse))
    return {
        "mae": absolute/voxels, "rmse": rmse, "bias": signed/voxels, "psnr": psnr,
        "ssim": ssim_3d(ref.values, pred.values, mask.values, ref.shape, bounds),
    }


def manifest_cases(path):
    with path.open(encoding="utf-8") as stream:
        contents = stream.read(2**20 + 1)
    if len(contents) > 2**20:
        raise ValueError("reference manifest is too large")
    data = json.loads(contents)
    if not isinstance(data, dict):
        raise ValueError("reference manifest must be an object")
    bounds = data.get("range")
    if (not isinstance(bounds, list) or len(bounds) != 2
            or not all(type(v) in (int, float) and -MAX_INTENSITY <= v <= MAX_INTENSITY for v in bounds)
            or bounds[1] - bounds[0] < 1):
        raise ValueError("manifest range must be two ordered finite intensities at least 1 unit apart")
    cases = data.get("cases")
    if not isinstance(cases, list) or not 1 <= len(cases) <= MAX_CASES:
        raise ValueError(f"manifest requires 1 to {MAX_CASES} cases")
    case_ids, groups = set(), set()
    for case in cases:
        if not isinstance(case, dict):
            raise ValueError("manifest case must be an object")
        for field in ("case_id", "specimen_id", "protocol"):
            if not isinstance(case.get(field), str) or not case[field].strip():
                raise ValueError(f"manifest case requires a nonempty {field}")
        case_id = case["case_id"]
        group = (case["specimen_id"], case["protocol"])
        if not CASE_ID.fullmatch(case_id) or case_id in case_ids or group in groups:
            raise ValueError("case ID is invalid or case ID/specimen-protocol is duplicated")
        case_ids.add(case_id)
        groups.add(group)
        for field in ("reference", "mask"):
            name = case.get(field)
            if not is_nifti(name) or Path(name).name != name:
                raise ValueError(f"{field} must be a volume filename")
    return bounds, cases


def evaluate(reference, predictions):
    bounds, cases = manifest_cases(reference / "manifest.json")
    prediction_names = {}
    for file in predictions.iterdir():
        if not is_nifti(file.name):
            raise ValueError("prediction directory contains an unexpected file")
        identifier = file.name.removesuffix(".gz").removesuffix(".nii")
        if identifier in prediction_names:
            raise ValueError("prediction directory contains duplicate case IDs")
        prediction_names[identifier] = file
    expected = {case["case_id"] for case in cases}
    if expected != prediction_names.keys():
        raise ValueError("prediction case set does not match the reference")
    by_specimen = defaultdict(list)
    for case in cases:
        ref = read_volume(reference / case["reference"])
        pred = read_volume(prediction_names[case["case_id"]])
        mask = read_volume(reference / case["mask"])
        by_specimen[case["specimen_id"]].append(measure(ref, pred, mask, bounds))
    scores = {
        key: fmean(fmean(case[key] for case in group) for group in by_specimen.values())
        for key in ("mae", "rmse", "bias", "psnr", "ssim")
    }
    return {**scores, "n_specimens": len(by_specimen)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference", required=True, type=Path)
    parser.add_argument("--predictions", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        scores = evaluate(args.reference, args.predictions)
        args.output.write_text(json.dumps(scores, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    except (EOFError, OSError, ValueError) as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()
