#!/usr/bin/env python3
"""
Self-Improving Repository Agent

Analyzes a repository using Claude API and automatically commits improvements.

Usage:
    python self-improve.py --api-key YOUR_KEY --github-token TOKEN --repo-path .
"""

import os
import sys
import json
import subprocess
import argparse
import base64
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any

import anthropic
import requests


class RepositoryAnalyzer:
    """Analyzes repository structure and content."""

    def __init__(self, repo_path: str):
        self.repo_path = Path(repo_path)
        self.excluded_dirs = {
            ".git",
            "__pycache__",
            ".pytest_cache",
            "node_modules",
            ".venv",
            "venv",
            ".idea",
            ".vscode",
            ".github",
            "build",
            "dist",
            "*.egg-info",
        }

    def get_python_files(self) -> list[str]:
        """Get all Python files in the repository."""
        python_files = []
        for file in self.repo_path.rglob("*.py"):
            if any(excluded in file.parts for excluded in self.excluded_dirs):
                continue
            python_files.append(str(file.relative_to(self.repo_path)))
        return sorted(python_files)[:10]

    def get_file_content(self, file_path: str) -> str:
        """Get content of a file."""
        full_path = self.repo_path / file_path
        if full_path.exists():
            with open(full_path, "r", encoding="utf-8") as f:
                return f.read()
        return ""

    def analyze_repository(self) -> Dict[str, Any]:
        """Generate a comprehensive analysis of the repository."""
        analysis = {
            "timestamp": datetime.now().isoformat(),
            "repository_path": str(self.repo_path.absolute()),
            "python_files": self.get_python_files(),
            "structure": self._analyze_structure(),
            "file_samples": self._get_file_samples(),
        }
        return analysis

    def _analyze_structure(self) -> Dict[str, Any]:
        """Analyze repository structure."""
        structure = {
            "total_files": len(list(self.repo_path.rglob("*"))),
            "has_readme": (self.repo_path / "README.md").exists(),
            "has_pyproject_toml": (self.repo_path / "pyproject.toml").exists(),
            "has_requirements_txt": (self.repo_path / "requirements.txt").exists(),
            "has_github_workflows": (self.repo_path / ".github" / "workflows").exists(),
            "has_tests": (self.repo_path / "tests").exists(),
        }
        return structure

    def _get_file_samples(self) -> Dict[str, str]:
        """Get samples of key files."""
        samples = {}

        readme_path = self.repo_path / "README.md"
        if readme_path.exists():
            content = readme_path.read_text(encoding="utf-8")
            samples["README.md"] = content[:500]

        python_files = self.get_python_files()
        if python_files:
            content = self.get_file_content(python_files[0])
            samples["sample_python"] = content[:300]

        pyproject_path = self.repo_path / "pyproject.toml"
        if pyproject_path.exists():
            samples["pyproject.toml"] = pyproject_path.read_text(encoding="utf-8")

        return samples


class ClaudeImprover:
    """Uses Claude API to suggest improvements."""

    def __init__(self, api_key: str):
        self.client = anthropic.Anthropic(api_key=api_key)

    def suggest_improvements(self, analysis: Dict[str, Any]) -> str:
        """Get improvement suggestions from Claude."""
        prompt = f"""
Analyze this GitHub repository structure and provide specific, actionable improvements.

Repository Analysis:
{json.dumps(analysis, indent=2)}

Please provide improvements in the following categories:

1. **Code Quality**: Type hints, docstrings, code organization
2. **Documentation**: README improvements, inline comments, examples
3. **Project Structure**: File organization, naming conventions
4. **Best Practices**: Python standards, security, performance
5. **Testing**: Test coverage, test organization

Format your response as a JSON object with these keys:
- "improvements": list of specific improvements to make
- "priority": which improvements to prioritize
- "estimated_effort": time to implement (quick/medium/complex)
- "files_to_modify": list of files that need changes

Be specific - each improvement should have:
- What to change
- Why (2-3 sentences explaining benefit)
- How to implement (code snippet if applicable)
"""

        message = self.client.messages.create(
            model="claude-opus-4-6",
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}],
        )

        return message.content[0].text


