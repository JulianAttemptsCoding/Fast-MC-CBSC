#!/usr/bin/env python3
"""Programmatic access to a DiCOS (ASGC) JupyterLab instance.

DiCOS exposes no SSH path we can automate (ASGC mandates Google-Authenticator
OTP on its login services), but the DiCOSApp JupyterLab is directly reachable
and its token authenticates the REST and kernel-websocket APIs. This client
wraps those into a small CLI so any agent or shell can drive the remote host:

    python scripts/dicos.py auth "<launch or address-bar URL>"   # start a session
    python scripts/dicos.py setup                                # provision/repair
    python scripts/dicos.py verify                               # re-hash artifacts
    python scripts/dicos.py info                                 # probe environment
    python scripts/dicos.py exec "nvidia-smi"                    # synchronous shell
    python scripts/dicos.py ls / put / get / mkdir                # files
    python scripts/dicos.py start "<cmd>" --name job             # detached, for hours
    python scripts/dicos.py jobs / logs job / stop job           # job control

Credentials live in ~/.dicos/config.json (outside the repository), holding
base_url, token, jupyter_root, workdir, data_file, and forbidden_paths.

DiCOS has been observed to issue a stable per-user token, so when a pod is
relaunched usually only its port changes. `auth` therefore accepts a URL with no
token and reuses the stored one; it verifies before saving and saves nothing on
failure.

Access scope is enforced client-side and mirrors the contract in AGENTS.md
17-21:

  * `put`/`mkdir` refuse any destination outside the configured workdir,
    after normalising `..` so traversal cannot slip past;
  * `exec` refuses commands that mutate `data_file`, the one permitted dataset;
  * `exec`/`start` refuse commands that appear to write outside the workdir;
  * `exec` refuses any command that so much as names a `forbidden_paths` entry,
    since those are out of scope for reading too.

These guards catch honest mistakes; they are not a security boundary, because
the token carries whatever permissions the account has.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import posixpath
import re
import shlex
import sys
import time
import uuid
from pathlib import Path

import requests

shlex_quote = shlex.quote

CONFIG_PATH = Path.home() / ".dicos" / "config.json"


TEMPLATE_PATH = Path(__file__).resolve().parent / "dicos_config.template.json"


def load_config() -> dict:
    """Credentials, or an actionable explanation of how to create them.

    The config lives outside the repository because it holds a token, so a
    fresh machine has none. Failing with just a path would leave the next
    agent guessing at account-specific values, which is exactly how the write
    guard ends up mis-scoped -- so point at the checked-in template instead.
    """
    if not CONFIG_PATH.exists():
        raise SystemExit(f"""no credentials at {CONFIG_PATH}

Create that file by copying the checked-in template:
    mkdir -p {CONFIG_PATH.parent}
    cp "{TEMPLATE_PATH}" "{CONFIG_PATH}"

then set `token` (docs/DICOS_BACKEND.md, "Recovering the token"), or run:
    python scripts/dicos.py auth "<URL containing ?token=...>"

