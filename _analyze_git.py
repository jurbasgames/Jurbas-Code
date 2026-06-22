#!/usr/bin/env python3
"""Helper script to extract git diff info from the repository.

Usage: python _analyze_git.py

Output: writes analysis to _git_analysis.txt
"""
import os
import zlib
import subprocess
import sys

REPO = os.path.dirname(os.path.abspath(__file__))
GIT_DIR = os.path.join(REPO, ".git")

def read_git_object(sha):
    """Read and decompress a git object."""
    path = os.path.join(GIT_DIR, "objects", sha[:2], sha[2:])
    if not os.path.exists(path):
        return None
    with open(path, "rb") as f:
        compressed = f.read()
    return zlib.decompress(compressed)

def parse_commit(raw):
    """Parse a git commit object."""
    lines = raw.decode("utf-8", errors="replace").split("\n")
    info = {}
    msg_start = 0
    for i, line in enumerate(lines):
        if not line:
            msg_start = i + 1
            break
        if " " in line:
            key, value = line.split(" ", 1)
            if key in ("tree", "parent"):
                info.setdefault(key, []).append(value)
            else:
                info[key] = value
    info["message"] = "\n".join(lines[msg_start:]).strip()
    return info

def main():
    output = []
    output.append("=" * 60)
    output.append("GIT ANALYSIS REPORT")
    output.append("=" * 60)

    # 1. Current branch
    head_path = os.path.join(GIT_DIR, "HEAD")
    with open(head_path) as f:
        head = f.read().strip()
    output.append(f"\nHEAD: {head}")

    # 2. Run git commands
    try:
        # Branch list
        result = subprocess.run(
            ["git", "branch", "-a"],
            capture_output=True, text=True, cwd=REPO, timeout=30
        )
        output.append("\n--- BRANCHES ---")
        output.append(result.stdout)

        # Diff between main and PR #3 branch (remote)
        result = subprocess.run(
            ["git", "diff", "--stat", "origin/main...origin/jules-12033590512229655020-a6d9c460"],
            capture_output=True, text=True, cwd=REPO, timeout=30
        )
        output.append("\n--- DIFF STAT (main vs PR#3) ---")
        output.append(result.stdout)
        if result.stderr:
            output.append(f"STDERR: {result.stderr}")

        # Full diff stats
        result = subprocess.run(
            ["git", "diff", "--numstat", "origin/main...origin/jules-12033590512229655020-a6d9c460"],
            capture_output=True, text=True, cwd=REPO, timeout=30
        )
        output.append("\n--- NUMSTAT (main vs PR#3) ---")
        output.append(result.stdout)

        # Files changed
        result = subprocess.run(
            ["git", "diff", "--name-only", "origin/main...origin/jules-12033590512229655020-a6d9c460"],
            capture_output=True, text=True, cwd=REPO, timeout=30
        )
        output.append("\n--- FILES CHANGED (main vs PR#3) ---")
        output.append(result.stdout)

        # Log of PR#3 commits
        result = subprocess.run(
            ["git", "log", "--oneline", "origin/main..origin/jules-12033590512229655020-a6d9c460"],
            capture_output=True, text=True, cwd=REPO, timeout=30
        )
        output.append("\n--- COMMITS ON PR#3 (not in main) ---")
        output.append(result.stdout)

        # Compare with other branches to find overlaps
        for branch in ["origin/fix-pr-3-streaming-2", "origin/git-tools", "origin/split/env-secrets", "origin/split/error-handling"]:
            result = subprocess.run(
                ["git", "cherry", "-v", "origin/main", branch],
                capture_output=True, text=True, cwd=REPO, timeout=30
            )
            output.append(f"\n--- CHERRY commits on {branch} (vs main) ---")
            output.append(result.stdout)

        # Check for duplicate/similar changes
        output.append("\n--- OVERLAP ANALYSIS ---")
        for branch in ["origin/fix-pr-3-streaming-2", "origin/git-tools", "origin/split/env-secrets", "origin/split/error-handling"]:
            result = subprocess.run(
                ["git", "diff", "--stat", "origin/jules-12033590512229655020-a6d9c460..." + branch],
                capture_output=True, text=True, cwd=REPO, timeout=30
            )
            output.append(f"\nDiff between PR#3 and {branch}:")
            output.append(result.stdout.strip() or "(identical or no diff)")

    except Exception as e:
        output.append(f"\nError running git: {e}")

    # Write output
    out_path = os.path.join(REPO, "_git_analysis.txt")
    with open(out_path, "w") as f:
        f.write("\n".join(output))
    print(f"Analysis written to {out_path}")

if __name__ == "__main__":
    main()
