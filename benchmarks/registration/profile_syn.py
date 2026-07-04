"""Profile 3D SyN registration between fixed and moving NIfTI images."""

import argparse
import cProfile
from pathlib import Path
import pstats
import time

import numpy as np

from dipy.align.imwarp import SymmetricDiffeomorphicRegistration
from dipy.align.metrics import CCMetric
from dipy.data import get_fnames
from dipy.io.image import load_nifti
from dipy.segment.mask import median_otsu


def load_volume(path, *, name):
    """Load one three-dimensional NIfTI volume as float32."""
    if not path.is_file():
        raise ValueError(f"{name} image does not exist: {path}")

    data, affine = load_nifti(path)
    if data.ndim != 3:
        raise ValueError(f"{name} image must be 3D, but {path} has shape {data.shape}")
    if not np.all(np.isfinite(data)):
        raise ValueError(f"{name} image contains non-finite values: {path}")
    return np.asarray(data, dtype=np.float32), affine


def load_example_pair():
    """Download and prepare the image pair from the 3D SyN example."""
    hardi_path, _, _ = get_fnames(name="stanford_hardi")
    _, syn_b0_path = get_fnames(name="syn_data")

    hardi, hardi_affine = load_nifti(hardi_path)
    if hardi.ndim != 4:
        raise ValueError(
            f"Stanford HARDI image must be 4D, but has shape {hardi.shape}"
        )
    static = np.asarray(hardi[..., 0], dtype=np.float32)
    moving, moving_affine = load_volume(Path(syn_b0_path), name="moving")

    static, _ = median_otsu(static, median_radius=4, numpass=4)
    moving, _ = median_otsu(moving, median_radius=4, numpass=4)
    return (
        static,
        hardi_affine,
        moving,
        moving_affine,
        Path(hardi_path),
        Path(syn_b0_path),
    )


def parse_level_iters(value):
    try:
        level_iters = [int(item) for item in value.split(",")]
    except ValueError as error:
        raise argparse.ArgumentTypeError("use comma-separated integers") from error
    if not level_iters or any(item < 1 for item in level_iters):
        raise argparse.ArgumentTypeError("iterations must be positive")
    return level_iters


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "fixed_path",
        nargs="?",
        type=Path,
        help="3D fixed/static NIfTI image (omit both paths for example data)",
    )
    parser.add_argument(
        "moving_path",
        nargs="?",
        type=Path,
        help="3D moving NIfTI image (omit both paths for example data)",
    )
    parser.add_argument(
        "--level-iters",
        type=parse_level_iters,
        default=parse_level_iters("10,10,5"),
        help="iterations from finest to coarsest level (default: 10,10,5)",
    )
    parser.add_argument(
        "--radius",
        type=int,
        default=4,
        help="cross-correlation neighborhood radius (default: 4)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("syn-registration.prof"),
        help="cProfile output file",
    )
    parser.add_argument(
        "--top",
        type=int,
        default=25,
        help="number of cumulative-time entries to print",
    )
    args = parser.parse_args()

    if args.radius < 1:
        parser.error("--radius must be positive")
    if (args.fixed_path is None) != (args.moving_path is None):
        parser.error("provide both fixed_path and moving_path, or neither")

    try:
        if args.fixed_path is None:
            print("No input images supplied; using the 3D SyN example data.")
            (
                static,
                static_affine,
                moving,
                moving_affine,
                fixed_path,
                moving_path,
            ) = load_example_pair()
        else:
            fixed_path = args.fixed_path
            moving_path = args.moving_path
            static, static_affine = load_volume(fixed_path, name="fixed")
            moving, moving_affine = load_volume(moving_path, name="moving")
    except (OSError, ValueError) as error:
        parser.error(str(error))

    metric = CCMetric(3, radius=args.radius)
    registration = SymmetricDiffeomorphicRegistration(
        metric,
        level_iters=args.level_iters,
    )

    print(f"Fixed:  {fixed_path} {static.shape}")
    print(f"Moving: {moving_path} {moving.shape}")

    profiler = cProfile.Profile()
    start = time.perf_counter()
    profiler.enable()
    registration.optimize(
        static,
        moving,
        static_grid2world=static_affine,
        moving_grid2world=moving_affine,
    )
    profiler.disable()
    elapsed = time.perf_counter() - start

    args.output.parent.mkdir(parents=True, exist_ok=True)
    profiler.dump_stats(args.output)
    print(f"SyN optimize wall time: {elapsed:.3f} s")
    print(f"Profile written to {args.output.resolve()}")
    pstats.Stats(profiler).strip_dirs().sort_stats("cumtime").print_stats(args.top)


if __name__ == "__main__":
    main()