The remaining fields encode the filesystem contract in AGENTS.md 17-21 --
workdir, data_file, forbidden_paths -- and must not be widened.""")
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


class Dicos:
    def __init__(self, config: dict):
        self.base = config["base_url"].rstrip("/")
        self.token = config["token"]
        self.workdir = config["workdir"].rstrip("/")
        # The contents API is rooted at the server's root_dir (here the user's
        # HOME), while exec/shell paths are absolute. Keeping the root lets the
        # two address spaces be translated instead of confused.
        self.jupyter_root = config.get("jupyter_root", "").rstrip("/")
        # The single permitted data source: readable, never writable.
        self.data_file = (config.get("data_file") or "").rstrip("/")
        # Paths that must not be touched at all, reads included.
        self.forbidden = [p.rstrip("/") for p in config.get("forbidden_paths", [])]
        self.readonly = [p for p in [self.data_file] if p]
        self.session = requests.Session()
        self.session.headers["Authorization"] = f"token {self.token}"

    # ------------------------------------------------------------ contents
    def _contents(self, path: str) -> str:
        """Translate an absolute remote path into a contents-API path."""
        if self.jupyter_root and path.startswith(self.jupyter_root):
            return path[len(self.jupyter_root):].lstrip("/")
        return path.lstrip("/")

    def ls(self, path: str) -> list[dict]:
        target = self._resolve(path)
        r = self.session.get(
            f"{self.base}/api/contents/{self._contents(target)}",
            params={"content": "1"}, timeout=60,
        )
        r.raise_for_status()
        payload = r.json()
        if payload["type"] != "directory":
            return [payload]
        return sorted(payload["content"], key=lambda c: (c["type"] != "directory", c["name"]))

    def get(self, remote: str, local: Path) -> int:
        target = self._resolve(remote)
        r = self.session.get(
            f"{self.base}/api/contents/{self._contents(target)}",
            params={"content": "1"}, timeout=300,
        )
        r.raise_for_status()
        payload = r.json()
        if payload["format"] == "base64":
            data = base64.b64decode(payload["content"])
        else:
            data = payload["content"].encode("utf-8")
        local.parent.mkdir(parents=True, exist_ok=True)
        local.write_bytes(data)
        return len(data)

    #: The contents API takes the whole body as base64 JSON, and the server
    #: rejects large payloads outright (a 29 MB checkpoint returns HTTP 500).
    #: Anything above this is uploaded in parts and reassembled on the host.
    CHUNK_BYTES = 4 * 1024 * 1024

    def _put_bytes(self, data: bytes, target: str, timeout: int = 300) -> None:
        body = {
            "type": "file", "format": "base64",
            "content": base64.b64encode(data).decode("ascii"),
        }
        r = self.session.put(
            f"{self.base}/api/contents/{self._contents(target)}",
            json=body, timeout=timeout,
        )
        r.raise_for_status()

    def put(self, local: Path, remote: str, log=None) -> int:
        target = self._resolve(remote)
        self._assert_writable(target)
        data = local.read_bytes()
        self.mkdir(posixpath.dirname(target))

        if len(data) <= self.CHUNK_BYTES:
            self._put_bytes(data, target)
            return len(data)

        # Chunked: upload parts, then concatenate on the host in one shell step
        # and verify by SHA-256 before removing them, so a truncated transfer
        # cannot masquerade as a complete file.
        parts = [data[i:i + self.CHUNK_BYTES] for i in range(0, len(data), self.CHUNK_BYTES)]
        digest = hashlib.sha256(data).hexdigest()
        for index, part in enumerate(parts):
            self._put_bytes(part, f"{target}.part{index:04d}")
            if log:
                log(f"  part {index + 1}/{len(parts)} ({len(part)} bytes)")
        base = posixpath.basename(target)
        directory = posixpath.dirname(target)
        script = (
            f"cd {shlex_quote(directory)} && "
            f"cat {shlex_quote(base)}.part* > {shlex_quote(base)} && "
            f"rm -f {shlex_quote(base)}.part* && "
            f'test "$(sha256sum {shlex_quote(base)} | cut -d" " -f1)" = {digest} '
            f'&& echo VERIFIED || {{ echo "CHECKSUM MISMATCH"; exit 1; }}'
        )
        if self._run(script, directory, timeout=600) != 0:
            raise SystemExit(f"chunked upload of {target} failed verification")
        return len(data)

    def mkdir(self, remote: str) -> None:
        """Create a directory (and parents).

        The contents API answers 405 for a directory PUT here, so this goes
        through the shell, which also keeps parent creation available.
        """
        target = self._resolve(remote)
        self._assert_writable(target)
        self._run(f"mkdir -p {shlex_quote(target)}", self.workdir, timeout=60)

    # -------------------------------------------------------------- guards
    def _resolve(self, path: str) -> str:
        """Absolute remote path; bare/relative paths resolve inside workdir.

        Normalises before returning so that traversal (`..`) cannot smuggle a
        destination past `_assert_writable`, and rejects Windows-style paths
        outright: a drive letter here means a local path leaked into a remote
        argument, which Git Bash does silently when a POSIX-looking absolute
        path is passed on the command line.
        """
        if re.match(r"^[A-Za-z]:[\\/]", path) or "\\" in path:
            raise SystemExit(
                f"{path!r} looks like a local Windows path, not a remote one.\n"
                "If you meant an absolute remote path, prefix the command with "
                "MSYS_NO_PATHCONV=1 (Git Bash rewrites POSIX paths otherwise), "
                "or pass it relative to the workdir."
            )
        combined = path if path.startswith("/") else f"{self.workdir}/{path.strip('/')}"
        resolved = posixpath.normpath(combined)
        if resolved in ("", "."):
            return self.workdir
        return resolved.rstrip("/") or "/"

    def _assert_writable(self, target: str) -> None:
        if target == self.workdir or target.startswith(self.workdir + "/"):
            return
        raise SystemExit(
            f"refusing to write outside the permitted workdir\n"
            f"  target:  {target}\n  allowed: {self.workdir}/**"
        )

    #: Shell constructs that create or destroy files. Matched against absolute
    #: paths only; relative paths run with cwd inside the workdir and are fine.
    _WRITE_VERBS = (
        "rm", "rmdir", "mv", "cp", "touch", "mkdir", "install", "tee", "dd",
        "truncate", "shred", "chmod", "chown", "ln", "rsync", "tar", "unzip",
    )

    def _assert_writes_stay_in_workdir(self, command: str) -> None:
        """Best-effort check that a shell command writes only inside the workdir.

        A shell cannot be fully parsed here, so this is a guard against the
        obvious and the accidental -- redirections and file-mutating commands
        naming an absolute path outside the permitted tree. It is deliberately
        conservative about what it claims: a determined command (a glob, a
        here-doc, a Python one-liner) can still escape, which is why the
        filesystem contract is also stated in AGENTS.md for humans and agents
        to honour, not left to this function alone.
        """
        # Positions are tracked, not just the matched text, because the workdir
        # itself contains a space ("Fast MC CBSC"): a token-based regex stops at
        # that space and would mistake a legitimate in-workdir path for an
        # escape. Comparing against the full workdir at the match offset avoids
        # depending on how the caller quoted it.
        # A URL is not a filesystem path, but its authority begins with "//" and
        # so matches the absolute-path patterns below -- `pip --index-url
        # https://download.pytorch.org/whl/cu124` was refused as a write to
        # //download.pytorch.org/whl. Blank the URLs out first, preserving
        # offsets so the workdir comparison below stays aligned.
        scan = re.sub(r"\w+://\S*", lambda m: " " * len(m.group(0)), command)

        suspects: list[tuple[str, int]] = []
        for match in re.finditer(r">>?\s*(~?/[^\s;|&'\"]+)", scan):
            suspects.append((match.group(1), match.start(1)))
        verbs = "|".join(self._WRITE_VERBS)
        for verb_match in re.finditer(rf"\b({verbs})\b([^;|&\n]*)", scan):
            segment, offset = verb_match.group(2), verb_match.start(2)
            for match in re.finditer(r"(?<![\w=])(~?/[^\s;|&'\"]+)", segment):
                suspects.append((match.group(1), offset + match.start(1)))

        # Character devices are not files anyone can damage, and `2>/dev/null`
        # is too common an idiom to treat as an escape attempt.
        sinks = {"/dev/null", "/dev/stdout", "/dev/stderr", "/dev/tty", "/dev/zero"}
        home = self.jupyter_root or ""
        for raw, position in suspects:
            if raw in sinks:
                continue
            # The command may continue with the (space-containing) workdir at
            # this offset even though the token stopped early.
            if command.startswith(self.workdir, position):
                continue
            candidate = raw
            if candidate.startswith("~"):
                if not home:
                    continue
                candidate = home + candidate[1:]
                if candidate == self.workdir or candidate.startswith(self.workdir + "/"):
                    continue
            resolved = posixpath.normpath(candidate)
            if resolved == self.workdir or resolved.startswith(self.workdir + "/"):
                continue
            raise SystemExit(
                "refusing: command appears to write outside the permitted workdir\n"
                f"  target:  {resolved}\n  allowed: {self.workdir}/**\n"
                f"  command: {command}\n"
                "If this is a false positive (the path is only read, not written), "
                "run the read through a form that does not look like a write, or "
                "narrow the command."
            )

    def _assert_command_safe(self, command: str) -> None:
        # Forbidden paths are off-limits entirely -- a mere mention is refused,
        # since reading them is as much a violation as writing them.
        for banned in self.forbidden:
            if banned in command or posixpath.basename(banned) in command:
                raise SystemExit(
                    f"refusing: that path is out of scope for this project\n"
                    f"  forbidden: {banned}\n  command:   {command}\n"
                    f"The only permitted data source is:\n  {self.data_file}"
                )
        for protected in self.readonly:
            # Any shell redirection into, or in-place mutation of, a declared
            # read-only dataset file.
            escaped = re.escape(protected)
            patterns = [
                rf">>?\s*{escaped}",
                rf"\b(rm|mv|chmod|chown|truncate|dd|shred|ln)\b[^|;&]*{escaped}",
                rf"\b(cp|rsync)\b[^|;&]*\s{escaped}\s*$",
            ]
            for pattern in patterns:
                if re.search(pattern, command):
                    raise SystemExit(
                        f"refusing: command appears to modify a read-only dataset\n"
                        f"  protected: {protected}\n  command:   {command}"
                    )
        self._assert_writes_stay_in_workdir(command)

    # ------------------------------------------------------- detached jobs
    #: Long work cannot run through `exec`: it is synchronous, and a DiCOSApp
    #: pod outlives any one client call but not indefinitely. Detached jobs are
    #: started under nohup with their output on the shared filesystem, so they
    #: survive the client disconnecting and remain inspectable afterwards --
    #: including from a later session, or after the pod is relaunched.
    JOBS_DIR = "_runs"

    def start(self, command: str, name: str, cwd: str | None = None) -> int:
        self._assert_command_safe(command)
        if not re.fullmatch(r"[A-Za-z0-9._-]+", name):
            raise SystemExit(f"job name must be simple, got {name!r}")
        workdir = self._resolve(cwd) if cwd else self.workdir
        # `&` binds to the whole `&&` chain, so the setup must complete in
        # separate statements first; otherwise mkdir itself is backgrounded and
        # the pid write races it.
        wrapper = (
            f"cd {shlex_quote(workdir)}; "
            f"mkdir -p {self.JOBS_DIR}; "
            f"nohup sh -c {shlex_quote(command)} "
            f"> {self.JOBS_DIR}/{name}.log 2>&1 & "
            f"echo $! > {self.JOBS_DIR}/{name}.pid; "
            f"sleep 1; echo \"started {name} pid=$(cat {self.JOBS_DIR}/{name}.pid)\""
        )
        return self._run(wrapper, self.workdir, timeout=120)

    def jobs(self) -> int:
        script = (
            f'cd {shlex_quote(self.workdir)} 2>/dev/null || exit 0; '
            f'[ -d {self.JOBS_DIR} ] || {{ echo "no jobs recorded"; exit 0; }}; '
            f'for p in {self.JOBS_DIR}/*.pid; do [ -e "$p" ] || continue; '
            f'n=$(basename "$p" .pid); pid=$(cat "$p"); '
            f'if kill -0 "$pid" 2>/dev/null; then s=RUNNING; else s=finished; fi; '
            f'sz=$(wc -c < {self.JOBS_DIR}/"$n".log 2>/dev/null || echo 0); '
            f'printf "  %-24s %-8s pid=%-8s log=%s bytes\\n" "$n" "$s" "$pid" "$sz"; done'
        )
        return self._run(script, self.workdir, timeout=120)

    def stop(self, name: str) -> int:
        """Terminate a detached job by its recorded pid.

        SIGTERM first so the process can checkpoint or clean up; the caller can
        re-run to escalate if it is still alive.
        """
        script = (
            f'p={self.JOBS_DIR}/{shlex_quote(name)}.pid; '
            f'[ -e "$p" ] || {{ echo "no such job: {name}"; exit 1; }}; '
            f'pid=$(cat "$p"); '
            f'if kill -0 "$pid" 2>/dev/null; then '
            f'  pkill -TERM -P "$pid" 2>/dev/null; kill -TERM "$pid" 2>/dev/null; '
            f'  sleep 2; '
            f'  if kill -0 "$pid" 2>/dev/null; then echo "still running, re-run to escalate"; '
            f'  else echo "stopped {name} (pid $pid)"; fi; '
            f'else echo "{name} was already finished"; fi'
        )
        return self._run(script, self.workdir, timeout=120)

    def logs(self, name: str, tail: int = 40) -> int:
        return self._run(
            f"tail -n {int(tail)} {self.JOBS_DIR}/{shlex_quote(name)}.log",
            self.workdir, timeout=120,
        )

    # ---------------------------------------------------------- execution
    def exec(self, command: str, cwd: str | None = None, timeout: int = 300) -> int:
        """Run a shell command in a transient kernel; stream stdout/stderr."""
        self._assert_command_safe(command)
        return self._run(command, self._resolve(cwd) if cwd else self.workdir, timeout)

    def _run(self, command: str, workdir: str, timeout: int = 300) -> int:
        """Transport only. Callers are responsible for having applied guards."""
        import websocket  # imported lazily so contents-only use needs no ws dep

        r = self.session.post(f"{self.base}/api/kernels", json={"name": "python3"}, timeout=60)
        r.raise_for_status()
        kernel_id = r.json()["id"]
        try:
            ws_url = (
                self.base.replace("https://", "wss://").replace("http://", "ws://")
                + f"/api/kernels/{kernel_id}/channels?token={self.token}"
            )
            # Per-recv socket timeout is deliberately short and independent of
            # the overall budget: a command that is working but silent (a clone,
            # a long hash) must not look like a dead connection. The loop below
            # tolerates idle recvs and enforces the real deadline itself.
            #
            # Retries cover *establishing* the connection only. Once the command
            # has been sent it may already have had effects, so a drop mid-flight
            # is reported rather than silently re-run -- re-running `start` would
            # launch a second training job.
            ws = None
            for attempt in range(3):
                try:
                    ws = websocket.create_connection(ws_url, timeout=30)
                    break
                except (ConnectionError, OSError, websocket.WebSocketException) as exc:
                    if attempt == 2:
                        raise SystemExit(f"could not open a kernel channel: {exc}")
                    time.sleep(2 * (attempt + 1))
            code = (
                "import subprocess,sys\n"
                f"_p=subprocess.run({command!r},shell=True,cwd={workdir!r},"
                "capture_output=True,text=True,errors='replace')\n"
                "sys.stdout.write(_p.stdout)\n"
                "sys.stderr.write(_p.stderr)\n"
                "print('__DICOS_EXIT__%d'%_p.returncode)\n"
            )
            msg_id = uuid.uuid4().hex
            ws.send(json.dumps({
                "header": {
                    "msg_id": msg_id, "username": "dicos", "session": uuid.uuid4().hex,
                    "msg_type": "execute_request", "version": "5.3",
                },
                "parent_header": {}, "metadata": {},
                "content": {
                    "code": code, "silent": False, "store_history": False,
                    "user_expressions": {}, "allow_stdin": False, "stop_on_error": True,
                },
                "channel": "shell",
            }))

            exit_code = 0
            deadline = time.time() + timeout
            while True:
                if time.time() > deadline:
                    sys.stderr.write(f"\n[dicos] timed out after {timeout}s\n")
                    exit_code = exit_code or 124
                    break
                try:
                    raw = ws.recv()
                except websocket.WebSocketTimeoutException:
                    continue  # silent-but-working command; keep waiting
                except (ConnectionError, OSError) as exc:
                    # The command may still be running on the host. Say so
                    # rather than implying it failed.
                    sys.stderr.write(
                        f"\n[dicos] connection dropped: {exc}\n"
                        "[dicos] the remote command may still be running; "
                        "check with `jobs` / `logs` before re-running.\n"
                    )
                    return 75
                message = json.loads(raw)
                if message.get("parent_header", {}).get("msg_id") != msg_id:
                    continue
                kind = message["msg_type"]
                content = message.get("content", {})
                if kind == "stream":
                    text = content.get("text", "")
                    marker = re.search(r"__DICOS_EXIT__(\d+)", text)
                    if marker:
                        exit_code = int(marker.group(1))
                        text = text[: marker.start()] + text[marker.end():]
                    stream = sys.stderr if content.get("name") == "stderr" else sys.stdout
                    stream.write(text)
                    stream.flush()
                elif kind == "error":
                    sys.stderr.write("\n".join(content.get("traceback", [])) + "\n")
                    exit_code = exit_code or 1
                elif kind == "status" and content.get("execution_state") == "idle":
                    break
            ws.close()
            return exit_code
        finally:
            # Best-effort cleanup: a failed teardown must not mask the command's
            # own result, and the server reaps idle kernels regardless.
            try:
                self.session.delete(f"{self.base}/api/kernels/{kernel_id}", timeout=60)
            except requests.RequestException:
                pass

    # -------------------------------------------------------------- status
    def status(self) -> dict:
        r = self.session.get(f"{self.base}/api/status", timeout=30)
        r.raise_for_status()
        return r.json()


#: Idempotent provisioning. A DiCOSApp is a fresh container every launch, and a
#: GPU app is a different image from the CPU one, so the venv is validated by
#: import rather than by existence -- a venv built against another base env is
#: present but broken. Everything lives on the shared filesystem, so repeated
#: runs are cheap and only repair what is actually missing.
SETUP_SCRIPT = r"""
set -u
REPO_URL="https://github.com/JulianAttemptsCoding/Fast-MC-CBSC.git"
GEOM_HASH="e22d4cfb1e9293a33dd13151587910268ba64cd8efbcdb7a835a7442f2edcb4b"
ok(){ printf '  [ok]   %s\n' "$1"; }
fix(){ printf '  [fix]  %s\n' "$1"; }
#: Every failure must reach the exit code. Earlier this only printed, so a pod
#: with a broken venv still reported "setup complete" and exited 0.
bad(){ printf '  [FAIL] %s\n' "$1"; echo "$1" >> _setup/.setup_failures; }

