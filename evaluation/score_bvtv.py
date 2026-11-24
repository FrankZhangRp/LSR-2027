"""LSR-2027 Task 3 BV/TV development preview; not a frozen challenge evaluator."""

import argparse
import csv
import json
import math
from pathlib import Path
from statistics import fmean


def read_scores(path):
    """Read one finite BV/TV percentage per unique specimen."""
    scores = {}
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream, strict=True)
        if reader.fieldnames != ["specimen_id", "bvtv_percent"]:
            raise ValueError(f"{path}: expected header specimen_id,bvtv_percent")
        for row in reader:
            location = f"{path}: line {reader.line_num}"
            if None in row or any(value is None for value in row.values()):
                raise ValueError(f"{location}: expected exactly two columns")
            specimen_id = row["specimen_id"].strip()
            if not specimen_id:
                raise ValueError(f"{location}: blank specimen_id")
            if specimen_id in scores:
                raise ValueError(f"{location}: duplicate specimen_id")
            try:
                value = float(row["bvtv_percent"])
            except ValueError:
                raise ValueError(f"{location}: bvtv_percent must be numeric") from None
            if not math.isfinite(value) or not 0 <= value <= 100:
                raise ValueError(f"{location}: bvtv_percent must be finite and within [0, 100]")
            scores[specimen_id] = value
    if not scores:
        raise ValueError(f"{path}: no specimen rows")
    return scores


def evaluate(reference, predictions):
    """Return equally weighted errors, with signed bias = prediction - reference."""
    missing = reference.keys() - predictions.keys()
    extra = predictions.keys() - reference.keys()
    if missing or extra:
        raise ValueError(f"specimen mismatch: {len(missing)} missing and {len(extra)} extra prediction rows")
    if not reference:
        raise ValueError("no specimens to evaluate")
    errors = [predictions[key] - reference[key] for key in sorted(reference)]
    return {
        "specimen_count": len(errors),
        "mae_percentage_points": fmean(abs(error) for error in errors),
        "bias_percentage_points": fmean(errors),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference", required=True, type=Path)
    parser.add_argument("--predictions", required=True, type=Path)
    args = parser.parse_args()
    try:
        result = evaluate(read_scores(args.reference), read_scores(args.predictions))
    except (OSError, UnicodeError, csv.Error, ValueError) as error:
        parser.error(str(error))
    print(json.dumps(result, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
