from typing import Optional
import torch
import torch.nn as nn
import torch.nn.functional as F


class MultiClassDiceLoss(nn.Module):
    """
    Multi-class Soft Dice Loss for sparse segmentation masks.
    """

    def __init__(self, smooth: float = 1e-5, weights: Optional[torch.Tensor] = None):
        super().__init__()
        self.smooth = smooth
        self.weights = weights

    def forward(self, logits: torch.Tensor, targets: torch.Tensor) -> torch.Tensor:
        num_classes = logits.shape[1]
        probs = F.softmax(logits, dim=1)

        # One-hot encode targets: (B, H, W) -> (B, C, H, W)
        targets_one_hot = F.one_hot(targets, num_classes=num_classes).permute(0, 3, 1, 2).float()

        dims = (0, 2, 3)
        intersection = torch.sum(probs * targets_one_hot, dims)
        cardinality = torch.sum(probs + targets_one_hot, dims)

        dice_score = (2.0 * intersection + self.smooth) / (cardinality + self.smooth)
        dice_loss = 1.0 - dice_score

        if self.weights is not None:
            weights = self.weights.to(logits.device)
            return torch.sum(dice_loss * weights) / torch.sum(weights)
        return torch.mean(dice_loss)


class CombinedBCEDiceLoss(nn.Module):
    """
    Combined weighted Cross-Entropy + Soft Dice Loss for handling sparse oil spill pixels.
    """

    def __init__(
        self,
        class_weights: Optional[torch.Tensor] = None,
        ce_weight: float = 0.5,
        dice_weight: float = 0.5,
    ):
        super().__init__()
        self.ce_weight = ce_weight
        self.dice_weight = dice_weight
        self.ce_loss = nn.CrossEntropyLoss(weight=class_weights)
        self.dice_loss = MultiClassDiceLoss(weights=class_weights)

    def forward(self, logits: torch.Tensor, targets: torch.Tensor) -> torch.Tensor:
        ce = self.ce_loss(logits, targets)
        dice = self.dice_loss(logits, targets)
        return self.ce_weight * ce + self.dice_weight * dice