echo "1. workdir"
mkdir -p _setup prep && ok "$(pwd)"
rm -f _setup/.setup_failures

echo "2. repository"
if [ -d repo/.git ]; then
  git -C repo pull --ff-only >/dev/null 2>&1 && ok "repo updated" || ok "repo present (pull skipped)"
else
  fix "cloning"; git clone --depth 1 "$REPO_URL" repo >/dev/null 2>&1 \
    && ok "cloned" || bad "clone failed"
fi

echo "3. base interpreter"
# pyproject requires >=3.10, so an older interpreter can never build the repo.
# Candidates are ordered most- to least-preferred; the first that satisfies the
# floor wins. A GPU image need not ship torch -- step 4 installs it.
BASE=""
for cand in /opt/miniconda3/envs/asgc/bin/python /opt/miniconda3/bin/python \
            /opt/conda/bin/python3 /usr/local/bin/python3 /usr/bin/python3; do
  [ -x "$cand" ] || continue
  "$cand" -c 'import sys; sys.exit(0 if sys.version_info[:2] >= (3,10) else 1)' 2>/dev/null || continue
  BASE="$cand"; break
done
[ -n "$BASE" ] && ok "base $BASE ($($BASE -V 2>&1))" || bad "no interpreter >= 3.10 found"

echo "4. venv"
NEED=0
if [ -x .venv/bin/python ]; then
  .venv/bin/python -c "import torch,numpy,uproot,cbsc_zdc" >/dev/null 2>&1 \
    && ok "venv healthy" || { NEED=1; fix "venv present but broken -> rebuilding"; }
