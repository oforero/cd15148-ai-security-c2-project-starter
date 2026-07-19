"""
Label-Flip Data Poisoning Attack

Copies the balanced dataset and flips a percentage of training labels
(moves images between receipt/non_receipt folders) to degrade model accuracy.

Three selection strategies (all keep the flip rate <= 10% of training labels):
  - random     : flip flip_ratio of EACH class, chosen at random (scaffold default).
  - targeted   : flip flip_ratio of the TOTAL labels, all from one class, chosen at random.
  - confidence : same budget/direction as targeted, but flip the examples the clean
                 model is MOST confident about (an informed, white-box poisoning attack).
                 Random noise gets averaged out; corrupting high-confidence boundary
                 anchors moves the decision boundary far more per flip.

Each strategy writes to its own dataset directory so runs do not clobber each other.

Usage:
    python 02_label_flip_poisoning.py                              # random symmetric (scaffold)
    python 02_label_flip_poisoning.py --strategy targeted --flip-rate 0.10
    python 02_label_flip_poisoning.py --strategy confidence --flip-rate 0.10
"""
import os
import shutil
import random
import argparse

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".gif", ".webp"}
CLASSES = ["receipt", "non_receipt"]
RESULTS_DIR = os.path.join(os.path.dirname(__file__), "results", "02_label_flip")
DEFAULT_CLEAN_MODEL = os.path.join(
    os.path.dirname(__file__), "..", "classifier", "checkpoints", "receipt_cnn_clean.pt"
)


def score_by_confidence(source_root, target_class, model_path):
    """
    Rank the training images of target_class by how confident the clean model is
    that they belong to target_class. Most-confident first.

    This is the "informed attacker" step: instead of flipping random examples, we
    identify the examples that most strongly anchor the model's notion of the class,
    so flipping them does maximum damage per label.

    torch is imported lazily so the random/targeted strategies do not require it.
    """
    import sys
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "classifier"))
    import torch
    from torchvision import transforms
    from PIL import Image
    from model import ReceiptCNN

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    transform = transforms.Compose([
        transforms.Resize((224, 224)),
        transforms.ToTensor(),
    ])

    model = ReceiptCNN().to(device)
    model.load_state_dict(torch.load(model_path, map_location=device, weights_only=True))
    model.eval()

    # ImageFolder orders classes alphabetically: non_receipt=0, receipt=1.
    # The model outputs P(receipt). Confidence that an image IS target_class is
    # that probability for receipt, or its complement for non_receipt.
    class_dir = os.path.join(source_root, "train", target_class)
    scored = []
    with torch.no_grad():
        for filename in os.listdir(class_dir):
            if os.path.splitext(filename)[1].lower() not in IMAGE_EXTENSIONS:
                continue
            path = os.path.join(class_dir, filename)
            image = transform(Image.open(path).convert("RGB")).unsqueeze(0).to(device)
            prob_receipt = model(image).item()
            confidence = prob_receipt if target_class == "receipt" else 1.0 - prob_receipt
            scored.append((filename, confidence))

    scored.sort(key=lambda pair: pair[1], reverse=True)
    return scored