class GitHubIntegration:
    """Handles GitHub API interactions for committing improvements."""

    def __init__(self, token: str, repo_owner: str, repo_name: str):
        self.token = token
        self.repo_owner = repo_owner
        self.repo_name = repo_name
        self.base_url = "https://api.github.com"
        self.headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json",
        }

    def get_repo_info(self) -> Dict[str, Any]:
        """Get repository information."""
        url = f"{self.base_url}/repos/{self.repo_owner}/{self.repo_name}"
        response = requests.get(url, headers=self.headers)
        return response.json()

    def commit_improvements_directly(
        self, suggestions: str, analysis: Dict[str, Any]
    ) -> bool:
        """Commit improvements directly to main branch."""
        try:
            # Get default branch info
            repo_info = self.get_repo_info()
            default_branch = repo_info["default_branch"]

            # Create file content
            file_content = f"""# 🤖 Automated Improvements from Claude Analysis

**Generated**: {analysis['timestamp']}
**Repository**: {self.repo_owner}/{self.repo_name}
**Python Files Analyzed**: {len(analysis['python_files'])}

## Suggested Improvements

{suggestions}

---
*Auto-generated by Self-Improvement Agent - Runs every 2 hours*
"""

            # Encode for GitHub API
            encoded_content = base64.b64encode(file_content.encode()).decode()

            # Create/update IMPROVEMENTS.md in main branch
            url = f"{self.base_url}/repos/{self.repo_owner}/{self.repo_name}/contents/IMPROVEMENTS.md"

            # Check if file exists
            sha = None
            try:
                existing = requests.get(url, headers=self.headers)
                if existing.status_code == 200:
                    sha = existing.json()["sha"]
            except Exception:
                pass

            # Commit the improvements
            data = {
                "message": f"🤖 Auto-improvements from Claude analysis",
                "content": encoded_content,
                "branch": default_branch,
            }

            if sha:
                data["sha"] = sha

            response = requests.put(url, json=data, headers=self.headers)

            if response.status_code in [200, 201]:
                print(f"✅ Improvements committed to {default_branch}")
                print(f"📝 File: IMPROVEMENTS.md")
                return True
            else:
                print(f"❌ Error committing improvements: {response.text}")
                return False

        except Exception as e:
            print(f"❌ Error: {e}")
            return False


def main():
    parser = argparse.ArgumentParser(
        description="Self-Improving Repository Agent"
    )
    parser.add_argument("--api-key", required=True, help="Claude API key")
    parser.add_argument("--github-token", required=True, help="GitHub Personal Access Token")
    parser.add_argument("--repo-path", default=".", help="Path to repository")
    parser.add_argument("--repo-owner", help="GitHub repository owner")
    parser.add_argument("--repo-name", help="GitHub repository name")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Don't commit, just show suggestions",
    )

    args = parser.parse_args()

    # Auto-detect repo owner and name if not provided
    if not args.repo_owner or not args.repo_name:
        try:
            remote_url = subprocess.check_output(
                ["git", "-C", args.repo_path, "config", "--get", "remote.origin.url"],
                text=True,
            ).strip()

            if "github.com" in remote_url:
                parts = remote_url.split("github.com")[-1].strip("/:").split("/")
                args.repo_owner = parts[0]
                args.repo_name = parts[1].replace(".git", "")
        except subprocess.CalledProcessError:
            print("Error: Could not auto-detect repo. Please provide --repo-owner and --repo-name")
            sys.exit(1)

    print(f"🔍 Analyzing repository: {args.repo_owner}/{args.repo_name}")
    print(f"📍 Repository path: {args.repo_path}")

    # Analyze repository
    analyzer = RepositoryAnalyzer(args.repo_path)
    analysis = analyzer.analyze_repository()

    print("📊 Repository analysis complete")
    print(f"   - Python files found: {len(analysis['python_files'])}")
    print(f"   - Has README: {analysis['structure']['has_readme']}")
    print(f"   - Has tests: {analysis['structure']['has_tests']}")

    # Get improvements from Claude
    print("\n🤖 Consulting Claude API for improvements...")
    improver = ClaudeImprover(args.api_key)
    suggestions = improver.suggest_improvements(analysis)

    print("\n💡 Improvement Suggestions:")
    print("=" * 60)
    print(suggestions)
    print("=" * 60)

    if args.dry_run:
        print("\n✅ Dry run completed. No changes committed.")
        return

    # Commit improvements directly to main
    print("\n📝 Committing improvements to main branch...")

    github = GitHubIntegration(args.github_token, args.repo_owner, args.repo_name)

    if github.commit_improvements_directly(suggestions, analysis):
        print("\n✅ Improvements automatically applied to main branch!")
        print("🎉 Repository improved successfully")
    else:
        print("❌ Failed to commit improvements")
        sys.exit(1)


if __name__ == "__main__":
    main()