else
  NEED=1; fix "venv missing -> creating"
fi
if [ "$NEED" = 1 ] && [ -n "$BASE" ]; then
  # Every accepted run used pytorch/pytorch:2.6.0-cuda12.4; pin that so a
  # backend move does not silently change the numerics. Isolated from the base
  # env on purpose: --system-site-packages once let a foreign torch decide
  # whether this step was even needed.
  BUILDLOG=_setup/venv_build.log
  fix "building venv (torch 2.6.0+cu124), log -> $BUILDLOG"
  { rm -rf .venv
    "$BASE" -m venv .venv \
    && .venv/bin/python -m pip install --upgrade pip setuptools wheel \
    && .venv/bin/pip install torch==2.6.0 --index-url https://download.pytorch.org/whl/cu124 \
    && .venv/bin/pip install --only-binary=:all: "numpy<3" pyyaml uproot awkward scikit-learn \
    && .venv/bin/pip install -e repo ; } >"$BUILDLOG" 2>&1
  .venv/bin/python -c "import torch,numpy,uproot,cbsc_zdc" >/dev/null 2>&1 \
    && ok "venv built ($(.venv/bin/python -c 'import torch;print(torch.__version__)'))" \
    || bad "venv build failed -- see $BUILDLOG"
fi

echo "5. frozen geometry"
if [ -f prep/geometry_frozen/geometry.npz ]; then
  .venv/bin/python - <<PY || bad "geometry hash mismatch"
