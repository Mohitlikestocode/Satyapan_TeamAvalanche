"""Small U-Net that predicts, per pixel, whether a payment screenshot was edited there.

Two encoders: a small one trained from scratch (no downloads, works anywhere) and a ResNet-18 encoder from torchvision
(pass pretrained=True to start from ImageNet weights, which downloads them once).
"""
from __future__ import annotations

import io

import torch
import torch.nn as nn
import torch.nn.functional as F

DEFAULT_SIZE = (704, 384)  # height, width: payment screens are tall phone captures


def _block(i: int, o: int) -> nn.Sequential:
    return nn.Sequential(nn.Conv2d(i, o, 3, padding=1, bias=False), nn.BatchNorm2d(o), nn.ReLU(inplace=True),
                         nn.Conv2d(o, o, 3, padding=1, bias=False), nn.BatchNorm2d(o), nn.ReLU(inplace=True))


class SmallUNet(nn.Module):
    def __init__(self, ch: tuple[int, ...] = (24, 48, 96, 160)):
        super().__init__()
        self.enc = nn.ModuleList()
        prev = 3
        for c in ch:
            self.enc.append(_block(prev, c))
            prev = c
        self.dec = nn.ModuleList()
        for hi, lo in zip(ch[:0:-1], ch[-2::-1]):
            self.dec.append(_block(hi + lo, lo))
        self.head = nn.Conv2d(ch[0], 1, 1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        skips = []
        for i, e in enumerate(self.enc):
            x = e(x if i == 0 else F.max_pool2d(x, 2))
            skips.append(x)
        x = skips.pop()
        for d in self.dec:
            s = skips.pop()
            x = d(torch.cat([F.interpolate(x, size=s.shape[-2:], mode="bilinear", align_corners=False), s], 1))
        return self.head(x)


class ResNetUNet(nn.Module):
    """ResNet-18 encoder + light decoder. Needs torchvision."""

    def __init__(self, pretrained: bool = False):
        super().__init__()
        from torchvision.models import ResNet18_Weights, resnet18
        r = resnet18(weights=ResNet18_Weights.IMAGENET1K_V1 if pretrained else None)
        self.stem = nn.Sequential(r.conv1, r.bn1, r.relu)
        self.pool, self.l1, self.l2, self.l3, self.l4 = r.maxpool, r.layer1, r.layer2, r.layer3, r.layer4
        self.d4, self.d3 = _block(512 + 256, 256), _block(256 + 128, 128)
        self.d2, self.d1 = _block(128 + 64, 64), _block(64 + 64, 32)
        self.head = nn.Conv2d(32, 1, 1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        s0 = self.stem(x)
        s1 = self.l1(self.pool(s0))
        s2 = self.l2(s1)
        s3 = self.l3(s2)
        s4 = self.l4(s3)
        up = lambda a, b: torch.cat([F.interpolate(a, size=b.shape[-2:], mode="bilinear", align_corners=False), b], 1)  # noqa: E731
        y = self.d4(up(s4, s3))
        y = self.d3(up(y, s2))
        y = self.d2(up(y, s1))
        y = self.d1(up(y, s0))
        return F.interpolate(self.head(y), size=x.shape[-2:], mode="bilinear", align_corners=False)


def build(encoder: str = "small", pretrained: bool = False) -> nn.Module:
    if encoder == "small":
        return SmallUNet()
    if encoder == "resnet18":
        return ResNetUNet(pretrained=pretrained)
    raise ValueError(f"unknown encoder {encoder!r}")


def to_tensor(img, size: tuple[int, int]) -> torch.Tensor:
    """PIL image -> normalised float tensor (3, H, W)."""
    import numpy as np
    from PIL import Image
    a = np.asarray(img.convert("RGB").resize((size[1], size[0]), Image.BILINEAR), dtype="float32") / 255.0
    return torch.from_numpy((a - 0.5) / 0.5).permute(2, 0, 1).contiguous()


def image_score(logits: torch.Tensor) -> torch.Tensor:
    """One number per image: the strongest 3x3-averaged edit probability anywhere."""
    p = torch.sigmoid(logits)
    return F.avg_pool2d(p, 3, stride=1, padding=1).amax(dim=(1, 2, 3))


def load_checkpoint(path_or_bytes) -> tuple[nn.Module, dict]:
    ck = torch.load(io.BytesIO(path_or_bytes) if isinstance(path_or_bytes, bytes) else path_or_bytes, map_location="cpu", weights_only=True)
    model = build(ck["config"]["encoder"], pretrained=False)
    model.load_state_dict(ck["state_dict"])
    return model.eval(), ck
