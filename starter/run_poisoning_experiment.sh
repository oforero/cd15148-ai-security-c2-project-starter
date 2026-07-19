#!/usr/bin/env bash
#
# Label-flip poisoning experiment: poison -> train -> evaluate, for every strategy.
#
# Compares the scaffold's random flip against targeted and confidence-based
# (model-informed) flips at the SAME <=10% budget, training each condition
# multiple times so the poisoning effect can be separated from training variance.
#
# Usage (from anywhere; paths resolve relative to this script):
#     bash run_poisoning_experiment.sh
#     FLIP_RATE=0.10 REPEATS=3 bash run_poisoning_experiment.sh
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ATTACKS="$SCRIPT_DIR/attacks"
CLASSIFIER="$SCRIPT_DIR/classifier"

FLIP_RATE="${FLIP_RATE:-0.10}"      # flip budget (<= 0.10 to stay within the rubric cap)
REPEATS="${REPEATS:-3}"             # trainings per condition (averages out GPU nondeterminism)
EVAL_ROOT="$CLASSIFIER/results/poisoning_experiment"

echo ">> Flip rate: $FLIP_RATE | Repeats per condition: $REPEATS"

# Fresh eval workspace so stale runs are not aggregated.
rm -rf "$EVAL_ROOT"
mkdir -p "$EVAL_ROOT"

# ---- Step 1: poison (one dataset per strategy) ----
cd "$ATTACKS"
for strat in random targeted confidence; do
  echo ">> Poisoning dataset: $strat"
  python 02_label_flip_poisoning.py --strategy "$strat" --flip-rate "$FLIP_RATE"
done

# ---- Step 2 + 3: train and evaluate each condition, REPEATS times ----
cd "$CLASSIFIER"
# Condition -> training data dir. "clean" is the baseline (no poisoning).
conditions=("clean:balanced_data"
            "random:poisoned_data_random"
            "targeted:poisoned_data_targeted"
            "confidence:poisoned_data_confidence")

for entry in "${conditions[@]}"; do
  cond="${entry%%:*}"
  datadir="${entry##*:}"
  for i in $(seq 1 "$REPEATS"); do
    ckpt="cnn_${cond}_${i}.pt"
    echo ">> Train [$cond] run $i on $datadir"
    python train.py --data-dir "$datadir" --checkpoint-name "$ckpt"
    echo ">> Eval  [$cond] run $i"
    python evaluate.py --model-path "checkpoints/$ckpt" \
      --test-dir balanced_data/test \
      --results-dir "$EVAL_ROOT/${cond}_${i}"
  done
done

# ---- Step 4: aggregate mean accuracy and drop vs clean ----
python "$SCRIPT_DIR/aggregate_poisoning_results.py" "$EVAL_ROOT"
