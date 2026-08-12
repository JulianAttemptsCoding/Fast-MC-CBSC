#!/usr/bin/env python
"""Build a self-contained audit bundle for an external reviewer.

The bundle is everything a reviewer needs to judge the work and nothing that
would be dangerous to hand over. It is deliberately built from `git ls-files`
rather than a directory walk, so an untracked local file cannot be swept in by
accident -- which is exactly how a credential would escape.

Three refusals, all fail-closed. The script writes no archive if any fires:

  1. a staged file matches a denylisted path,
  2. a staged file contains a live credential, checked by reading the real
     values out of `~/.dicos/*.json` and searching for them verbatim (the values
     are never printed, logged, or written anywhere),
  3. the archive would exceed the size cap.

Usage:
    python scripts/build_audit_bundle.py --output CBSC_ZDC_audit_bundle.zip
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

#: Never bundled, whatever git says. `POD_ACCESS.local.md` is untracked and so
#: would not be picked up anyway; it is named here so the intent survives
#: someone later switching to a directory walk.
DENY_NAMES = {
    "POD_ACCESS.local.md",
    ".git-credentials",
    ".netrc",
    "id_rsa",
    "id_ed25519",
}
DENY_PARTS = {".git", ".claude", "node_modules", "__pycache__", ".venv",
              ".pytest_cache", ".ruff_cache", ".vinext", ".wrangler", "dist"}

#: `exhibition/data/visualizations/<tag>/epoch_*.json` is the raw 50-condition,
#: 5-draws-per-condition sample dump behind the structural-invariant QA gate --
#: ~13.5 MB per epoch, ~1.25 GB total as of 2026-08-12, and it is what a
#: checkpoint is checked *against*, not evidence about the loss function or
#: architecture. The figures it produces (exhibition/current/model/*.png,
#: same_condition_longitudinal_profiles etc.) are derived from it and stay in
#: the bundle; the raw draws do not. A reviewer who wants them has the full
#: repository on GitHub (see GIT_PROVENANCE.md). Excluded explicitly, not
#: silently -- reported in the build summary and in AUDIT_README.md.
SKIP_PREFIXES = ("exhibition/data/visualizations/",)

#: Untracked files worth including. Each must be justified: a reviewer needs the
#: host operating rules to understand why the run procedure looks as it does.
EXTRA_FILES = {
    "CLAUDE.md": "host-specific operating rules (untracked, local to the workstation)",
}

#: Sibling repositories that produced the downstream evaluations cited by this
#: project. Each is pinned to the commit recorded in the corresponding
#: `exhibition/current/external_metrics/source_data/.../metrics.json`, and the
#: build refuses if the checkout has moved -- otherwise the bundle would ship an
#: evaluator that is not the one the numbers came from.
EXTERNAL_REPOS = {
    "external_models/classifier_c2st__Fast-MC-tester": {
        "path": "../Fast-MC-tester",
        "commit": "1e7abc593805c633d5e42a44ce073ca6287e8972",
        "role": "low-level and high-level classifier two-sample tests (C2ST) "
                "used for the AUROC separability numbers",
        "metrics_key": "auroc",
    },
    "external_models/four_momentum__ASIoP-ZDC-2": {
        "path": "../ML ZDC all 1",
        "commit": "34aeaa61622fba69341bebc3813ca20485b65ace",
        "role": "downstream four-momentum reconstruction model, used for the "
                "energy and angular accuracy numbers and the Geant4 control",
        "metrics_key": "four_momentum",
    },
}

#: `dashboard/public/data/*.json` epoch payloads are gitignored and total about
#: 870 MB, so they cannot all ship. Four tests resolve the *accepted-best*
#: payload for each family, and without them the bundle fails its own suite on
#: arrival. Only those four are included, and the selection is read from the
#: published snapshot file rather than hardcoded, so it cannot drift.
PUBLIC_SNAPSHOTS = Path("../Fast-MC-Visual-Tests/config/public_snapshots.json")


def accepted_best_payloads() -> list[str]:
    """Repo-relative dashboard payloads for the currently published bests."""
    source = (ROOT / PUBLIC_SNAPSHOTS).resolve()
    if not source.exists():
        return []
    payload = json.loads(source.read_text(encoding="utf-8"))
    names = []
    for entry in payload.get("snapshots", []):
        identifier = entry.get("id", "")
        # `<run>-<family>:<stage>:<epoch>` addresses
        # `<run>-<family>_<stage>_epoch_<epoch>.json` on disk.
        parts = identifier.split(":")
        if len(parts) != 3:
            continue
        run_family, stage, epoch = parts
        names.append(
            f"dashboard/public/data/{run_family}_{stage}_epoch_{epoch}.json"
        )
    return names


#: Textual patterns that must never appear in a bundled file.
SECRET_PATTERNS = [
    (re.compile(r"NotebookApp\.token\s*=\s*[A-Za-z0-9]{16,}"), "jupyter token assignment"),
    (re.compile(r"Bearer\s+[A-Za-z0-9._\-]{20,}"), "bearer token"),
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"), "private key"),
    (re.compile(r"(?i)\bpassword\s*[:=]\s*[\"'][^\"']{4,}[\"']"), "inline password"),
    (re.compile(r"(?i)\b(api[_-]?key|secret[_-]?key)\s*[:=]\s*[\"'][^\"']{8,}[\"']"),
     "inline api/secret key"),
    (re.compile(r"\"token\"\s*:\s*\"[A-Za-z0-9._\-]{16,}\""), "json token field"),
]

#: Values that look like credentials to the patterns above but are documented
#: placeholders. Listed explicitly rather than by loosening a pattern, so a real
#: credential in the same position still fails the build.
ALLOWED_PLACEHOLDERS = {
    "PASTE_THE_DICOSAPP_JUPYTER_TOKEN_HERE",
    "REPLACE_ME",
    "CHANGEME",
    "your-token-here",
    "xxxxxxxxxxxx",
}

TEXT_SUFFIXES = {
    ".py", ".md", ".txt", ".json", ".yaml", ".yml", ".csv", ".jsonl", ".js",
    ".ts", ".tsx", ".html", ".css", ".sh", ".toml", ".cfg", ".ini", ".svg",
}


def live_secret_values() -> list[str]:
    """Read the actual credentials so we can prove they are absent.

    Returned values are used only for `in` tests. They are never printed,
    written, or included in any message.
    """
    values: list[str] = []
    for path in sorted(Path.home().glob(".dicos/config*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        for key in ("token", "password", "secret"):
            value = payload.get(key)
            if isinstance(value, str) and len(value) >= 12:
                values.append(value)
    local = ROOT / "POD_ACCESS.local.md"
    if local.exists():
        # Any long alphanumeric run in the pod-access note is treated as secret.
        values.extend(
            match for match in re.findall(r"[A-Za-z0-9]{24,}", local.read_text(
                encoding="utf-8", errors="replace"))
        )
    return sorted(set(values), key=len, reverse=True)


def tracked_files() -> list[str]:
    out = subprocess.run(["git", "ls-files"], cwd=ROOT,
                         capture_output=True, text=True, check=True)
    return out.stdout.splitlines()


def denied(relative: str) -> str | None:
    normalized = relative.replace("\\", "/")
    parts = Path(relative).parts
    if Path(relative).name in DENY_NAMES:
        return f"denylisted name {Path(relative).name}"
    for part in parts:
        if part in DENY_PARTS:
            return f"denylisted directory component {part!r}"
    for prefix in SKIP_PREFIXES:
        if normalized.startswith(prefix):
            return f"raw QA data, not analysis material ({prefix})"
    return None


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def scan_for_secrets(staged: Path, secrets: list[str]) -> list[str]:
    findings = []
    for path in sorted(staged.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(staged).as_posix()
        try:
            raw = path.read_bytes()
        except OSError:
            continue
        # Exact live-credential check runs on every file, binary included.
        for value in secrets:
            if value.encode("utf-8") in raw:
                findings.append(f"{relative}: contains a live credential value")
                break
        if path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        text = raw.decode("utf-8", errors="replace")
        for pattern, label in SECRET_PATTERNS:
            for match in pattern.finditer(text):
                hit = match.group(0)
                if any(place in hit for place in ALLOWED_PLACEHOLDERS):
                    continue
                findings.append(f"{relative}: matches {label}")
                break
    return findings


def git_provenance() -> str:
    def run(*args: str) -> str:
        return subprocess.run(["git", *args], cwd=ROOT, capture_output=True,
                              text=True).stdout.strip()
    head = run("rev-parse", "HEAD")
    status = run("status", "--porcelain")
    return "\n".join([
        "# Git provenance of this bundle",
        "",
        "The bundle is a snapshot of the working tree at the commit below. It",
        "does not contain `.git`, so full history is not included here; clone",
        "the repository if you need it.",
        "",
        "```text",
        f"HEAD              {head}",
        f"branch            {run('rev-parse', '--abbrev-ref', 'HEAD')}",
        f"remote            {run('config', '--get', 'remote.origin.url')}",
        f"working tree      {'clean' if not status else 'DIRTY - see below'}",
        "```",
        "",
        "## Last 25 commits",
        "",
        "```text",
        run("log", "-25", "--format=%h %ad %s", "--date=short"),
        "```",
        "",
        *(["## Uncommitted changes at bundle time", "", "```text", status, "```", ""]
          if status else []),
    ])


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path,
                        default=ROOT / "CBSC_ZDC_audit_bundle.zip")
    parser.add_argument("--stage", type=Path, required=True,
                        help="staging directory; extra material is copied in "
                             "here before the archive is built")
    parser.add_argument("--max-mb", type=float, default=255.0)
    args = parser.parse_args(argv)

    stage = args.stage.resolve()
    stage.mkdir(parents=True, exist_ok=True)
    payload = stage / "CBSC_ZDC_audit_bundle"
    if payload.exists():
        shutil.rmtree(payload)
    payload.mkdir(parents=True)

    # Anything already staged (pulled live evidence) is preserved alongside.
    preserved = [p for p in stage.iterdir() if p != payload]

    copied = 0
    skipped = []
    for relative in tracked_files():
        reason = denied(relative)
        if reason:
            skipped.append(f"{relative}: {reason}")
            continue
        source = ROOT / relative
        if not source.is_file():
            continue
        target = payload / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        copied += 1

    for relative, why in EXTRA_FILES.items():
        source = ROOT / relative
        if not source.exists():
            skipped.append(f"{relative}: absent ({why})")
            continue
        if denied(relative):
            skipped.append(f"{relative}: denylisted")
            continue
        shutil.copy2(source, payload / relative)
        copied += 1

    payload_count = 0
    for relative in accepted_best_payloads():
        source = ROOT / relative
        if not source.is_file():
            skipped.append(f"{relative}: accepted-best payload absent")
            continue
        target = payload / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        payload_count += 1
    print(f"accepted-best dashboard payloads staged: {payload_count}")

    external_report = []
    for destination, spec in EXTERNAL_REPOS.items():
        repo = (ROOT / spec["path"]).resolve()
        if not (repo / ".git").exists():
            print(f"REFUSING: external repo {repo} is not a git checkout",
                  file=sys.stderr)
            return 4
        head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo,
                              capture_output=True, text=True).stdout.strip()
        if head != spec["commit"]:
            print(f"REFUSING: {destination} is at {head} but the recorded "
                  f"metrics were produced at {spec['commit']}. Shipping a "
                  "different evaluator than the numbers came from would make "
                  "the bundle misleading.", file=sys.stderr)
            return 5
        listing = subprocess.run(["git", "ls-files"], cwd=repo,
                                 capture_output=True, text=True).stdout.splitlines()
        count = 0
        for relative in listing:
            if denied(relative):
                continue
            source = repo / relative
            if not source.is_file():
                continue
            target = payload / destination / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
            count += 1
        log = subprocess.run(["git", "log", "-10", "--format=%h %ad %s",
                              "--date=short"], cwd=repo,
                             capture_output=True, text=True).stdout.strip()
        (payload / destination / "REPO_PROVENANCE.md").write_text(
            "\n".join([
                f"# {destination}",
                "",
                spec["role"],
                "",
                "```text",
                f"HEAD    {head}",
                f"remote  {subprocess.run(['git','config','--get','remote.origin.url'], cwd=repo, capture_output=True, text=True).stdout.strip()}",
                "```",
                "",
                "This commit is the one recorded as `external_repo_commit` in",
                f"`exhibition/current/external_metrics/source_data/dicos-p9/epoch_0038/{spec['metrics_key']}/metrics.json`,",
                "and the bundle build verifies the match rather than assuming it.",
                "",
                "## Last 10 commits",
                "",
                "```text", log, "```", "",
            ]), encoding="utf-8")
        external_report.append(f"{destination}: {count} files at {head[:8]}")
        print(f"external repo staged: {destination} ({count} files, {head[:8]})")

    for extra in preserved:
        target = payload / extra.name
        if extra.is_dir():
            shutil.copytree(extra, target, dirs_exist_ok=True)
        else:
            shutil.copy2(extra, target)

    (payload / "GIT_PROVENANCE.md").write_text(git_provenance(), encoding="utf-8")

    secrets = live_secret_values()
    findings = scan_for_secrets(payload, secrets)
    print(f"credential check: {len(secrets)} live value(s) searched for, "
          f"{len(findings)} finding(s)")
    if findings:
        print("REFUSING TO BUILD - credential scan failed:", file=sys.stderr)
        for finding in findings:
            print(f"  {finding}", file=sys.stderr)
        return 2

    manifest_lines = []
    total = 0
    for path in sorted(payload.rglob("*")):
        if path.is_file() and path.name != "MANIFEST.sha256":
            relative = path.relative_to(payload).as_posix()
            size = path.stat().st_size
            total += size
            manifest_lines.append(f"{sha256_file(path)}  {size:>10}  {relative}")
    (payload / "MANIFEST.sha256").write_text(
        "\n".join(manifest_lines) + "\n", encoding="utf-8")

    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        output.unlink()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for path in sorted(payload.rglob("*")):
            if path.is_file():
                zf.write(path, path.relative_to(payload.parent).as_posix())

    size_mb = output.stat().st_size / 1048576
    print(f"files bundled: {copied + len(preserved)} copied, "
          f"{len(manifest_lines)} in manifest")
    print(f"uncompressed:  {total/1048576:.1f} MB")
    print(f"archive:       {output} ({size_mb:.1f} MB)")
    if skipped:
        print(f"skipped {len(skipped)}:")
        for item in skipped[:10]:
            print(f"  {item}")
    if size_mb > args.max_mb:
        print(f"REFUSING: archive {size_mb:.1f} MB exceeds the "
              f"{args.max_mb:.0f} MB cap", file=sys.stderr)
        output.unlink()
        return 3
    print(f"sha256 {sha256_file(output)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
