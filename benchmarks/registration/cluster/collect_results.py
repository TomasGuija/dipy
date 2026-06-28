"""Collect per-pair cluster benchmark outputs into one results JSON.

Example
-------
python benchmarks/registration/cluster/collect_results.py \
    --out-dir outputs/oasis2_cluster_run \
    --pairs data/oasis2_pairs.csv \
    --n 100
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import statistics

METRIC_NAMES = ("ncc", "nmi")
OVERLAP_SECTIONS = ("whole_brain", "mean_labels")
OVERLAP_METRICS = ("dice", "jaccard")
def read_json(path: Path) -> dict:
    with path.open() as f:
        return json.load(f)


def read_pairs(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as f:
        rows = list(csv.DictReader(f))

    required = {"fixed_path", "moving_path"}
    missing = required - set(rows[0]) if rows else required
    if missing:
        raise ValueError(f"Pair CSV is missing columns: {sorted(missing)}")
    return rows


def select_pairs(rows: list[dict[str, str]], n: int) -> list[dict[str, str]]:
    if n < 0:
        raise ValueError(f"Requested n={n}, but n must be non-negative.")
    if n > len(rows):
        raise ValueError(f"Requested n={n}, but only found {len(rows)} pairs.")
    return rows[:n]


def summarize_timings(samples: list[dict]) -> dict:
    summary = {}

    available_keys = sorted(
        {
            key
            for sample in samples
            for key in sample.get("timings", {})
        }
    )

    for key in available_keys:
        values = [
            sample["timings"][key]
            for sample in samples
            if key in sample.get("timings", {})
        ]
        if not values:
            continue

        summary[key] = mean_std(values)

    return summary


def get_pair_id(row: dict[str, str], index: int) -> str:
    pair_id = row.get("pair_id", "").strip()
    return pair_id or f"pair_{index:04d}"


def mean_std(values: list[float]) -> dict:
    return {
        "mean": statistics.mean(values),
        "std": statistics.stdev(values) if len(values) > 1 else 0.0,
    }


def summarize(samples: list[dict]) -> dict:
    summary = {}
    methods = sorted({method for sample in samples for method in sample["metrics"]})

    for method in methods:
        method_summary = {"n": len(samples)}
        for metric in METRIC_NAMES:
            values = [
                sample["metrics"][method][metric]
                for sample in samples
                if method in sample["metrics"]
            ]
            method_summary[metric] = mean_std(values)

            if method == "baseline":
                continue

            gain_values = [
                sample["gains_vs_baseline"][method][metric]
                for sample in samples
                if method in sample["gains_vs_baseline"]
            ]
            method_summary[f"{metric}_gain_vs_baseline"] = mean_std(gain_values)
        summary[method] = method_summary

    return summary


def summarize_overlap(samples: list[dict]) -> dict:
    summary = {}
    methods = sorted(
        method for sample in samples for method in sample.get("overlap_metrics", {})
    )

    for method in methods:
        method_samples = [
            sample["overlap_metrics"][method]
            for sample in samples
            if method in sample.get("overlap_metrics", {})
        ]
        method_summary = {"n": len(method_samples)}

        for section in OVERLAP_SECTIONS:
            method_summary[section] = {}
            for metric in OVERLAP_METRICS:
                values = [sample[section][metric] for sample in method_samples]
                method_summary[section][metric] = mean_std(values)
        summary[method] = method_summary

    return summary


def collect(
    out_dir: Path,
    pairs_path: Path,
    n: int,
) -> dict:
    rows = select_pairs(read_pairs(pairs_path), n)
    sample_paths = [
        out_dir / get_pair_id(row, index) / "sample_result.json"
        for index, row in enumerate(rows, start=1)
    ]

    if not sample_paths:
        raise FileNotFoundError(f"No sample_result.json files found under {out_dir}")

    missing_paths = [path for path in sample_paths if not path.exists()]
    if missing_paths:
        missing = "\n".join(str(path) for path in missing_paths)
        raise FileNotFoundError(f"Missing sample_result.json files:\n{missing}")

    samples = [read_json(path) for path in sample_paths]
    return {
        "metadata": {
            "out_dir": str(out_dir),
            "n_pairs": len(samples),
            "collected_from_cluster_jobs": True,
            "pairs_file": str(pairs_path),
            "n": n,
        },
        "samples": samples,
        "summary": summarize(samples),
        "overlap_summary": summarize_overlap(samples),
        "timing_summary": summarize_timings(samples),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Collect registration benchmark cluster outputs."
    )
    parser.add_argument("--out-dir", required=True, type=Path)
    parser.add_argument("--out-json", type=Path, default=None)
    parser.add_argument(
        "--pairs",
        type=Path,
        required=True,
        help="Pair CSV used by the benchmark.",
    )
    parser.add_argument(
        "--n",
        type=int,
        required=True,
        help="Collect the first N pairs from the CSV.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    out_json = args.out_json or args.out_dir / "benchmark_results.json"
    results = collect(args.out_dir, args.pairs, args.n)
    with out_json.open("w") as f:
        json.dump(results, f, indent=2)
    print(f"Collected {len(results['samples'])} samples into: {out_json}")


if __name__ == "__main__":
    main()