import json,sys,numpy as np
sys.path.insert(0,"repo/src")
from cbsc_zdc.data.geometry import geometry_hash
got=geometry_hash(dict(np.load("prep/geometry_frozen/geometry.npz")))
if got=="$GEOM_HASH":
    print("  [ok]   geometry hash verified")
else:
    print("  [FAIL] geometry hash MISMATCH "+got); sys.exit(1)
PY
else
  bad "prep/geometry_frozen/geometry.npz absent -- upload it (see docs/DICOS_BACKEND.md)"
fi

echo "6. compute"
if command -v nvidia-smi >/dev/null 2>&1; then
  nvidia-smi --query-gpu=name,memory.total --format=csv,noheader | sed 's/^/  [ok]   GPU /'
  .venv/bin/python -c "import torch;print('  [%s]   torch.cuda.is_available()=%s'%('ok' if torch.cuda.is_available() else 'WARN',torch.cuda.is_available()))"
else
  echo "  [note] CPU-only pod ($(nproc) cores) -- fine for conversion, not training"
fi

echo "7. source data (read-only)"
D=~/sharedfs/work/IOP/ZDC_ML_20260620/dataset/myTree_20251117_765k_0to300GeV_neutron_All.root
[ -r "$D" ] && ok "readable, $(stat -c%s "$D") bytes" || bad "source dataset not readable"

