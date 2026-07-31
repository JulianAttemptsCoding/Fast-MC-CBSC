"""Guards on the DiCOS client's write scope.

These encode the filesystem contract in AGENTS.md rules 17-19: exactly one
writable directory, and two immutable source datasets. They run offline -- no
token, no network -- so the contract stays enforced even when the remote host
is unreachable.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from dicos import Dicos  # noqa: E402

ROOT = "/dicos_ui_home/julianjuan"
WORKDIR = f"{ROOT}/sharedfs/work/IOP/julian/Fast MC CBSC"
DATASET = f"{ROOT}/sharedfs/work/IOP/ZDC_ML_20260620/dataset"
PLAIN = f"{DATASET}/myTree_20251117_765k_0to300GeV_neutron_All.root"
TRANSFORMED = f"{DATASET}/myTree_20251117_765k_0to300GeV_neutron_All_transformed.root"


@pytest.fixture
def client() -> Dicos:
    return Dicos({
        "base_url": "http://example.invalid:32065",
        "token": "0" * 64,
        "jupyter_root": ROOT,
        "workdir": WORKDIR,
        "readonly_data": [PLAIN, TRANSFORMED],
    })


def test_relative_paths_resolve_inside_the_workdir(client: Dicos) -> None:
    assert client._resolve("prep/geometry") == f"{WORKDIR}/prep/geometry"
    assert client._resolve(".") == WORKDIR
    client._assert_writable(client._resolve("prep/geometry"))


@pytest.mark.parametrize("escape", [
    f"{ROOT}/evil.txt",                       # absolute, outside workdir
    f"{DATASET}/evil.txt",                    # into the read-only dataset dir
    "../../../../evil.txt",                   # traversal out of the workdir
    f"{ROOT}/sharedfs/work/IOP/other/x.txt",  # another group's directory
])
def test_writes_outside_the_workdir_are_refused(client: Dicos, escape: str) -> None:
    with pytest.raises(SystemExit, match="outside the permitted workdir"):
        client._assert_writable(client._resolve(escape))


def test_traversal_cannot_smuggle_a_path_past_the_guard(client: Dicos) -> None:
    """Normalisation must happen before the prefix check, not after."""
    resolved = client._resolve("prep/../../../evil.txt")
    assert ".." not in resolved
    with pytest.raises(SystemExit):
        client._assert_writable(resolved)


@pytest.mark.parametrize("local", [
    "C:/Program Files/Git/dicos_ui_home/evil.txt",
    r"C:\Users\Julia\evil.txt",
])
def test_local_windows_paths_are_rejected(client: Dicos, local: str) -> None:
    """Git Bash silently rewrites POSIX-looking paths into Windows ones; a
    drive letter arriving here means a local path leaked into a remote slot."""
    with pytest.raises(SystemExit, match="local Windows path"):
        client._resolve(local)


@pytest.mark.parametrize("command", [
    f"echo x > {PLAIN}",
    f"rm -f {TRANSFORMED}",
    f"mv {PLAIN} /tmp/x",
    f"truncate -s 0 {PLAIN}",
    f"chmod 000 {TRANSFORMED}",
    f"dd if=/dev/zero of={PLAIN}",
])
def test_commands_that_would_mutate_a_source_dataset_are_refused(
    client: Dicos, command: str
) -> None:
    with pytest.raises(SystemExit, match="read-only dataset"):
        client._assert_command_safe(command)


@pytest.mark.parametrize("command", [
    f"sha256sum {PLAIN}",
    f"ls -la {DATASET}",
    f"python -c \"import uproot; uproot.open('{PLAIN}')\"",
])
def test_reading_a_source_dataset_is_allowed(client: Dicos, command: str) -> None:
    """The datasets are read-only, not untouchable -- reads must still work."""
    client._assert_command_safe(command)