def poison_dataset(source_root, target_root, flip_ratio=0.05, seed=42,
                   target_class=None, strategy="random", model_path=None):
    """
    Copy dataset and flip a percentage of training labels.

    Label flipping works by moving images between class folders:
    - A receipt image moved to non_receipt/ gets a flipped label
    - A non_receipt image moved to receipt/ gets a flipped label

    Only training labels are flipped, the test set stays clean so we can
    measure the true impact of poisoning on model performance.

    Args:
        source_root: Path to clean balanced dataset
        target_root: Path for poisoned dataset output
        flip_ratio: Fraction of training labels to flip (default 0.05 = 5%)
        seed: Random seed for reproducibility
        target_class: Class to flip FROM for directional strategies (default "receipt").
        strategy: "random" (symmetric, scaffold), "targeted" (directional, random
            selection), or "confidence" (directional, most-confident examples first).
        model_path: Clean model checkpoint used to score examples in "confidence" mode.
    """
    random.seed(seed)

    # Step 1: Copy the entire clean dataset to target
    if os.path.exists(target_root):
        shutil.rmtree(target_root)
    shutil.copytree(source_root, target_root)

    opposite = {"receipt": "non_receipt", "non_receipt": "receipt"}
    train_root = os.path.join(target_root, "train")

    # Snapshot the original file list for each class BEFORE moving anything.
    # If we listed folders while flipping, files just moved into a folder could
    # be re-selected and flipped back, corrupting the flip rate.
    original_files = {}
    for class_name in CLASSES:
        class_dir = os.path.join(train_root, class_name)
        original_files[class_name] = [
            f for f in os.listdir(class_dir)
            if os.path.isfile(os.path.join(class_dir, f))
            and os.path.splitext(f)[1].lower() in IMAGE_EXTENSIONS
        ]

    total_train = sum(len(files) for files in original_files.values())
    total_flipped = 0

    def _flip(class_name, filenames):
        """Move the given files from class_name into the opposite class folder."""
        opposite_dir = os.path.join(train_root, opposite[class_name])
        for filename in filenames:
            src = os.path.join(train_root, class_name, filename)
            # Encode the ORIGINAL class in the prefix so the file's true origin
            # is recoverable (visualize_flip relies on this) and collisions are avoided.
            dst = os.path.join(opposite_dir, f"flipped_{class_name}_{filename}")
            shutil.move(src, dst)
        return len(filenames)

    # Flip only TRAINING labels; the test set is left untouched.
    if strategy == "random":
        # Symmetric attack: flip flip_ratio of EACH class, selected at random.
        for class_name in CLASSES:
            n_flip = int(len(original_files[class_name]) * flip_ratio)
            total_flipped += _flip(class_name, random.sample(original_files[class_name], n_flip))
        mode = "random symmetric (both directions)"
    else:
        # Directional attacks: spend the whole flip_ratio budget on one class.
        tc = target_class or "receipt"
        n_flip = min(int(total_train * flip_ratio), len(original_files[tc]))
        if strategy == "targeted":
            # Same direction, but examples chosen at random.
            chosen = random.sample(original_files[tc], n_flip)
            mode = f"targeted random ({tc} -> {opposite[tc]})"
        elif strategy == "confidence":
            # Informed attacker: flip the examples the clean model is most sure about.
            snapshot = set(original_files[tc])
            ranked = [f for f, _ in score_by_confidence(source_root, tc, model_path) if f in snapshot]
            chosen = ranked[:n_flip]
            mode = f"confidence-ranked ({tc} -> {opposite[tc]})"
        else:
            raise ValueError(f"unknown strategy: {strategy!r}")
        total_flipped = _flip(tc, chosen)

    # Summary
    print("\n**Label-Flip Poisoning Summary**")
    print(f"Strategy: {strategy}")
    print(f"Mode: {mode}")
    print(f"Flip rate requested: {flip_ratio:.2%} | seed: {seed}")
    print(f"Total training images: {total_train}")
    print(f"Labels flipped:        {total_flipped}")
    print(f"Actual flip rate:      {total_flipped / total_train:.2%}" if total_train else "n/a")

    print("\nImage counts per split (poisoned dataset):")
    for split in ("train", "test"):
        for class_name in CLASSES:
            class_dir = os.path.join(target_root, split, class_name)
            if not os.path.isdir(class_dir):
                continue
            count = len([
                f for f in os.listdir(class_dir)
                if os.path.isfile(os.path.join(class_dir, f))
                and os.path.splitext(f)[1].lower() in IMAGE_EXTENSIONS
            ])
            print(f"  {split}/{class_name}: {count}")


