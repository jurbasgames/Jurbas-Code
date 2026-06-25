"""Local skills loading and retrieval module."""

import os
import glob

# The registry to hold loaded skills
_SKILLS_REGISTRY = {}

def _parse_frontmatter(content: str) -> tuple[dict, str]:
    """Parse a simple YAML-like frontmatter.

    Returns a tuple of (metadata_dict, body_string).
    """
    lines = content.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, content

    metadata = {}
    body_start_idx = 1

    for i in range(1, len(lines)):
        line = lines[i].strip()
        if line == "---":
            body_start_idx = i + 1
            break

        if ":" in line:
            key, val = line.split(":", 1)
            metadata[key.strip()] = val.strip()

    body = "\n".join(lines[body_start_idx:])
    return metadata, body

def skills_load(skills_dir: str = "~/.hermes/skills/") -> None:
    """Scan and load all .md files in the skills directory."""
    global _SKILLS_REGISTRY
    _SKILLS_REGISTRY.clear()

    expanded_dir = os.path.expanduser(skills_dir)
    if not os.path.isdir(expanded_dir):
        return

    search_pattern = os.path.join(expanded_dir, "*.md")
    for file_path in glob.glob(search_pattern):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            metadata, body = _parse_frontmatter(content)

            # The name is either from frontmatter or the filename (without extension)
            name = metadata.get("name", os.path.splitext(os.path.basename(file_path))[0])
            description = metadata.get("description", "No description provided.")

            _SKILLS_REGISTRY[name] = {
                "name": name,
                "description": description,
                "content": content,
                "metadata": metadata
            }
        except Exception:
            # Silently ignore files that can't be read, per robust handling
            continue

def skills_list() -> str:
    """Return available skill names and descriptions."""
    if not _SKILLS_REGISTRY:
        return "No skills loaded or available."

    lines = ["Available skills:"]
    for name, skill in sorted(_SKILLS_REGISTRY.items()):
        lines.append(f"- {name}: {skill['description']}")
    return "\n".join(lines)

def skills_get(name: str) -> str:
    """Return the full content of a specific skill."""
    if not isinstance(name, str):
        return "Error: skill name must be a string."

    skill = _SKILLS_REGISTRY.get(name)
    if not skill:
        return f"Error: skill '{name}' not found."

    return skill["content"]
