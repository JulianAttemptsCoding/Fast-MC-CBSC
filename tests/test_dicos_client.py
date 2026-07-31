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
        "data_file": PLAIN,
        "forbidden_paths": [TRANSFORMED],
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
    f"mv {PLAIN} /tmp/x",
    f"truncate -s 0 {PLAIN}",
    f"chmod 000 {PLAIN}",
    f"rm -f {PLAIN}",
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
def test_reading_the_permitted_dataset_is_allowed(client: Dicos, command: str) -> None:
    """The permitted dataset is read-only, not untouchable -- reads must work."""
    client._assert_command_safe(command)


@pytest.mark.parametrize("command", [
    f"ls -l {TRANSFORMED}",
    f"sha256sum {TRANSFORMED}",
    f"python -c \"import uproot; uproot.open('{TRANSFORMED}')\"",
    "head myTree_20251117_765k_0to300GeV_neutron_All_transformed.root",
])
def test_the_transformed_file_is_refused_even_for_reading(
    client: Dicos, command: str
) -> None:
    """Scope was narrowed to a single dataset: the transformed variant is out of
    bounds entirely, not merely unwritable. It also has an incompatible geometry
    (6,400 vs 6,390 HCAL channels) and four fewer events."""
    with pytest.raises(SystemExit, match="out of scope"):
        client._assert_command_safe(command)


# --------------------------------------------------------------- exec scope
# `exec` is the path every real action takes -- training, conversion, mkdir --
# so the write-scope rule has to hold there, not only on put/mkdir. An audit
# found it did not, which is what these pin.

@pytest.mark.parametrize("command", [
    "mkdir -p ~/scratch",
    "echo x > /tmp/evil.txt",
    "rm -rf /dicos_ui_home/julianjuan/.jupyter",
    f"touch {ROOT}/stray",
    "cp results.json /dicos_ui_home/julianjuan/results.json",
    "tee /etc/passwd",
])
def test_exec_refuses_writes_outside_the_workdir(client: Dicos, command: str) -> None:
    with pytest.raises(SystemExit, match="outside the permitted workdir"):
        client._assert_command_safe(command)


@pytest.mark.parametrize("command", [
    "mkdir -p prep/data",
    "echo hello > _setup/note.txt",
    f"rm -rf {WORKDIR}/_runs",
    "python -m cbsc_zdc.cli convert --output ../prep/data",
    f"touch {WORKDIR}/prep/marker",
])
def test_exec_allows_writes_inside_the_workdir(client: Dicos, command: str) -> None:
    client._assert_command_safe(command)


@pytest.mark.parametrize("command", [
    "ls prep/data/*.npz 2>/dev/null | wc -l",
    "jupyter server list 2>/dev/null",
    "command -v sbatch >/dev/null 2>&1",
])
def test_discarding_output_to_dev_null_is_not_an_escape(
    client: Dicos, command: str
) -> None:
    """`2>/dev/null` is too common an idiom to treat as writing outside scope;
    a character device is not a file the contract is protecting."""
    client._assert_command_safe(command)


def test_reading_outside_the_workdir_is_still_permitted(client: Dicos) -> None:
    """The rule constrains writes and named datasets, not every read: setup has
    to inspect /opt interpreters and the venv to do its job."""
    client._assert_command_safe("/opt/miniconda3/envs/asgc/bin/python -V")
    client._assert_command_safe("ls /opt")
