from __future__ import annotations

import argparse
import json
import random
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Create low-shot fine-tuning splits from the S-BIAD840 28.5C external test set."
    )
    p.add_argument("--source_split", required=True, help="Source JSON containing the embryo pool.")
    p.add_argument("--out_dir", required=True, help="Directory to write fine-tune split JSONs.")
    p.add_argument("--train_counts", default="12,24", help="Comma-separated train embryo counts, e.g. 12,24")
    p.add_argument("--val_count", type=int, default=12, help="Validation embryo count for every split.")
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--prefix", default="28C5_sbiad840")
    return p.parse_args()


def jload(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def jdump(path: Path, obj: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    args = parse_args()
    source_split = Path(args.source_split)
    out_dir = Path(args.out_dir)

    src = jload(source_split)
    pool = list(dict.fromkeys(src.get("train", []) + src.get("val", []) + src.get("test", [])))
    if not pool:
        raise ValueError(f"No embryo ids found in {source_split}")

    train_counts = [int(x.strip()) for x in args.train_counts.split(",") if x.strip()]
    if not train_counts:
        raise ValueError("No train counts requested.")

    rng = random.Random(int(args.seed))
    shuffled = list(pool)
    rng.shuffle(shuffled)

    manifest: list[dict[str, Any]] = []
    for train_count in train_counts:
        if train_count <= 0:
            raise ValueError(f"train_count must be positive, got {train_count}")
        if train_count + int(args.val_count) >= len(shuffled):
            raise ValueError(
                f"Requested train={train_count} val={args.val_count} but pool has only {len(shuffled)} embryos"
            )

        train = shuffled[:train_count]
        val = shuffled[train_count:train_count + int(args.val_count)]
        test = shuffled[train_count + int(args.val_count):]
        split = {"train": train, "val": val, "test": test}

        name = f"{args.prefix}_ft{train_count}_v{args.val_count}_seed{args.seed}.json"
        out_path = out_dir / name
        jdump(out_path, split)
        manifest.append(
            {
                "name": name,
                "train": len(train),
                "val": len(val),
                "test": len(test),
                "seed": int(args.seed),
                "source": str(source_split),
            }
        )
        print(f"[WROTE] {out_path} train={len(train)} val={len(val)} test={len(test)}")

    manifest_path = out_dir / f"{args.prefix}_manifest_seed{args.seed}.json"
    jdump(manifest_path, {"splits": manifest})
    print(f"[WROTE] {manifest_path}")


if __name__ == "__main__":
    main()
