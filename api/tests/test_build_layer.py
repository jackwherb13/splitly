"""Lambda dependency layer — SPEC §T11, §C37.

`pywebpush` is not in the Lambda runtime. Its dependency `cryptography` ships
compiled code, so a layer built by a plain `pip install` on Windows holds
`.pyd` files that Linux cannot load — and the function fails at import time,
before any handler runs. The platform pin is the thing under test.
"""

import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "build_layer", Path(__file__).parents[1] / "scripts" / "build_layer.py"
)
build_layer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build_layer)


def test_the_layer_carries_the_runtime_dependencies_from_pyproject():
    assert any(req.startswith("pywebpush") for req in build_layer.requirements())


def test_boto3_is_left_to_the_runtime():
    """The Lambda runtime provides it; bundling it adds ~15MB for nothing."""
    assert not any(req.startswith("boto3") for req in build_layer.requirements())


def test_wheels_are_pinned_to_the_lambda_platform_not_the_build_machine():
    args = build_layer.pip_args(Path("out"))
    assert args[args.index("--platform") + 1].startswith("manylinux")
    assert args[args.index("--python-version") + 1] == "3.11"
    # Without this pip may build from source for the host, which is the bug.
    assert "--only-binary=:all:" in args


def test_sdist_only_dependencies_are_wheeled_first_then_found():
    """`http-ece` ships no wheel at all, and `--platform` forbids sdists.
    Pure-Python sdists become `py3-none-any` wheels on the host; the pinned
    install then finds them. Host-only binary wheels are ignored by it."""
    wheel = build_layer.wheel_args(Path("wheels"))
    assert wheel[wheel.index("-m") + 1 : wheel.index("-m") + 3] == ["pip", "wheel"]
    assert wheel[wheel.index("--wheel-dir") + 1] == "wheels"

    install = build_layer.pip_args(Path("out"), wheelhouse=Path("wheels"))
    assert install[install.index("--find-links") + 1] == "wheels"


def test_the_layer_lands_under_dist():
    """§C37 — one gitignored artifact location. Lambda layers put Python
    packages under `python/`."""
    repo = Path(__file__).parents[2]
    assert build_layer.LAYER_DIR == repo / "dist" / "lambda" / "layer"
    assert build_layer.pip_args(build_layer.LAYER_DIR)[
        build_layer.pip_args(build_layer.LAYER_DIR).index("--target") + 1
    ] == str(build_layer.LAYER_DIR / "python")


def test_the_layer_is_byte_identical_across_builds():
    """Unchanged deps must not replace the layer on every apply. Compiled
    .pyc files embed the install time, so they are not shipped; Lambda
    compiles on import."""
    assert "--no-compile" in build_layer.pip_args(Path("out"))


def test_console_script_launchers_are_pruned(tmp_path):
    """pip writes host launchers (Windows .exe) that differ every build and
    that Lambda never runs."""
    (tmp_path / "python" / "bin").mkdir(parents=True)
    (tmp_path / "python" / "bin" / "vapid.exe").write_bytes(b"MZ")
    (tmp_path / "python" / "pywebpush").mkdir()
    # RECORD lists the launchers' hashes, so it churns with them.
    (tmp_path / "python" / "pywebpush-2.5.0.dist-info").mkdir()
    (tmp_path / "python" / "pywebpush-2.5.0.dist-info" / "RECORD").write_text("x")
    (tmp_path / "python" / "pywebpush-2.5.0.dist-info" / "METADATA").write_text("x")

    build_layer.prune(tmp_path)

    assert not (tmp_path / "python" / "bin").exists()
    assert not (tmp_path / "python" / "pywebpush-2.5.0.dist-info" / "RECORD").exists()
    assert (tmp_path / "python" / "pywebpush-2.5.0.dist-info" / "METADATA").exists()
    assert (tmp_path / "python" / "pywebpush").exists()