echo "8. prepared corpus"
if [ -f prep/data/dataset_manifest.json ]; then
  .venv/bin/python - <<'PY' || bad "prepared corpus does not match the canonical corpus"
import json, sys
from pathlib import Path
m = json.loads(Path("prep/data/dataset_manifest.json").read_text())
n, shards = m["n_events"], len(m["shards"])
good = (n == 764940 and shards == 187
        and m["geometry_hash"] == "e22d4cfb1e9293a33dd13151587910268ba64cd8efbcdb7a835a7442f2edcb4b"
        and all(v == 0 for v in m["rejected"].values()))
print(f"  [{'ok  ' if good else 'FAIL'}]   {n} events in {shards} shards, "
      f"rejections {sum(m['rejected'].values())}")
sys.exit(0 if good else 1)
PY
else
  echo "  [note] not built yet -- see docs/DICOS_BACKEND.md step 5"
fi

echo "9. split"
if [ -f prep/splits.json ]; then
  .venv/bin/python - <<'PY' || bad "split does not match the canonical assignment"
import json, sys
from pathlib import Path
s = json.loads(Path("prep/splits.json").read_text())
want = {"train": 612482, "validation": 76158, "test": 76300}
canon = "f71003e07eb16baf4029387fd8e54b2e22b98981bbd6ee519a6d363167b4c8c8"
good = s["counts"] == want and s["assignment_sha256"] == canon
print(f"  [{'ok  ' if good else 'FAIL'}]   {s['counts']}"
      + ("" if good else "  <- does NOT match the canonical assignment"))
sys.exit(0 if good else 1)
PY
else
  echo "  [note] not built yet -- see docs/DICOS_BACKEND.md step 6"
fi
echo
if [ -s _setup/.setup_failures ]; then
  printf 'setup INCOMPLETE -- %s check(s) failed:\n' "$(wc -l < _setup/.setup_failures)"
  sed 's/^/  - /' _setup/.setup_failures
  exit 1
fi
echo "setup complete"
"""

#: Full integrity check of the prepared artifacts, re-hashing from disk rather
#: than trusting recorded values, so a truncated or corrupted file cannot pass.
#: The 187 shard hashes are compared through a single aggregate digest over the
#: sorted (path, sha256) pairs, which is as strong as listing them and small
#: enough to inline. Run this after any pod change, and before relying on the
#: corpus for a training run.
VERIFY_SCRIPT = r"""
./.venv/bin/python - <<'PY'
import hashlib, json, os, sys
from pathlib import Path
sys.path.insert(0, "repo/src")
import numpy as np
from cbsc_zdc.data.geometry import geometry_hash

GEOM   = "e22d4cfb1e9293a33dd13151587910268ba64cd8efbcdb7a835a7442f2edcb4b"
SHARDS = "6932abdd5b9bc5d844b5f388cc8df845cf1dd859c1afb95ef5d33a8fcf96f362"
ASSIGN = "f71003e07eb16baf4029387fd8e54b2e22b98981bbd6ee519a6d363167b4c8c8"
SCHEMA = "4fbede6b9769d308cc80e69c8540c46b3d2ef36630ba5827e174c9f95bd20aab"
COUNTS = {"train": 612482, "validation": 76158, "test": 76300}

fails, n = [], 0
def check(label, got, want):
    global n
    n += 1
    if got == want:
        print(f"  [ok]   {label}")
    else:
        fails.append(label)
        print(f"  [FAIL] {label}\n           got  {got}\n           want {want}")

def sha(path, chunk=1 << 22):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        while b := fh.read(chunk):
            h.update(b)
    return h.hexdigest()

print("geometry")
check("hash recomputed from arrays",
      geometry_hash(dict(np.load("prep/geometry_frozen/geometry.npz"))), GEOM)
cm = json.loads(Path("prep/geometry_frozen/cell_map.json").read_text())
check("cell_map bijective over 6790", sorted(cm.values()) == list(range(6790)), True)

print("prepared corpus")
man = json.loads(Path("prep/data/dataset_manifest.json").read_text())
pairs, ev, hits, bad = [], 0, 0, 0
for e in man["shards"]:
    actual = sha(Path("prep/data") / e["path"])
    bad += actual != e["sha256"]
    pairs.append((e["path"], actual)); ev += e["n_events"]; hits += e["n_hits"]
agg = hashlib.sha256("".join(f"{p}:{h}" for p, h in sorted(pairs)).encode()).hexdigest()
check("shard count", len(man["shards"]), 187)
check("shards matching their manifest entry", bad, 0)
check("aggregate of all 187 content hashes", agg, SHARDS)
check("total events", ev, 764940)
check("total hits", hits, 1157840863)
check("geometry_hash", man["geometry_hash"], GEOM)
check("schema_sha256", man["schema_sha256"], SCHEMA)
check("rejections", sum(man["rejected"].values()), 0)

print("split")
sp = json.loads(Path("prep/splits.json").read_text())
check("counts", sp["counts"], COUNTS)
check("assignment re-hashed", sha("prep/splits_assignments.npz"), ASSIGN)
check("split pins this manifest", sp["manifest_sha256"], sha("prep/data/dataset_manifest.json"))