def visualize_flip(source_root, target_root, num_images=5, output_dir=RESULTS_DIR, seed=42):
    """Save a grid showing clean labels beside their flipped poisoned labels."""
    flipped_samples = []

    for poisoned_label in CLASSES:
        poisoned_dir = os.path.join(target_root, "train", poisoned_label)
        if not os.path.isdir(poisoned_dir):
            continue

        for filename in os.listdir(poisoned_dir):
            poisoned_path = os.path.join(poisoned_dir, filename)
            if (
                not os.path.isfile(poisoned_path)
                or os.path.splitext(filename)[1].lower() not in IMAGE_EXTENSIONS
            ):
                continue

            original_label = None
            original_filename = None
            for cls in CLASSES:
                prefix = f"flipped_{cls}_"
                if filename.startswith(prefix):
                    original_label = cls
                    original_filename = filename[len(prefix):]
                    break

            if original_label is None:
                continue

            clean_path = os.path.join(
                source_root,
                "train",
                original_label,
                original_filename,
            )
            if os.path.exists(clean_path):
                flipped_samples.append({
                    "clean_path": clean_path,
                    "poisoned_path": poisoned_path,
                    "original_label": original_label,
                    "poisoned_label": poisoned_label,
                    "filename": original_filename,
                })

    if not flipped_samples:
        print("No flipped images found to visualize.")
        return None

    rng = random.Random(seed)
    sample_count = min(num_images, len(flipped_samples))
    samples = rng.sample(flipped_samples, sample_count)

    fig, axes = plt.subplots(sample_count, 2, figsize=(8, 3 * sample_count))
    if sample_count == 1:
        axes = [axes]

    for row, sample in enumerate(samples):
        clean_img = plt.imread(sample["clean_path"])
        poisoned_img = plt.imread(sample["poisoned_path"])

        axes[row][0].imshow(clean_img)
        axes[row][0].set_title(
            f"Clean: {sample['original_label']}\n{sample['filename']}",
            fontsize=9,
        )
        axes[row][0].axis("off")

        axes[row][1].imshow(poisoned_img)
        axes[row][1].set_title(
            f"Flipped label: {sample['poisoned_label']}\n"
            f"from {sample['original_label']}",
            fontsize=9,
        )
        axes[row][1].axis("off")

    fig.suptitle(
        f"Label Flip Poisoning Samples ({sample_count} images)",
        fontsize=12,
    )
    fig.tight_layout()

    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, f"label_flip_results_{sample_count}.png")
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)

    print(f"Label flip visualization saved to: {output_path}")
    return output_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Label-Flip Poisoning Attack")
    parser.add_argument(
        "--source",
        default=os.path.join(os.path.dirname(__file__),
                             "..", "classifier", "balanced_data"),
    )
    parser.add_argument(
        "--target", default=None,
        help="Poisoned dataset output dir. Defaults to "
             "../classifier/poisoned_data_<strategy> so strategies do not clobber each other.",
    )
    parser.add_argument("--flip-rate", type=float, default=0.05)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--visualize-count", type=int, default=5)
    parser.add_argument(
        "--results-dir", default=None,
        help="Visualization output dir. Defaults to results/02_label_flip/<strategy>.",
    )
    parser.add_argument(
        "--strategy", choices=["random", "targeted", "confidence"], default="random",
        help="Label selection strategy (default: random, the scaffold behavior).",
    )
    parser.add_argument(
        "--target-class", choices=CLASSES, default=None,
        help="Class to flip FROM for targeted/confidence strategies (default: receipt).",
    )
    parser.add_argument(
        "--model-path", default=DEFAULT_CLEAN_MODEL,
        help="Clean model checkpoint used to score examples in confidence strategy.",
    )
    args = parser.parse_args()

    # Save each strategy's dataset and visualizations separately.
    target = args.target or os.path.join(
        os.path.dirname(__file__), "..", "classifier", f"poisoned_data_{args.strategy}"
    )
    results_dir = args.results_dir or os.path.join(RESULTS_DIR, args.strategy)

    poison_dataset(
        args.source, target, args.flip_rate, args.seed,
        target_class=args.target_class, strategy=args.strategy, model_path=args.model_path,
    )
    visualize_flip(
        args.source,
        target,
        num_images=args.visualize_count,
        output_dir=results_dir,
        seed=args.seed,
    )
