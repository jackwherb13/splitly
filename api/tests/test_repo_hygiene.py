"""Enforces SPEC §V14 — no build artifact is ever tracked by git.

§C37 says artifacts live in one gitignored location. B1 records the time that
slipped: an editable pip install wrote api/src/splitly_api.egg-info/ and
`git add -A` swept it into a commit. Nothing checked, so nothing caught it.

.terraform/ (a provider cache, hundreds of MB) and *.tfstate (which can hold
secrets) are the same shape, added before infra/ exists rather than after.
.terraform.lock.hcl is deliberately NOT a marker — it is committed on purpose.
"""

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
