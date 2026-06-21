#!/usr/bin/env python3
"""Extract git objects directly (without git CLI) and write analysis to _git_objects.txt"""
import os
import zlib
import struct

GIT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".git")
OUTPUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_git_objects.txt")

def read_git_object(sha):
    path = os.path.join(GIT_DIR, "objects", sha[:2], sha[2:])
    if not os.path.exists(path):
        return None
    with open(path, "rb") as f:
        compressed = f.read()
    return zlib.decompress(compressed)

def parse_commit(raw):
    data = raw.decode("utf-8", errors="replace")
    lines = data.split("\n")
    info = {"type": "commit"}
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

def parse_tree(raw):
    info = {"type": "tree", "entries": []}
    data = raw
    # Skip "tree <size>\0"
    null = data.find(b"\x00")
    data = data[null+1:]
    while data:
        mode_end = data.find(b" ")
        name_end = data.find(b"\x00", mode_end)
        mode = data[:mode_end].decode()
        name = data[mode_end+1:name_end].decode()
        sha = data[name_end+1:name_end+21]
        hex_sha = sha.hex()
        info["entries"].append({"mode": mode, "name": name, "sha": hex_sha})
        data = data[name_end+21:]
    return info

def resolve_ref(ref_path):
    path = os.path.join(GIT_DIR, ref_path)
    if os.path.exists(path):
        with open(path) as f:
            content = f.read().strip()
        if content.startswith("ref: "):
            return resolve_ref(content[5:])
        return content
    return None

def main():
    lines = []
    def log(m):
        lines.append(m)
        print(m)

    log("=" * 65)
    log("EXTRAÇÃO DE OBJETOS GIT (SEM CLI)")
    log("=" * 65)

    # Read packed-refs
    packed_refs = {}
    with open(os.path.join(GIT_DIR, "packed-refs")) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                parts = line.split(" ", 1)
                if len(parts) == 2:
                    packed_refs[parts[1]] = parts[0]

    log("\n📌 REFS DE INTERESSE:")
    interesting = [
        "refs/heads/main",
        "refs/heads/jules-12033590512229655020-a6d9c460",
        "refs/remotes/origin/main",
        "refs/remotes/origin/jules-12033590512229655020-a6d9c460",
        "refs/remotes/origin/fix-pr-3-streaming-2-8123061117886389558",
        "refs/remotes/origin/git-tools",
        "refs/remotes/origin/split/env-secrets",
        "refs/remotes/origin/split/error-handling",
        "refs/remotes/origin/fix-pr-7-security-bugs-16695444652935866273",
        "refs/remotes/origin/token-metrics-17768994347185268362",
        "refs/remotes/origin/pr-11-5535174162383994733",
        "refs/remotes/origin/pr/13",
    ]
    for ref in interesting:
        sha = packed_refs.get(ref, "NÃO ENCONTRADO")
        log(f"  {ref} → {sha}")

    # Read commits from packed-refs
    PR_REMOTE = packed_refs.get("refs/remotes/origin/jules-12033590512229655020-a6d9c460", "")
    MAIN_REMOTE = packed_refs.get("refs/remotes/origin/main", "")
    FIX_STREAM = packed_refs.get("refs/remotes/origin/fix-pr-3-streaming-2-8123061117886389558", "")
    GIT_TOOLS = packed_refs.get("refs/remotes/origin/git-tools", "")
    SPLIT_ENV = packed_refs.get("refs/remotes/origin/split/env-secrets", "")
    SPLIT_ERR = packed_refs.get("refs/remotes/origin/split/error-handling", "")
    FEAT_MULTI = packed_refs.get("refs/remotes/origin/feat/multi-provider-claude-subscription", "")
    TOKEN_METRICS = packed_refs.get("refs/remotes/origin/token-metrics-17768994347185268362", "")
    PR113 = packed_refs.get("refs/remotes/origin/pr-11-5535174162383994733", "")
    PR13 = packed_refs.get("refs/remotes/origin/pr/13", "")
    FIX_AUTH = packed_refs.get("refs/remotes/origin/fix-auth-early-fail-loop-17477551473002829533", "")
    FIX_SECURITY = packed_refs.get("refs/remotes/origin/fix-pr-7-security-bugs-16695444652935866273", "")

    log("\n📋 PARSING COMMIT OBJECTS...")
    for label, sha in [
        ("PR #3 (remote)", PR_REMOTE),
        ("main (remote)", MAIN_REMOTE),
        ("fix-pr-3-streaming", FIX_STREAM),
        ("git-tools", GIT_TOOLS),
        ("split/env-secrets", SPLIT_ENV),
        ("split/error-handling", SPLIT_ERR),
        ("feat/multi-provider", FEAT_MULTI),
        ("token-metrics", TOKEN_METRICS),
        ("pr-11", PR113),
        ("pr/13", PR13),
        ("fix-auth", FIX_AUTH),
        ("fix-security", FIX_SECURITY),
    ]:
        if not sha:
            log(f"\n  ❌ {label}: SHA vazio")
            continue
        raw = read_git_object(sha)
        if raw is None:
            log(f"\n  ❌ {label}: objeto não encontrado localmente ({sha})")
            continue
        info = parse_commit(raw)
        log(f"\n  📌 {label} ({sha[:8]}):")
        log(f"     Tree: {info.get('tree', ['?'])[0][:12] if isinstance(info.get('tree'), list) else '?'}")
        parents = info.get("parent", [])
        if parents:
            log(f"     Parent(s): {[p[:8] for p in parents]}")
        msg = info.get("message", "")
        msg_preview = msg[:200].replace("\n", " | ")
        log(f"     Message: {msg_preview}")

    # Parse tree objects to see what files are tracked
    log("\n\n📂 PARSING TREE OBJECTS (files in each commit)...")
    for label, sha in [
        ("PR #3", PR_REMOTE),
        ("main", MAIN_REMOTE),
        ("fix-pr-3-streaming", FIX_STREAM),
        ("split/env-secrets", SPLIT_ENV),
        ("split/error-handling", SPLIT_ERR),
    ]:
        if not sha:
            continue
        raw = read_git_object(sha)
        if raw is None:
            continue
        info = parse_commit(raw)
        tree_sha = info.get("tree", [""])[0] if isinstance(info.get("tree"), list) else ""
        if not tree_sha:
            continue
        tree_raw = read_git_object(tree_sha)
        if tree_raw is None:
            log(f"\n  ❌ {label}: tree object não encontrado ({tree_sha})")
            continue
        tree = parse_tree(tree_raw)
        log(f"\n  📂 {label} tree ({tree_sha[:8]}):")
        for entry in tree["entries"]:
            log(f"     {entry['mode']} {entry['sha'][:8]} {entry['name']}")

    log("\n\n✅ Extração concluída!")
    
    with open(OUTPUT, "w") as f:
        f.write("\n".join(lines))
    print(f"\n📝 Salvo em: {OUTPUT}")

if __name__ == "__main__":
    main()