print("audit")
au = json.loads(Path("prep/train_data_audit.json").read_text())
check("n_events", au["n_events"], 612482)
check("response_cap_ratio", au["response_cap_ratio"], 0.6301101273502666)

print("checkpoints")
ck = Path("prep/checkpoints")
found = sorted(p.name for p in ck.glob("*.pt")) if ck.exists() else []
print(f"  [info] {len(found)} staged: {found}")
if (ck / "calibrated_lr3e4_best_epoch4.pt").exists():
    check("calibrated_lr3e4 epoch4 sha256",
          sha(ck / "calibrated_lr3e4_best_epoch4.pt"),
          "3f1022b87361b8a14d9f8432273dcd6c72f6a5e599c1be1575e7f37f4014803d")

print("hygiene")
mine, pid = set(), os.getpid()
while pid > 1:
    mine.add(pid)
    try:
        pid = int(Path(f"/proc/{pid}/stat").read_text().split(")")[-1].split()[1])
    except Exception:
        break
alive = []
for f in Path("_runs").glob("*.pid") if Path("_runs").exists() else []:
    try:
        q = int(f.read_text().strip())
    except ValueError:
        continue
    if q in mine:
        continue
    try:
        os.kill(q, 0); alive.append(f.stem)
    except OSError:
        pass
check("no other job running", alive, [])
check("no leftover upload parts", [str(p) for p in Path("prep").rglob("*.part*")], [])

print()
print(f"{n - len(fails)}/{n} checks passed")
print("VERIFIED" if not fails else f"PROBLEMS: {fails}")
sys.exit(1 if fails else 0)
PY
"""

INFO_SCRIPT = r"""
echo "=== identity / host ==="
whoami; hostname; echo "pwd: $(pwd)"
echo
echo "=== GPU ==="
(nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv 2>/dev/null) || echo "no nvidia-smi (CPU-only pod)"
echo
echo "=== python / ML stack ==="
python3 -V 2>&1
python3 -c "import torch;print('torch',torch.__version__,'cuda',torch.cuda.is_available(),torch.version.cuda)" 2>&1 | tail -1
python3 -c "import numpy;print('numpy',numpy.__version__)" 2>&1 | tail -1
python3 -c "import uproot;print('uproot',uproot.__version__)" 2>&1 | tail -1
echo
echo "=== batch system ==="
for c in sbatch squeue sinfo condor_submit; do
  printf '%-14s %s\n' "$c" "$(command -v $c || echo '-- not present --')"
