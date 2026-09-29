"""Build the Lambda dependency layer into dist/ — SPEC §T11, §C37.

Wheels are pinned to the Lambda platform, not the machine running the build:
`cryptography` ships compiled code, and a Windows wheel fails at import time.

Two passes, because a pinned platform forbids sdists and `http-ece` ships
nothing else: the host turns sdists into wheels, then the pinned install finds
the pure-Python ones there. A compiled sdist-only dependency still fails loudly.

The output must be byte-identical across builds, or every apply replaces the
layer: no .pyc (they embed the install time), no host script launchers,
no RECORD (it lists the launchers' hashes).
"""

import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PYPROJECT = REPO / "api" / "pyproject.toml"
LAYER_DIR = REPO / "dist" / "lambda" / "layer"
WHEEL_DIR = REPO / "dist" / "lambda" / "wheels"

# Provided by the Lambda runtime.
RUNTIME_PROVIDED = ("boto3",)


def requirements():
    deps = tomllib.loads(PYPROJECT.read_text())["project"]["dependencies"]
    return [dep for dep in deps if not dep.startswith(RUNTIME_PROVIDED)]


def wheel_args(wheelhouse):
    return [
        sys.executable, "-m", "pip", "wheel",
        "--wheel-dir", str(wheelhouse),
        "--quiet",
        *requirements(),
    ]


def pip_args(layer_dir, wheelhouse=WHEEL_DIR):
    return [
        sys.executable, "-m", "pip", "install",
        "--target", str(layer_dir / "python"),
        "--platform", "manylinux2014_x86_64",
        "--implementation", "cp",
        "--python-version", "3.11",
        "--only-binary=:all:",
        "--find-links", str(wheelhouse),
        "--no-compile",
        "--quiet",
        *requirements(),
    ]


def prune(layer_dir):
    shutil.rmtree(layer_dir / "python" / "bin", ignore_errors=True)
    # pip's uninstall manifest; it lists the launchers' hashes.
    for record in (layer_dir / "python").glob("*.dist-info/RECORD"):
        record.unlink()


if __name__ == "__main__":
    for stale in (LAYER_DIR, WHEEL_DIR):
        shutil.rmtree(stale, ignore_errors=True)
    subprocess.run(wheel_args(WHEEL_DIR), check=True)
    subprocess.run(pip_args(LAYER_DIR), check=True)
    prune(LAYER_DIR)
