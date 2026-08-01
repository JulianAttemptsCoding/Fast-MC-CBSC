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


@pytest.mark.parametrize("command", [
    "pip install torch==2.6.0 --index-url https://download.pytorch.org/whl/cu124",
    "curl -sSI https://pypi.org/simple/",
    "git clone https://github.com/JulianAttemptsCoding/Fast-MC-CBSC.git repo",
])
def test_urls_are_not_mistaken_for_absolute_paths(client: Dicos, command: str) -> None:
    """A URL's authority starts with '//', which matches the absolute-path
    pattern; setup was refused as a write to //download.pytorch.org/whl."""
    client._assert_command_safe(command)


def test_a_url_does_not_mask_a_real_escape_next_to_it(client: Dicos) -> None:
    """Blanking URLs must not blank the rest of the command."""
    with pytest.raises(SystemExit, match="outside the permitted workdir"):
        client._assert_command_safe(
            "curl -s https://example.com/x.tar > /dicos_ui_home/julianjuan/x.tar"
        )


@pytest.mark.parametrize(
    "command",
    [
        "(nvidia-smi --query-gpu=name --format=csv 2>/dev/null) || echo none",
        "{ python3 -V; } >/dev/null 2>&1",
        "(cat /etc/os-release 2>/dev/null)",
    ],
)
def test_a_closing_paren_does_not_stick_to_a_path(client: Dicos, command: str) -> None:
    """`info`'s own probe is `(nvidia-smi ... 2>/dev/null)`. If the token regex
    swallows the paren the candidate becomes '/dev/null)', which misses the
    sink whitelist and refuses a command that writes nothing."""
    client._assert_command_safe(command)


def test_a_paren_does_not_hide_a_real_escape(client: Dicos) -> None:
    """Ending the token at ')' must not stop the check from seeing the path."""
    with pytest.raises(SystemExit, match="outside the permitted workdir"):
        client._assert_command_safe("(echo x > /dicos_ui_home/julianjuan/escape.txt)")


def test_reading_outside_the_workdir_is_still_permitted(client: Dicos) -> None:
    """The rule constrains writes and named datasets, not every read: setup has
    to inspect /opt interpreters and the venv to do its job."""
    client._assert_command_safe("/opt/miniconda3/envs/asgc/bin/python -V")
    client._assert_command_safe("ls /opt")


# ------------------------------------------------------- job / transfer shape
# These pin behaviour that was only discovered by running against the host:
# the contents API rejects large bodies, and `&` binds to a whole `&&` chain.

def test_large_files_are_chunked(client: Dicos) -> None:
    """A 29 MB checkpoint returns HTTP 500 from the contents API, so anything
    over the chunk size must be split and reassembled rather than sent whole."""
    assert client.CHUNK_BYTES <= 8 * 1024 * 1024
    assert 29_366_432 > client.CHUNK_BYTES


@pytest.mark.parametrize("name", ["../escape", "a b", "semi;colon", "", "sl/ash"])
def test_job_names_must_be_simple(client: Dicos, name: str) -> None:
    """Job names become filenames and shell tokens; anything exotic is refused
    before it can be interpolated."""
    with pytest.raises(SystemExit, match="job name"):
        client.start("echo hi", name)


# ------------------------------------------------- continuation epoch algebra
# `training.epochs` is an absolute target, not a count of additional epochs:
# the trainer resumes at checkpoint_epoch + 1 and runs range(start, epochs).
# The first wave was built with epochs=6 against parents ending at epoch 4 and
# so ran a single epoch, annealing the cosine restart to min_learning_rate
# across it. These pin the algebra that fixes it.

def test_continuation_epochs_are_an_absolute_target() -> None:
    import build_dicos_continuations as builder

    assert builder.EPOCHS == builder.PARENT_LAST_EPOCH + 1 + builder.ADDITIONAL_EPOCHS
    start_epoch = builder.PARENT_LAST_EPOCH + 1
    assert len(range(start_epoch, builder.EPOCHS)) == builder.ADDITIONAL_EPOCHS


