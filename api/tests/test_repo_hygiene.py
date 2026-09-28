"""Enforces SPEC §V14 — no build artifact is ever tracked by git.

§C37 says artifacts live in one gitignored location. B1 records the time that
slipped: an editable pip install wrote api/src/splitly_api.egg-info/ and
`git add -A` swept it into a commit. Nothing checked, so nothing caught it.

.terraform/ (a provider cache, hundreds of MB) and *.tfstate (which can hold
secrets) are the same shape, added before infra/ exists rather than after.
.terraform.lock.hcl is deliberately NOT a marker — it is committed on purpose.

B2 records why that is not enough on its own: the markers match FILENAMES, and
an artifact names itself. infra/state.json was real Terraform state, tracked,
and this file passed. Terraform state is therefore identified by CONTENT — a
JSON object carrying both "terraform_version" and "lineage" is state whatever
it is called. Substring matching was rejected: docs/Decisions.md discusses
those key names in prose and would be a false positive.
"""

import json
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

ARTIFACT_MARKERS = (
    "dist/",
    ".egg-info/",
    "node_modules/",
    "__pycache__/",
    ".terraform/",
    ".tfstate",
)
ARTIFACT_SUFFIXES = (".pyc",)


def tracked_files():
    out = subprocess.run(
        ["git", "ls-files"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return out.stdout.splitlines()


def test_no_build_artifacts_tracked():
    offenders = [
        path
        for path in tracked_files()
        if any(marker in path for marker in ARTIFACT_MARKERS)
        or path.endswith(ARTIFACT_SUFFIXES)
    ]
    assert offenders == [], (
        "build artifacts are tracked by git, violating SPEC §C37 / §V14:\n  "
        + "\n  ".join(offenders)
    )


STATE_KEYS = frozenset({"terraform_version", "lineage"})


def test_no_terraform_state_tracked():
    """SPEC §V14 content clause — see B2. Filename markers cannot catch this."""
    offenders = []
    for path in tracked_files():
        try:
            data = json.loads((REPO_ROOT / path).read_text(encoding="utf-8"))
        except (OSError, ValueError, UnicodeDecodeError):
            continue
        if isinstance(data, dict) and STATE_KEYS <= data.keys():
            offenders.append(path)
    assert offenders == [], (
        "Terraform state is tracked by git, violating SPEC §V14:\n  "
        + "\n  ".join(offenders)
    )


JS_EXTENSIONS = (".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx")


def test_no_two_paths_collide_case_insensitively():
    """SPEC §V17 — see B5.

    Windows and macOS resolve `./Foo` and `./foo` to the same file; Linux
    does not, so a colliding pair builds on one platform and fails on the
    other — and CI is the platform the developer is not on.
    """
    offenders = []

    by_path = {}
    for path in tracked_files():
        key = path.lower()
        if key in by_path:
            offenders.append(f"{by_path[key]} <> {path}")
        by_path[key] = path

    # An import writes no extension, so the bundler tries each in turn and
    # Balances.jsx and balances.js are one specifier. Their full paths
    # differ, which is exactly why the loop above cannot see them.
    by_specifier = {}
    for path in tracked_files():
        directory, _, filename = path.rpartition("/")
        stem, dot, extension = filename.rpartition(".")
        if not dot or f".{extension}" not in JS_EXTENSIONS:
            continue
        key = (directory.lower(), stem.lower())
        if key in by_specifier:
            offenders.append(f"{by_specifier[key]} <> {path} (one import specifier)")
        by_specifier[key] = path

    assert offenders == [], (
        "paths that resolve differently per platform, violating SPEC §V17:\n  "
        + "\n  ".join(offenders)
    )
