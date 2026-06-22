"""Git object parsing and analysis utilities (works without the git CLI)."""

import os
import subprocess
import sys
import zlib

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(errors="replace")
    except AttributeError:
        pass

from .security import ALLOWED_BASE

GIT_DIR = os.path.join(ALLOWED_BASE, ".git")


# ─── Low-level object readers ───

def _read_git_object(sha: str) -> bytes | None:
    """Read and decompress a loose git object by its SHA-1 hash."""
    path = os.path.join(GIT_DIR, "objects", sha[:2], sha[2:])
    if not os.path.exists(path):
        return None
    with open(path, "rb") as f:
        return zlib.decompress(f.read())


def _parse_commit(raw: bytes) -> dict:
    """Parse a git commit object into a dictionary."""
    data = raw.decode("utf-8", errors="replace")
    lines = data.split("\n")
    info: dict = {}
    msg_start = 0
    for i, line in enumerate(lines):
        if not line:
            msg_start = i + 1
            break
        if " " in line:
            key, value = line.split(" ", 1)
            if key in ("tree", "parent"):
                info.setdefault(key, []).append(value.strip())
            else:
                info[key] = value.strip()
    info["message"] = "\n".join(lines[msg_start:]).strip()
    return info


def _parse_tree(raw: bytes) -> list[dict]:
    """Parse a git tree object into a list of {mode, name, sha} entries."""
    entries = []
    data = raw
    null = data.find(b"\x00")
    data = data[null + 1:]  # skip header
    while data:
        mode_end = data.find(b" ")
        name_end = data.find(b"\x00", mode_end)
        mode = data[:mode_end].decode()
        name = data[mode_end + 1:name_end].decode()
        sha = data[name_end + 1:name_end + 21]
        entries.append({"mode": mode, "name": name, "sha": sha.hex()})
        data = data[name_end + 21:]
    return entries


# ─── High-level analysis ───

def extract_git_info() -> str:
    """Extract git object info without CLI, save to ``_git_objects.txt``.

    Returns the full text written to the file.
    """
    out: list[str] = []

    def log(m: str = "") -> None:
        out.append(m)
        print(m)

    packed: dict[str, str] = {}
    ppath = os.path.join(GIT_DIR, "packed-refs")
    if os.path.exists(ppath):
        with open(ppath) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    parts = line.split(" ", 1)
                    if len(parts) == 2:
                        packed[parts[1]] = parts[0]

    log("=" * 65)
    log("EXTRAÇÃO DE OBJETOS GIT")
    log("=" * 65)

    KEY_REFS = {
        "main":             "refs/remotes/origin/main",
        "PR3":              "refs/remotes/origin/jules-12033590512229655020-a6d9c460",
        "fix-pr3-streaming":"refs/remotes/origin/fix-pr-3-streaming-2-8123061117886389558",
        "git-tools":        "refs/remotes/origin/git-tools",
        "split/env-secrets":"refs/remotes/origin/split/env-secrets",
        "split/error-handling":"refs/remotes/origin/split/error-handling",
        "feat/multi-provider":"refs/remotes/origin/feat/multi-provider-claude-subscription",
        "token-metrics":    "refs/remotes/origin/token-metrics-17768994347185268362",
        "fix-auth":         "refs/remotes/origin/fix-auth-early-fail-loop-17477551473002829533",
        "fix-security":     "refs/remotes/origin/fix-pr-7-security-bugs-16695444652935866273",
        "pr-11":            "refs/remotes/origin/pr-11-5535174162383994733",
        "pr/13":            "refs/remotes/origin/pr/13",
        "jules-3944":       "refs/remotes/origin/jules-3944310241002831044-2c2d1064",
    }

    log("\n📌 REFS:")
    for name, ref in KEY_REFS.items():
        sha = packed.get(ref, "❌")
        log(f"  {name:25s} → {sha}")

    log("\n📋 COMMITS:")
    for name, ref in KEY_REFS.items():
        sha = packed.get(ref, "")
        if not sha:
            continue
        raw = _read_git_object(sha)
        if raw is None:
            log(f"\n  ❌ {name}: obj não encontrado ({sha})")
            continue
        info = _parse_commit(raw)
        tree_sha = info.get("tree", ["?"])[0] if isinstance(info.get("tree"), list) else "?"
        parents = info.get("parent", [])
        parent_str = ",".join(p[:8] for p in parents) if parents else "(root)"
        msg = info.get("message", "").replace("\n", " | ")[:250]
        log(f"\n  📌 {name} ({sha[:8]}) tree={tree_sha[:8]} parent=[{parent_str}]")
        log(f"     {msg}")

    log("\n📂 ÁRVORES:")
    for name, ref in KEY_REFS.items():
        sha = packed.get(ref, "")
        if not sha:
            continue
        raw = _read_git_object(sha)
        if raw is None:
            continue
        info = _parse_commit(raw)
        tree_sha = info.get("tree", [""])[0] if isinstance(info.get("tree"), list) else ""
        if not tree_sha:
            continue
        tree_raw = _read_git_object(tree_sha)
        if tree_raw is None:
            log(f"\n  ❌ {name}: tree faltando ({tree_sha})")
            continue
        entries = _parse_tree(tree_raw)
        log(f"\n  📂 {name} ({tree_sha[:8]}):")
        for e in entries:
            log(f"     {e['mode']} {e['sha'][:8]} {e['name']}")

    log("\n✅ Concluído!")
    rpath = os.path.join(ALLOWED_BASE, "_git_objects.txt")
    with open(rpath, "w", encoding="utf-8") as f:
        f.write("\n".join(out))
    print(f"\n📝 Salvo em: {rpath}")
    return "\n".join(out)