def test_continuation_requests_six_more_epochs() -> None:
    import build_dicos_continuations as builder

    assert builder.ADDITIONAL_EPOCHS == 6
    # Patience must not be able to cut the comparison phase short, and must not
    # be confused with the absolute epoch target.
    assert builder.ADDITIONAL_EPOCHS <= builder.EPOCHS


# ------------------------------------------------------------ setup contract
# A GPU DiCOSApp is a different image from the CPU one. The first GPU pod
# exposed three defects at once: the base interpreter fell back to Python 3.9
# (below the project floor), torch was never installed because the script
# assumed it came from the base env's site-packages, and a failed build still
# reported "setup complete" and exited 0. These pin all three.

def test_setup_requires_an_interpreter_new_enough_to_build_the_project() -> None:
    """pyproject sets requires-python >= 3.10; a 3.9 base can never install it."""
    from dicos import SETUP_SCRIPT
    assert "(3,10)" in SETUP_SCRIPT
    assert "/opt/miniconda3/bin/python" in SETUP_SCRIPT, (
        "the GPU image's own interpreter must be a candidate; without it the "
        "search falls through to /usr/bin/python3, which was 3.9.21"
    )


def test_setup_installs_the_pinned_torch_itself() -> None:
    """Torch must not be inherited from the base env: the accepted runs all used
    pytorch/pytorch:2.6.0-cuda12.4, and a GPU image need not ship torch at all."""
    from dicos import SETUP_SCRIPT
    assert "torch==2.6.0" in SETUP_SCRIPT
    assert "cu124" in SETUP_SCRIPT
    assert "-m venv --system-site-packages" not in SETUP_SCRIPT


def test_setup_failures_reach_the_exit_code() -> None:
    from dicos import SETUP_SCRIPT
    assert "_setup/.setup_failures" in SETUP_SCRIPT
    assert "exit 1" in SETUP_SCRIPT
    # Each check that can fail must route through bad() or exit non-zero.
    for expected in ("|| bad ", "setup INCOMPLETE"):
        assert expected in SETUP_SCRIPT


def test_setup_updates_the_repo_without_git_dash_c() -> None:
    """The A100 image ships git 1.8.3.1, which has no -C flag. `git -C repo
    pull` there fails into the "pull skipped" branch and runs stale code while
    reporting success -- worse than failing."""
    from dicos import SETUP_SCRIPT
    code = "\n".join(
        line for line in SETUP_SCRIPT.splitlines() if not line.lstrip().startswith("#")
    )
    assert "git -C" not in code
    assert "( cd repo && git pull --ff-only )" in code


def test_setup_never_builds_a_dependency_from_source() -> None:
    """On the A100 image (Python 3.11, GCC < 9.3) pip found no matching numpy
    wheel and fell back to an sdist, which failed with 'NumPy requires GCC >=
    9.3'. Wheels only: a missing wheel must fail loudly, not invoke a
    toolchain whose version nobody controls."""
    from dicos import SETUP_SCRIPT
    assert "--only-binary=:all:" in SETUP_SCRIPT


def test_setup_keeps_the_venv_build_log() -> None:
    """The original build discarded pip's output, so the failure was invisible."""
    from dicos import SETUP_SCRIPT
    assert "_setup/venv_build.log" in SETUP_SCRIPT


def test_job_command_is_guarded_before_being_detached(client: Dicos) -> None:
    """`start` must apply the same contract as `exec` -- a detached job that
    escapes the workdir is worse, not better, than an interactive one."""
    with pytest.raises(SystemExit, match="outside the permitted workdir"):
        client.start("rm -rf /dicos_ui_home/julianjuan/.jupyter", "evil")
    with pytest.raises(SystemExit, match="out of scope"):
        client.start(f"cp {TRANSFORMED} .", "evil")
