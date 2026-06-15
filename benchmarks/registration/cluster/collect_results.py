"""Collect per-pair cluster benchmark outputs into one results JSON.

Example
-------
python benchmarks/registration/cluster/collect_results.py \
    --out-dir outputs/oasis2_cluster_run
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import statistics

METRIC_NAMES = ("ncc", "nmi")
OVERLAP_SECTIONS = ("whole_brain", "mean_labels")
OVERLAP_METRICS = ("dice", "jaccard")


def read_json(path: Path) -> dict:
    with path.open() as f:
        return json.load(f)


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


def collect(out_dir: Path) -> dict:
    sample_paths = sorted(out_dir.glob("*/sample_result.json"))
    if not sample_paths:
        raise FileNotFoundError(f"No sample_result.json files found under {out_dir}")

    samples = [read_json(path) for path in sample_paths]
    return {
        "metadata": {
            "out_dir": str(out_dir),
            "n_pairs": len(samples),
            "collected_from_cluster_jobs": True,
        },
        "samples": samples,
        "summary": summarize(samples),
        "overlap_summary": summarize_overlap(samples),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Collect registration benchmark cluster outputs."
    )
    parser.add_argument("--out-dir", required=True, type=Path)
    parser.add_argument("--out-json", type=Path, default=None)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    out_json = args.out_json or args.out_dir / "benchmark_results.json"
    results = collect(args.out_dir)
    with out_json.open("w") as f:
        json.dump(results, f, indent=2)
    print(f"Collected {len(results['samples'])} samples into: {out_json}")


if __name__ == "__main__":
    main()