def analyze_pr() -> str:
    """Analyze PR #3 using git CLI, save to ``_git_analysis.txt``.

    Returns the full text written to the file.
    """
    lines: list[str] = []

    def log(msg: str = "") -> None:
        lines.append(msg)
        print(msg)

    log("=" * 65)
    log("🔍 ANALISANDO PR #3")
    log("=" * 65)

    PR = "origin/jules-12033590512229655020-a6d9c460"
    MAIN = "origin/main"

    for title, cmd in [
        ("Commits no PR", f"git log --oneline {MAIN}..{PR}"),
        ("Diff Stat", f"git diff --stat {MAIN}...{PR}"),
        ("Arquivos", f"git diff --name-only {MAIN}...{PR}"),
        ("Numstat", f"git diff --numstat {MAIN}...{PR}"),
    ]:
        log(f"\n{title}\n" + "-" * 40)
        r = subprocess.run(
            cmd, shell=True, capture_output=True, text=True,
            cwd=ALLOWED_BASE, timeout=30,
        )
        log((r.stdout or "").strip() or "(vazio)")

    log("\n" + "=" * 65)
    log("COMPARAÇÃO COM BRANCHES")
    log("=" * 65)

    for name, branch in [
        ("fix-pr-3-streaming", "origin/fix-pr-3-streaming-2-8123061117886389558"),
        ("git-tools",           "origin/git-tools"),
        ("split/env-secrets",   "origin/split/env-secrets"),
        ("split/error-handling","origin/split/error-handling"),
        ("feat/multi-provider", "origin/feat/multi-provider-claude-subscription"),
        ("token-metrics",       "origin/token-metrics-17768994347185268362"),
    ]:
        log(f"\n📎 {name}")
        log("-" * 40)
        r = subprocess.run(
            f"git log --oneline {MAIN}..{branch}",
            shell=True, capture_output=True, text=True,
            cwd=ALLOWED_BASE, timeout=30,
        )
        log(f"Commits: {(r.stdout or '').strip() or '(nenhum)'}")
        r = subprocess.run(
            f"git diff --stat {PR}...{branch}",
            shell=True, capture_output=True, text=True,
            cwd=ALLOWED_BASE, timeout=30,
        )
        diff = (r.stdout or "").strip()
        log(f"Diff vs PR#3: {diff or '(idêntico)'}")
        r = subprocess.run(
            f"git cherry -v {PR} {branch}",
            shell=True, capture_output=True, text=True,
            cwd=ALLOWED_BASE, timeout=30,
        )
        cherry = (r.stdout or "").strip()
        if cherry:
            exc = [l for l in cherry.split("\n") if l.startswith("+")]
            inside = [l for l in cherry.split("\n") if l.startswith("-")]
            if exc:
                log(f"⚠️  Exclusivos ({len(exc)}):")
                for c in exc:
                    log(f"     {c}")
            if inside:
                log(f"✅ Já no PR#3 ({len(inside)}):")
                for c in inside:
                    log(f"     {c}")

    log("\n✅ Concluído!")
    rpath = os.path.join(ALLOWED_BASE, "_git_analysis.txt")
    with open(rpath, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    log(f"\n📝 Salvo em: {rpath}")
    return "\n".join(lines)
