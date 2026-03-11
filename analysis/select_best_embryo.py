#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import math
from pathlib import Path


def main() -> None:
    ap = argparse.ArgumentParser(description="Select best embryo by minimal rmse_resid, tie-breaking by max_abs_resid.")
    ap.add_argument("--embryo_csv", required=True)
    args = ap.parse_args()

    path = Path(args.embryo_csv)
    best: tuple[tuple[float, float], str] | None = None
    with path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            eid = str(row["eid"])
            rr = float(row["rmse_resid"])
            mx = float(row["max_abs_resid"])
            if not (math.isfinite(rr) and math.isfinite(mx)):
                continue
            key = (rr, mx)
            if best is None or key < best[0]:
                best = (key, eid)

    if best is None:
        raise SystemExit("No valid rows found in embryo.csv")
    print(best[1])


if __name__ == "__main__":
    main()
