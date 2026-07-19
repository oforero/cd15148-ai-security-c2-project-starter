"""
Aggregate the poisoning experiment's evaluation results.

Reads every metrics.json produced by run_poisoning_experiment.sh (one folder per
run, named <condition>_<run-index>) and prints the mean accuracy per condition
and its drop versus the clean baseline.

Usage:
    python aggregate_poisoning_results.py [eval_root]

Defaults eval_root to classifier/results/poisoning_experiment relative to this file.
"""
import argparse
import glob
import json
import os
from collections import defaultdict

CONDITION_ORDER = ["clean", "random", "targeted", "confidence"]
DEFAULT_EVAL_ROOT = os.path.join(
    os.path.dirname(__file__), "classifier", "results", "poisoning_experiment"
)


def collect_accuracies(eval_root):
    """Map each condition to its list of accuracies across runs."""
    accuracies = defaultdict(list)
    for path in glob.glob(os.path.join(eval_root, "*", "metrics.json")):
        # Folder is named "<condition>_<run-index>", e.g. "confidence_2".
        condition = os.path.basename(os.path.dirname(path)).rsplit("_", 1)[0]
        with open(path) as f:
            accuracies[condition].append(json.load(f)["accuracy"])
    return accuracies


def print_comparison(accuracies):
    """Print a mean-accuracy table with the drop versus the clean baseline."""
    clean = accuracies.get("clean", [])
    clean_mean = sum(clean) / len(clean) if clean else None

    print("\n**Poisoning Strategy Comparison (accuracy on clean test set)**")
    header = f"{'Condition':<12}{'runs':>5}{'mean':>9}{'min':>9}{'max':>9}{'drop vs clean':>16}"
    print(header)

    for condition in CONDITION_ORDER:
        values = accuracies.get(condition, [])
        if not values:
            continue
        mean = sum(values) / len(values)
        if clean_mean is None or condition == "clean":
            drop = ""
        else:
            drop = f"{(clean_mean - mean) * 100:+.2f} pts"
        print(f"{condition:<12}{len(values):>5}{mean:>9.4f}{min(values):>9.4f}{max(values):>9.4f}{drop:>16}")

    print("\n(positive drop = poisoned model is worse than clean; target is >= 5.00 pts)")


def main():
    parser = argparse.ArgumentParser(description="Aggregate poisoning experiment results")
    parser.add_argument("eval_root", nargs="?", default=DEFAULT_EVAL_ROOT)
    args = parser.parse_args()

    accuracies = collect_accuracies(args.eval_root)
    if not accuracies:
        print(f"No metrics.json files found under {args.eval_root}")
        return
    print_comparison(accuracies)


if __name__ == "__main__":
    main()
