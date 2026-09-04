import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from typing import Dict, Tuple
import numpy as np
import torch
from torch.utils.data import DataLoader

from backend.f1_detection.dataset import OilSpillDataset
from backend.f1_detection.loss import CombinedBCEDiceLoss
from backend.f1_detection.model import UNetBaseline
from backend.shared.config.settings import settings


def compute_metrics(
    preds: np.ndarray, targets: np.ndarray, target_class: int = 1
) -> Dict[str, float]:
    """
    Computes binary IoU, Dice, Precision, and Recall for a specific class (default: 1=oil).
    """
    p = (preds == target_class).astype(np.uint8)
    t = (targets == target_class).astype(np.uint8)

    tp = float(np.sum((p == 1) & (t == 1)))
    fp = float(np.sum((p == 1) & (t == 0)))
    fn = float(np.sum((p == 0) & (t == 1)))

    intersection = tp
    union = tp + fp + fn

    iou = intersection / (union + 1e-6) if union > 0 else 1.0
    dice = (2.0 * tp) / (2.0 * tp + fp + fn + 1e-6) if (tp + fp + fn) > 0 else 1.0
    precision = tp / (tp + fp + 1e-6) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn + 1e-6) if (tp + fn) > 0 else 0.0

    return {
        "iou": round(float(iou), 4),
        "dice": round(float(dice), 4),
        "precision": round(float(precision), 4),
        "recall": round(float(recall), 4),
    }


def evaluate(
    model: torch.nn.Module, val_loader: DataLoader, device: torch.device
) -> Dict[str, float]:
    model.eval()
    all_preds = []
    all_targets = []

    with torch.no_grad():
        for imgs, masks, _ in val_loader:
            imgs = imgs.to(device)
            logits = model(imgs)
            preds = torch.argmax(logits, dim=1).cpu().numpy()
            all_preds.append(preds)
            all_targets.append(masks.numpy())

    preds_cat = np.concatenate(all_preds, axis=0)
    targets_cat = np.concatenate(all_targets, axis=0)

    oil_metrics = compute_metrics(preds_cat, targets_cat, target_class=1)
    lookalike_metrics = compute_metrics(preds_cat, targets_cat, target_class=2)

    return {
        "oil_iou": oil_metrics["iou"],
        "oil_dice": oil_metrics["dice"],
        "oil_precision": oil_metrics["precision"],
        "oil_recall": oil_metrics["recall"],
        "lookalike_iou": lookalike_metrics["iou"],
    }


def train_f1_baseline(
    epochs: int = 5,
    batch_size: int = 4,
    learning_rate: float = 1e-3,
    output_dir: Optional[Path] = None,
) -> Dict[str, float]:
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"[F1 Train] Using compute device: {device}")

    train_dataset = OilSpillDataset(split="train", augment=True)
    val_dataset = OilSpillDataset(split="val", augment=False)

    train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True, drop_last=False)
    val_loader = DataLoader(val_dataset, batch_size=batch_size, shuffle=False)

    print(f"[F1 Train] Train scenes: {len(train_dataset)} | Val scenes: {len(val_dataset)}")

    model = UNetBaseline(in_channels=1, num_classes=5, base_features=16).to(device)

    # Class weights giving priority to oil (1) and look-alike (2)
    # Classes: 0: sea, 1: oil, 2: lookalike, 3: ship, 4: land
    class_weights = torch.tensor([1.0, 6.0, 4.0, 2.0, 2.0], device=device)
    criterion = CombinedBCEDiceLoss(class_weights=class_weights, ce_weight=0.4, dice_weight=0.6)
    optimizer = torch.optim.Adam(model.parameters(), lr=learning_rate, weight_decay=1e-5)

    if output_dir is None:
        output_dir = settings.models_dir / "f1_detection" / "unet_baseline" / "v1"
    output_dir.mkdir(parents=True, exist_ok=True)

    best_val_dice = -1.0
    best_metrics = {}

    for epoch in range(1, epochs + 1):
        model.train()
        train_loss = 0.0

        for imgs, masks, _ in train_loader:
            imgs = imgs.to(device)
            masks = masks.to(device)

            optimizer.zero_grad()
            logits = model(imgs)
            loss = criterion(logits, masks)
            loss.backward()
            optimizer.step()

            train_loss += loss.item() * len(imgs)

        train_loss /= len(train_dataset)
        val_metrics = evaluate(model, val_loader, device)

        print(
            f"Epoch {epoch:02d}/{epochs:02d} | Train Loss: {train_loss:.4f} | "
            f"Val Oil IoU: {val_metrics['oil_iou']:.4f} | Val Oil Dice: {val_metrics['oil_dice']:.4f}"
        )

        if val_metrics["oil_dice"] >= best_val_dice:
            best_val_dice = val_metrics["oil_dice"]
            best_metrics = val_metrics

            # Save best weights
            torch.save(model.state_dict(), output_dir / "model.pt")

    # Save metadata
    metadata = {
        "model_name": "unet_baseline",
        "model_version": "v1",
        "framework": "PyTorch",
        "architecture": "UNetBaseline",
        "in_channels": 1,
        "num_classes": 5,
        "classes": {
            0: "sea",
            1: "oil",
            2: "lookalike",
            3: "ship",
            4: "land",
        },
        "source_dataset": "synthetic",
        "epochs_trained": epochs,
        "train_samples": len(train_dataset),
        "val_samples": len(val_dataset),
        "best_val_metrics": best_metrics,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    with open(output_dir / "metadata.json", "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)

    print(f"[F1 Train] Finished. Best weights saved to: {output_dir / 'model.pt'}")
    return best_metrics


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train F1 U-Net Baseline on Synthetic SAR imagery")
    parser.add_argument("--epochs", type=int, default=5, help="Number of training epochs")
    parser.add_argument("--batch-size", type=int, default=4, help="Batch size")
    parser.add_argument("--lr", type=float, default=1e-3, help="Learning rate")
    args = parser.parse_args()

    train_f1_baseline(epochs=args.epochs, batch_size=args.batch_size, learning_rate=args.lr)
