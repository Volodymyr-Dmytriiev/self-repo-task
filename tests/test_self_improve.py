"""
Tests for self-improve.py

Smoke-tests the RepositoryAnalyzer logic without hitting real APIs.
Uses tempfile.mkdtemp() to avoid NTFS mount issues with pytest tmp_path.
Run with:  pytest tests/ -v
"""

import importlib.util
import os
import shutil
import sys
import tempfile
import types
from pathlib import Path

import pytest

# ──────────────────────────────────────────────────────────────────────────────
# Import self-improve.py via importlib (hyphen in filename)
# ──────────────────────────────────────────────────────────────────────────────
_ROOT = Path(__file__).parent.parent

_spec = importlib.util.spec_from_file_location(
    "self_improve",
    _ROOT / "self-improve.py",
)
_mod = importlib.util.module_from_spec(_spec)

for _name in ("anthropic", "requests"):
    if _name not in sys.modules:
        sys.modules[_name] = types.ModuleType(_name)

_spec.loader.exec_module(_mod)
RepositoryAnalyzer = _mod.RepositoryAnalyzer


# ──────────────────────────────────────────────────────────────────────────────
# Fixture — uses stdlib tempfile, not pytest tmp_path
# ──────────────────────────────────────────────────────────────────────────────

@pytest.fixture()
def fake_repo():
    """Create a minimal fake repository in /tmp."""
    tmp = tempfile.mkdtemp(prefix="pytest_repo_")
    try:
        root = Path(tmp)
        (root / "README.md").write_text("# Hello World\nThis is a test repo.")
        (root / "main.py").write_text("def add(a, b):\n    return a + b\n")
        (root / "utils.py").write_text("def greet(name):\n    return f'Hello {name}'\n")
        (root / "requirements.txt").write_text("requests==2.31.0\n")
        (root / "pyproject.toml").write_text("[project]\nname = 'fake'\n")

        wf_dir = root / ".github" / "workflows"
        wf_dir.mkdir(parents=True)
        (wf_dir / "ci.yml").write_text("name: CI\non: push\n")

        test_dir = root / "tests"
        test_dir.mkdir()
        (test_dir / "__init__.py").write_text("# tests\n")
        (test_dir / "test_main.py").write_text(
            "from main import add\ndef test_add(): assert add(1, 2) == 3\n"
        )

        yield root
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ──────────────────────────────────────────────────────────────────────────────
# Tests
# ──────────────────────────────────────────────────────────────────────────────

class TestRepositoryAnalyzer:
    def test_instantiation(self, fake_repo):
        analyzer = RepositoryAnalyzer(str(fake_repo))
        assert analyzer.repo_path == fake_repo

    def test_get_python_files_finds_py_files(self, fake_repo):
        analyzer = RepositoryAnalyzer(str(fake_repo))
        py_files = analyzer.get_python_files()
        names = [Path(f).name for f in py_files]
        assert "main.py" in names
        assert "utils.py" in names

    def test_get_python_files_excludes_git(self, fake_repo):
        git_dir = fake_repo / ".git"
        git_dir.mkdir(exist_ok=True)
        (git_dir / "hook.py").write_text("# should be excluded")
        analyzer = RepositoryAnalyzer(str(fake_repo))
        py_files = analyzer.get_python_files()
        assert not any(".git" in f for f in py_files)

    def test_get_file_content_existing(self, fake_repo):
        analyzer = RepositoryAnalyzer(str(fake_repo))
        content = analyzer.get_file_content("README.md")
        assert "Hello World" in content

    def test_get_file_content_missing(self, fake_repo):
        analyzer = RepositoryAnalyzer(str(fake_repo))
        content = analyzer.get_file_content("nonexistent.txt")
        assert content == ""

    def test_analyze_structure_detects_readme(self, fake_repo):
        analyzer = RepositoryAnalyzer(str(fake_repo))
        structure = analyzer._analyze_structure()
        assert structure["has_readme"] is True

    def test_analyze_structure_detects_pyproject(self, fake_repo):
        analyzer = RepositoryAnalyzer(str(fake_repo))
        structure = analyzer._analyze_structure()
        assert structure["has_pyproject_toml"] is True

    def test_analyze_structure_detects_tests(self, fake_repo):
        analyzer = RepositoryAnalyzer(str(fake_repo))
        structure = analyzer._analyze_structure()
        assert structure["has_tests"] is True

    def test_analyze_structure_detects_workflows(self, fake_repo):
        analyzer = RepositoryAnalyzer(str(fake_repo))
        structure = analyzer._analyze_structure()
        assert structure["has_github_workflows"] is True

    def test_analyze_repository_returns_dict(self, fake_repo):
        analyzer = RepositoryAnalyzer(str(fake_repo))
        analysis = analyzer.analyze_repository()
        assert isinstance(analysis, dict)
        assert "timestamp" in analysis
        assert "python_files" in analysis
        assert "structure" in analysis

    def test_file_samples_include_readme(self, fake_repo):
        analyzer = RepositoryAnalyzer(str(fake_repo))
        samples = analyzer._get_file_samples()
        assert "README.md" in samples
        assert len(samples["README.md"]) > 0

    def test_get_python_files_capped_at_10(self, fake_repo):
        for i in range(15):
            (fake_repo / f"module_{i:02d}.py").write_text(f"# module {i}\n")
        analyzer = RepositoryAnalyzer(str(fake_repo))
        py_files = analyzer.get_python_files()
        assert len(py_files) <= 10


# ──────────────────────────────────────────────────────────────────────────────
# Project layout sanity checks
# ──────────────────────────────────────────────────────────────────────────────

class TestProjectLayout:
    def test_hetzner_deploy_exists(self):
        assert (_ROOT / "hetzner_deploy.py").exists()

    def test_self_improve_exists(self):
        assert (_ROOT / "self-improve.py").exists()

    def test_requirements_txt_exists(self):
        assert (_ROOT / "requirements.txt").exists()

    def test_hetzner_workflow_exists(self):
        assert (_ROOT / ".github" / "workflows" / "hetzner_runner.yml").exists()

    def test_self_improve_workflow_exists(self):
        assert (_ROOT / ".github" / "workflows" / "self-improve.yml").exists()

    def test_tests_directory_exists(self):
        assert (_ROOT / "tests").is_dir()
