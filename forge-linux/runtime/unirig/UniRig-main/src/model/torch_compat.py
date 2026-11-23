"""PyTorch equivalents of UniRig's inference operators."""
from dataclasses import dataclass, field, replace
from itertools import product
import math
import os
from types import SimpleNamespace

import torch
from torch import nn
from torch.nn import functional as F

ROCM_INFERENCE = os.environ.get('UNIRIG_ROCM') == '1'
PORTABLE_INFERENCE = os.environ.get('UNIRIG_CPU') == '1' or ROCM_INFERENCE


def segment_csr(values, offsets, reduce):
    op = 'sum' if reduce == 'add' else reduce
    return torch.segment_reduce(values.contiguous(), op, offsets=offsets.contiguous())


def fps(points, batch, ratio, random_start):
    selections = []
    for batch_id in batch.unique(sorted=True):
        indices = (batch == batch_id).nonzero().flatten()
        cloud = points[indices]
        distances = cloud.new_full((len(cloud),), float('inf'))
        chosen = torch.randint(len(cloud), (), device=cloud.device) if random_start else indices.new_zeros(())
        selected = []
        for _ in range(math.ceil(len(cloud) * ratio)):
            selected.append(chosen)
            distances = torch.minimum(distances, (cloud - cloud[chosen]).square().sum(dim=1))
            chosen = distances.argmax()
        selections.append(indices[torch.stack(selected)])
    return torch.cat(selections)


class CrossAttention(nn.Module):
    """Retain the projection names and shapes used by FlashAttention MHA."""

    def __init__(self, embed_dim, num_heads, cross_attn=True):
        super().__init__()
        if not cross_attn or embed_dim % num_heads:
            raise ValueError('Expected cross-attention with evenly sized heads')
        self.num_heads = num_heads
        self.Wq = nn.Linear(embed_dim, embed_dim)
        self.Wkv = nn.Linear(embed_dim, 2 * embed_dim)
        self.out_proj = nn.Linear(embed_dim, embed_dim)

    def forward(self, query, x_kv):
        def heads(tensor):
            return tensor.unflatten(-1, (self.num_heads, -1)).transpose(1, 2)

        key, value = self.Wkv(x_kv).chunk(2, dim=-1)
        attention = F.scaled_dot_product_attention(heads(self.Wq(query)), heads(key), heads(value))
        return self.out_proj(attention.transpose(1, 2).flatten(2))


@dataclass
class SparseConvTensor:
    features: torch.Tensor
    indices: torch.Tensor
    spatial_shape: list
    batch_size: int
    neighbors: dict = field(default_factory=dict)

    def replace_feature(self, features):
        return replace(self, features=features)


class SubMConv3d(nn.Module):
    """Stride-one submanifold cross-correlation in spconv 2.x KRSC layout."""

    def __init__(self, in_channels, out_channels, kernel_size, padding=0, bias=True, indice_key=None):
        super().__init__()
        self.kernel_size = kernel_size
        self.indice_key = indice_key
        self.weight = nn.Parameter(torch.empty(out_channels, kernel_size, kernel_size, kernel_size, in_channels))
        self.bias = nn.Parameter(torch.zeros(out_channels)) if bias else None
        nn.init.kaiming_uniform_(self.weight, a=math.sqrt(5))

    def forward(self, sparse):
        coords = sparse.indices.to(torch.int64)
        radius = self.kernel_size // 2
        offsets = tuple(product(range(-radius, radius + 1), repeat=3))
        cache_key = (self.indice_key, self.kernel_size)
        if cache_key not in sparse.neighbors:
            x, y, z = sparse.spatial_shape
            stride = coords.new_tensor((x * y * z, y * z, z, 1))
            limits = coords.new_tensor((x, y, z))
            codes, indices = (coords * stride).sum(dim=1).sort(stable=True)
            pairs = []
            for offset in offsets:
                adjacent = coords[:, 1:] + coords.new_tensor(offset)
                valid = ((adjacent >= 0) & (adjacent < limits)).all(dim=1)
                target = valid.nonzero().flatten()
                query = coords[target, 0] * stride[0] + (adjacent[target] * stride[1:]).sum(dim=1)
                position = torch.searchsorted(codes, query).clamp(max=len(codes) - 1)
                match = codes[position] == query
                pairs.append((target[match], indices[position[match]]))
            sparse.neighbors[cache_key] = pairs

        result = sparse.features.new_zeros((len(coords), self.weight.shape[0]))
        kernel = self.weight.flatten(1, 3)
        for index, (target, source) in enumerate(sparse.neighbors[cache_key]):
            if source.numel():
                result.index_add_(0, target, F.linear(sparse.features[source], kernel[:, index]))
        if self.bias is not None:
            result += self.bias
        return sparse.replace_feature(result)


spconv = SimpleNamespace(
    SparseConvTensor=SparseConvTensor,
    SubMConv3d=SubMConv3d,
    modules=SimpleNamespace(is_spconv_module=lambda module: isinstance(module, SubMConv3d)),
)
