"""Finish a UniRig ROCm inference in the installed Blender/bpy runtime."""
import argparse
import os

from src.data.exporter import Exporter
from src.data.raw_data import RawData, RawSkin
from src.system.skin import reskin


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', required=True, help='extracted raw_data.npz')
    parser.add_argument('--skeleton', required=True, help='AR prediction NPZ')
    parser.add_argument('--skin', required=True, help='skin prediction NPZ')
    parser.add_argument('--output', required=True, help='destination FBX')
    args = parser.parse_args()

    source = RawData.load(args.source)
    skeleton = RawData.load(args.skeleton)
    predicted = RawSkin.load(args.skin)
    if source.vertices is None or source.faces is None:
        raise RuntimeError('Source NPZ has no mesh geometry.')
    if skeleton.joints is None or skeleton.parents is None:
        raise RuntimeError('Skeleton NPZ is missing joints or parent data.')

    parents = [None if parent is None or int(parent) < 0 else int(parent)
               for parent in skeleton.parents]
    names = ([f'bone_{index}' for index in range(len(parents))] if skeleton.names is None else [str(name) for name in skeleton.names])
    weights = reskin(
        sampled_vertices=predicted.vertices,
        vertices=source.vertices,
        parents=parents,
        faces=source.faces,
        sampled_skin=predicted.skin,
        sample_method='median',
        alpha=2.0,
        threshold=0.03,
    )
    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    Exporter()._export_fbx(
        path=args.output,
        vertices=source.vertices,
        joints=skeleton.joints,
        skin=weights,
        parents=parents,
        names=names,
        faces=source.faces,
        group_per_vertex=4,
        tails=skeleton.tails,
        use_extrude_bone=False,
        use_connect_unique_child=False,
    )
    if not os.path.isfile(args.output) or os.path.getsize(args.output) == 0:
        raise RuntimeError('Blender did not create the FBX output.')
    print(f'Created rigged FBX: {args.output} ({os.path.getsize(args.output):,} bytes)')


if __name__ == '__main__':
    main()
