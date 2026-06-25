import os
import shutil
import tempfile
import pytest

from jurbas_code.skills import skills_load, skills_list, skills_get, _parse_frontmatter, _SKILLS_REGISTRY

@pytest.fixture
def temp_skills_dir():
    dir_path = tempfile.mkdtemp()
    yield dir_path
    shutil.rmtree(dir_path)

def test_parse_frontmatter():
    content = """---
name: my_skill
description: does things
version: 1.0.0
---
# Body
Hello World
"""
    metadata, body = _parse_frontmatter(content)
    assert metadata["name"] == "my_skill"
    assert metadata["description"] == "does things"
    assert metadata["version"] == "1.0.0"
    assert body.strip() == "# Body\nHello World"

def test_parse_frontmatter_no_frontmatter():
    content = "# Just a body\nNo metadata"
    metadata, body = _parse_frontmatter(content)
    assert metadata == {}
    assert body == content

def test_skills_load_missing_dir():
    # Clear registry first
    _SKILLS_REGISTRY.clear()
    # Loading a non-existent dir should fail gracefully
    skills_load("/path/that/does/not/exist/ever")
    assert len(_SKILLS_REGISTRY) == 0

def test_skills_load_and_retrieve(temp_skills_dir):
    # Create a couple of skill files
    skill1_path = os.path.join(temp_skills_dir, "skill1.md")
    with open(skill1_path, "w", encoding="utf-8") as f:
        f.write("---\nname: my_test_skill\ndescription: Test description\n---\nBody1")

    skill2_path = os.path.join(temp_skills_dir, "skill2.md")
    with open(skill2_path, "w", encoding="utf-8") as f:
        f.write("No frontmatter here, but valid MD")

    # Load skills
    skills_load(temp_skills_dir)

    # We should have 2 skills
    assert len(_SKILLS_REGISTRY) == 2
    assert "my_test_skill" in _SKILLS_REGISTRY
    assert "skill2" in _SKILLS_REGISTRY # Filename used as fallback name

    # Test list
    list_output = skills_list()
    assert "Available skills:" in list_output
    assert "- my_test_skill: Test description" in list_output
    assert "- skill2: No description provided." in list_output

    # Test get
    content1 = skills_get("my_test_skill")
    assert "---\nname: my_test_skill\ndescription: Test description\n---\nBody1" in content1

    content2 = skills_get("skill2")
    assert "No frontmatter here" in content2

    # Test get missing
    assert "Error: skill 'nonexistent' not found." in skills_get("nonexistent")

def test_skills_list_empty():
    _SKILLS_REGISTRY.clear()
    assert skills_list() == "No skills loaded or available."
