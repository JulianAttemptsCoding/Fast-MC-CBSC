#!/usr/bin/env python3
"""Programmatic access to a DiCOS (ASGC) JupyterLab instance.

DiCOS exposes no SSH path we can automate (ASGC mandates Google-Authenticator
OTP on its login services), but the DiCOSApp JupyterLab is directly reachable
and its token authenticates the REST and kernel-websocket APIs. This client
wraps those into a small CLI so any agent or shell can drive the remote host:

    python scripts/dicos.py info
    python scripts/dicos.py exec "nvidia-smi"
    python scripts/dicos.py exec "python -c 'import torch; print(torch.__version__)'"
    python scripts/dicos.py ls .
    python scripts/dicos.py put local.py remote/path.py
    python scripts/dicos.py get remote/path.json local.json

Credentials live in ~/.dicos/config.json (outside the repository), holding
base_url, token, workdir, and readonly_data.

Write scope is enforced client-side: `put` refuses any destination outside the
configured workdir, and `exec` refuses commands that redirect into, or mutate,
the declared read-only dataset paths. These guards are a safety net for honest
mistakes, not a security boundary -- the token itself carries whatever
permissions the account has.
"""

from __future__ import annotations

import argparse
import base64
import json
import posixpath
import re
import sys
import time
import uuid
from pathlib import Path

import requests

CONFIG_PATH = Path.home() / ".dicos" / "config.json"


def load_config() -> dict:
    if not CONFIG_PATH.exists():
        raise SystemExit(f"no credentials at {CONFIG_PATH}")
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
        self.readonly = [p.rstrip("/") for p in config.get("readonly_data", [])]
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

    def put(self, local: Path, remote: str) -> int:
        target = self._resolve(remote)
        self._assert_writable(target)
        data = local.read_bytes()
        body = {
            "type": "file", "format": "base64",
            "content": base64.b64encode(data).decode("ascii"),
        }
        r = self.session.put(
            f"{self.base}/api/contents/{self._contents(target)}",
            json=body, timeout=300,
        )
        r.raise_for_status()
        return len(data)

    def mkdir(self, remote: str) -> None:
        target = self._resolve(remote)
        self._assert_writable(target)
        r = self.session.put(
            f"{self.base}/api/contents/{self._contents(target)}",
            json={"type": "directory"}, timeout=60,
        )
        if r.status_code not in (200, 201):
            r.raise_for_status()

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

    def _assert_command_safe(self, command: str) -> None:
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

    # ---------------------------------------------------------- execution
    def exec(self, command: str, cwd: str | None = None, timeout: int = 300) -> int:
        """Run a shell command in a transient kernel; stream stdout/stderr."""
        import websocket  # imported lazily so contents-only use needs no ws dep

        self._assert_command_safe(command)
        workdir = self._resolve(cwd) if cwd else self.workdir

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
            ws = websocket.create_connection(ws_url, timeout=30)
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
bad(){ printf '  [FAIL] %s\n' "$1"; }

echo "1. workdir"
mkdir -p _setup prep && ok "$(pwd)"

echo "2. repository"
if [ -d repo/.git ]; then
  git -C repo pull --ff-only >/dev/null 2>&1 && ok "repo updated" || ok "repo present (pull skipped)"
else
  fix "cloning"; git clone --depth 1 "$REPO_URL" repo >/dev/null 2>&1 \
    && ok "cloned" || bad "clone failed"
fi

echo "3. base interpreter"
BASE=""
for cand in /opt/miniconda3/envs/asgc/bin/python /opt/conda/bin/python3 /usr/bin/python3; do
  [ -x "$cand" ] || continue
  if "$cand" -c "import torch" >/dev/null 2>&1; then BASE="$cand"; break; fi
  [ -n "$BASE" ] || BASE="$cand"
done
[ -n "$BASE" ] && ok "base $BASE ($($BASE -V 2>&1))" || bad "no interpreter found"

echo "4. venv"
NEED=0
if [ -x .venv/bin/python ]; then
  .venv/bin/python -c "import torch,numpy,uproot,cbsc_zdc" >/dev/null 2>&1 \
    && ok "venv healthy" || { NEED=1; fix "venv present but broken -> rebuilding"; }
else
  NEED=1; fix "venv missing -> creating"
fi
if [ "$NEED" = 1 ]; then
  rm -rf .venv
  "$BASE" -m venv --system-site-packages .venv >/dev/null 2>&1
  .venv/bin/pip install -q --upgrade pip >/dev/null 2>&1
  .venv/bin/pip install -q uproot awkward >/dev/null 2>&1
  .venv/bin/pip install -q -e repo >/dev/null 2>&1
  .venv/bin/python -c "import torch,numpy,uproot,cbsc_zdc" >/dev/null 2>&1 \
    && ok "venv built" || bad "venv build failed"
fi

echo "5. frozen geometry"
if [ -f prep/geometry_frozen/geometry.npz ]; then
  .venv/bin/python - <<PY
import json,sys,numpy as np
sys.path.insert(0,"repo/src")
from cbsc_zdc.data.geometry import geometry_hash
got=geometry_hash(dict(np.load("prep/geometry_frozen/geometry.npz")))
print(("  [ok]   geometry hash verified" if got=="$GEOM_HASH"
       else "  [FAIL] geometry hash MISMATCH "+got))
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
echo
echo "setup complete"
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
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("exec", help="run a shell command remotely")
    p.add_argument("command")
    p.add_argument("--cwd")
    p.add_argument("--timeout", type=int, default=300)

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
    sub.add_parser("info", help="probe the remote environment")
    sub.add_parser("status", help="server status")

    args = parser.parse_args()

    if args.cmd == "auth":
        raw = args.url_or_token.strip()
        explicit = (args.token or "").strip()
        found = re.search(r"[?&]token=([0-9a-fA-F]{16,})", raw)
        token = explicit or (found.group(1) if found else raw)
        if not re.fullmatch(r"[0-9a-fA-F]{16,}", token):
            raise SystemExit(
                "no token found.\n"
                "Jupyter removes ?token=... from the address bar after login, so a URL "
                "copied later will not contain one. Recover it on the pod with:\n"
                "    jupyter server list\n"
                "then pass the browser URL and that token together:\n"
                '    dicos.py auth "<browser URL>" "<token>"'
            )

        config = load_config()
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
            print(f"authenticated against {candidate}")
            print(f"workdir: {trial['workdir']}")
            return 0
        raise SystemExit(
            f"could not authenticate, nothing saved. Tried: {', '.join(candidates) or '(none)'}\n"
            f"last error: {last_error}"
        )

    client = Dicos(load_config())

    if args.cmd == "exec":
        return client.exec(args.command, cwd=args.cwd, timeout=args.timeout)
    if args.cmd == "setup":
        return client.exec(SETUP_SCRIPT, timeout=1800)
    if args.cmd == "info":
        return client.exec(INFO_SCRIPT, timeout=180)
    if args.cmd == "status":
        print(json.dumps(client.status(), indent=2))
    elif args.cmd == "ls":
        for entry in client.ls(args.path):
            size = entry.get("size")
            print(f"{entry['type']:9} {str(size) if size is not None else '':>14}  {entry['name']}")
    elif args.cmd == "put":
        n = client.put(Path(args.local), args.remote)
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