done
echo
echo "=== workdir ==="
ls -la . 2>&1 | head -20
echo
echo "=== write permission check ==="
(touch .dicos_write_test && rm .dicos_write_test && echo "writable: yes") || echo "writable: NO"
echo
echo "=== disk / quota ==="
df -h . 2>&1 | tail -2
"""


def main() -> int:
    # Remote output is UTF-8 (pip progress bars use box-drawing glyphs). A
    # Windows console defaults to cp1252 and raises UnicodeEncodeError on them,
    # which would lose an entire job log to a rendering detail.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("exec", help="run a shell command remotely")
    p.add_argument("command")
    p.add_argument("--cwd")
    p.add_argument("--timeout", type=int, default=300)

    p = sub.add_parser(
        "start", help="run a long command detached (survives client disconnect)")
    p.add_argument("command")
    p.add_argument("--name", required=True, help="job name, used for its log")
    p.add_argument("--cwd")

    sub.add_parser("jobs", help="list detached jobs and whether they are running")

    p = sub.add_parser("stop", help="terminate a detached job")
    p.add_argument("name")

    p = sub.add_parser("logs", help="tail a detached job's log")
    p.add_argument("name")
    p.add_argument("--tail", type=int, default=40)

    p = sub.add_parser("ls", help="list a remote path")
    p.add_argument("path", nargs="?", default=".")

    p = sub.add_parser("put", help="upload a file")
    p.add_argument("local"); p.add_argument("remote")

    p = sub.add_parser("get", help="download a file")
    p.add_argument("remote"); p.add_argument("local")

    p = sub.add_parser("mkdir", help="create a remote directory")
    p.add_argument("remote")

    p = sub.add_parser(
        "auth",
        help="refresh the stored token after a DiCOSApp restart",
        description=(
            "A DiCOSApp session ends on its own schedule and the next one issues a "
            "new token, so this is the first thing to run in a new session. Paste "
            "either the whole launch URL from the portal or just the token."
        ),
    )
    p.add_argument("url_or_token", help="launch URL containing ?token=..., or the bare token")
    p.add_argument(
        "token", nargs="?",
        help="token, when the first argument is a browser URL that has none "
             "(Jupyter strips ?token= from the address bar after login)",
    )

    sub.add_parser("setup", help="idempotently provision the remote workdir")
    sub.add_parser("verify", help="re-hash and verify the prepared artifacts")
    sub.add_parser("info", help="probe the remote environment")
    sub.add_parser("status", help="server status")

    args = parser.parse_args()

    STALE = (
        "DiCOS rejected the stored credentials (HTTP {code}).\n"
        "\n"
        "The token has so far been stable per user, so the usual cause is that the\n"
        "pod moved to a different port, not that the token changed.\n"
        "\n"
        "  1. Open the DiCOSApp from https://dicos.grid.sinica.edu.tw/dockerapps/\n"
        "  2. Re-point at it with the address-bar URL:\n"
        "       python scripts/dicos.py auth \"<URL>\"\n"
        "     (the stored token is reused when the URL carries none)\n"
        "  3. If that still fails, the token did change. Recover it in a\n"
        "     JupyterLab terminal (File > New > Terminal):\n"
        "       jupyter server list\n"
        "     then:\n"
        "       python scripts/dicos.py auth \"<URL>\" \"<token>\"\n"
    )

    if args.cmd == "auth":
        raw = args.url_or_token.strip()
        explicit = (args.token or "").strip()
        found = re.search(r"[?&]token=([0-9a-fA-F]{16,})", raw)
        config = load_config()
        stored = config.get("token", "")

        token = explicit or (found.group(1) if found else raw)
        reused = False
        if not re.fullmatch(r"[0-9a-fA-F]{16,}", token):
            # A URL copied from the address bar has no token, because Jupyter
            # moves it into a cookie after login. DiCOS has been observed to
            # issue a stable per-user token, so the stored one is very likely
            # still valid and only the pod's port has changed. Try it rather
            # than making the user hunt for something that has not changed.
            if re.match(r"https?://", raw) and re.fullmatch(r"[0-9a-fA-F]{16,}", stored):
                token, reused = stored, True
            else:
                raise SystemExit(
                    "no token found, and none stored to fall back on.\n"
                    "Jupyter removes ?token=... from the address bar after login, so a "
                    "URL copied later will not contain one. Recover it with any of:\n"
                    "  - JupyterLab: File > New > Terminal, then `jupyter server list`\n"
                    "  - a notebook cell (newest by mtime; sorting by name is\n"
                    "    lexicographic on PID and can return a dead pod's token):\n"
                    "      import json,glob,os,pathlib\n"
                    "      f=glob.glob(str(pathlib.Path.home()/\n"
                    "        '.local/share/jupyter/runtime/jpserver-*.json'))\n"
                    "      print(json.load(open(max(f,key=os.path.getmtime)))['token'])\n"
                    "then:\n"
                    '    dicos.py auth "<browser URL>" "<token>"'
                )

        config = dict(config)
        config["token"] = token

        # Candidate hosts, most specific first. `jupyter server list` reports the
        # pod-internal address (e.g. jupyterlabcpu-user:8888), which is not
        # reachable from outside the cluster, so a candidate is only adopted if
        # it actually authenticates -- the stored external URL usually wins.
        candidates: list[str] = []
        parsed = re.match(r"(https?://[^/?#]+)", raw)
        if parsed:
            host = parsed.group(1)
            internal = re.search(r"//(0\.0\.0\.0|127\.0\.0\.1|localhost|[^.:/]+)(:|$)", host)
            if not (internal and internal.group(1) not in ("", None) and "." not in internal.group(1)):
                candidates.append(host)
        if config.get("base_url"):
            candidates.append(config["base_url"])

        last_error: Exception | None = None
        for candidate in dict.fromkeys(candidates):
            trial = {**config, "base_url": candidate}
            try:
                Dicos(trial).status()
            except Exception as exc:  # noqa: BLE001 - try the next candidate
                last_error = exc
                continue
            CONFIG_PATH.write_text(json.dumps(trial, indent=2), encoding="utf-8")
            print(f"authenticated against {candidate}"
                  + (" (reused the stored token)" if reused else ""))
            print(f"workdir: {trial['workdir']}")
            return 0
        raise SystemExit(
            f"could not authenticate, nothing saved. Tried: {', '.join(candidates) or '(none)'}\n"
            f"last error: {last_error}"
        )

    client = Dicos(load_config())
    try:
        client.status()
    except requests.HTTPError as exc:
        code = exc.response.status_code if exc.response is not None else "?"
        raise SystemExit(STALE.format(code=code))
    except requests.RequestException as exc:
        raise SystemExit(
            f"cannot reach {client.base}: {exc}\n"
            "The pod may have ended, or its port changed. Relaunch the DiCOSApp "
            "and re-run auth with the new URL."
        )

    if args.cmd == "exec":
        return client.exec(args.command, cwd=args.cwd, timeout=args.timeout)
    if args.cmd == "start":
        return client.start(args.command, args.name, cwd=args.cwd)
    if args.cmd == "jobs":
        return client.jobs()
    if args.cmd == "stop":
        return client.stop(args.name)
    if args.cmd == "logs":
        return client.logs(args.name, tail=args.tail)
    if args.cmd == "setup":
        return client.exec(SETUP_SCRIPT, timeout=1800)
    if args.cmd == "verify":
        return client.exec(VERIFY_SCRIPT, timeout=1800)
    if args.cmd == "info":
        return client.exec(INFO_SCRIPT, timeout=180)
    if args.cmd == "status":
        print(json.dumps(client.status(), indent=2))
    elif args.cmd == "ls":
        for entry in client.ls(args.path):
            size = entry.get("size")
            print(f"{entry['type']:9} {str(size) if size is not None else '':>14}  {entry['name']}")
    elif args.cmd == "put":
        n = client.put(Path(args.local), args.remote, log=print)
        print(f"uploaded {n} bytes -> {client._resolve(args.remote)}")
    elif args.cmd == "get":
        n = client.get(args.remote, Path(args.local))
        print(f"downloaded {n} bytes -> {args.local}")
    elif args.cmd == "mkdir":
        client.mkdir(args.remote)
        print(f"created {client._resolve(args.remote)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
