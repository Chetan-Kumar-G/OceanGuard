import torch
import torch.nn as nn
import torch.nn.functional as F


class DoubleConv(nn.Module):
    """(Conv2D -> BatchNorm -> ReLU) * 2"""

    def __init__(self, in_channels: int, out_channels: int):
        super().__init__()
        self.double_conv = nn.Sequential(
            nn.Conv2d(in_channels, out_channels, kernel_size=3, padding=1, bias=False),
            nn.BatchNorm2d(out_channels),
            nn.ReLU(inplace=True),
            nn.Conv2d(out_channels, out_channels, kernel_size=3, padding=1, bias=False),
            nn.BatchNorm2d(out_channels),
            nn.ReLU(inplace=True),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.double_conv(x)


class UNetBaseline(nn.Module):
    """
    Standard U-Net Baseline for SAR oil-spill and look-alike segmentation.
    Follows authoritative architecture specification in Blueprint Part 10.
    """

    def __init__(self, in_channels: int = 1, num_classes: int = 5, base_features: int = 16):
        super().__init__()
        self.in_channels = in_channels
        self.num_classes = num_classes

        f = base_features
        # Encoder
        self.inc = DoubleConv(in_channels, f)
        self.down1 = nn.Sequential(nn.MaxPool2d(2), DoubleConv(f, f * 2))
        self.down2 = nn.Sequential(nn.MaxPool2d(2), DoubleConv(f * 2, f * 4))
        self.down3 = nn.Sequential(nn.MaxPool2d(2), DoubleConv(f * 4, f * 8))

        # Bottleneck
        self.bot = nn.Sequential(nn.MaxPool2d(2), DoubleConv(f * 8, f * 16))

        # Decoder
        self.up1 = nn.ConvTranspose2d(f * 16, f * 8, kernel_size=2, stride=2)
        self.conv_up1 = DoubleConv(f * 16, f * 8)

        self.up2 = nn.ConvTranspose2d(f * 8, f * 4, kernel_size=2, stride=2)
        self.conv_up2 = DoubleConv(f * 8, f * 4)

        self.up3 = nn.ConvTranspose2d(f * 4, f * 2, kernel_size=2, stride=2)
        self.conv_up3 = DoubleConv(f * 4, f * 2)

        self.up4 = nn.ConvTranspose2d(f * 2, f, kernel_size=2, stride=2)
        self.conv_up4 = DoubleConv(f * 2, f)

        # Output projection
        self.outc = nn.Conv2d(f, num_classes, kernel_size=1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # Encoder
        x1 = self.inc(x)
        x2 = self.down1(x1)
        x3 = self.down2(x2)
        x4 = self.down3(x3)
        
        # Bottleneck
        xb = self.bot(x4)

        # Decoder with skip connections
        u1 = self.up1(xb)
        u1 = self._pad_and_cat(u1, x4)
        d1 = self.conv_up1(u1)

        u2 = self.up2(d1)
        u2 = self._pad_and_cat(u2, x3)
        d2 = self.conv_up2(u2)

        u3 = self.up3(d2)
        u3 = self._pad_and_cat(u3, x2)
        d3 = self.conv_up3(u3)

        u4 = self.up4(d3)
        u4 = self._pad_and_cat(u4, x1)
        d4 = self.conv_up4(u4)

        logits = self.outc(d4)
        return logits

    @staticmethod
    def _pad_and_cat(upsampled: torch.Tensor, bypass: torch.Tensor) -> torch.Tensor:
        diff_y = bypass.size()[2] - upsampled.size()[2]
        diff_x = bypass.size()[3] - upsampled.size()[3]
        if diff_y > 0 or diff_x > 0:
            upsampled = F.pad(
                upsampled,
                [diff_x // 2, diff_x - diff_x // 2, diff_y // 2, diff_y - diff_y // 2],
            )
        return torch.cat([bypass, upsampled], dim=1)
