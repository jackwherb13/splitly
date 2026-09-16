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
