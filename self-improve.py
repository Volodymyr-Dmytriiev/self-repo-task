#!/usr/bin/env python3
"""
Self-Improving Repository Agent

This script analyzes a repository and uses Claude API to suggest improvements,
then creates a pull request with the improvements.

Usage:
    python self-improve.py --api-key YOUR_KEY --github-token TOKEN --repo-path .
"""

import os
import sys
import json
import subprocess
import argparse
from pathlib import Path
from datetime import datetime
from typing import Optional
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
            # Skip excluded directories
            if any(excluded in file.parts for excluded in self.excluded_dirs):
                continue
            python_files.append(str(file.relative_to(self.repo_path)))
        return sorted(python_files)[:10]  # Limit to 10 files for analysis

    def get_file_content(self, file_path: str) -> str:
        """Get content of a file."""
        full_path = self.repo_path / file_path
        if full_path.exists():
            with open(full_path, "r", encoding="utf-8") as f:
                return f.read()
        return ""

    def analyze_repository(self) -> dict:
        """Generate a comprehensive analysis of the repository."""
        analysis = {
            "timestamp": datetime.now().isoformat(),
            "repository_path": str(self.repo_path.absolute()),
            "python_files": self.get_python_files(),
            "structure": self._analyze_structure(),
            "file_samples": self._get_file_samples(),
        }
        return analysis

    def _analyze_structure(self) -> dict:
        """Analyze repository structure."""
        structure = {
            "total_files": len(list(self.repo_path.rglob("*"))),
            "total_dirs": len(list(self.repo_path.rglob("*"))),
            "has_readme": (self.repo_path / "README.md").exists(),
            "has_pyproject_toml": (self.repo_path / "pyproject.toml").exists(),
            "has_requirements_txt": (self.repo_path / "requirements.txt").exists(),
            "has_github_workflows": (self.repo_path / ".github" / "workflows").exists(),
            "has_tests": (self.repo_path / "tests").exists(),
        }
        return structure

    def _get_file_samples(self) -> dict:
        """Get samples of key files."""
        samples = {}

        # README
        readme_path = self.repo_path / "README.md"
        if readme_path.exists():
            content = readme_path.read_text(encoding="utf-8")
            samples["README.md"] = content[:500] + (
                "..." if len(content) > 500 else ""
            )

        # First Python file
        python_files = self.get_python_files()
        if python_files:
            content = self.get_file_content(python_files[0])
            samples["sample_python"] = content[:300] + (
                "..." if len(content) > 300 else ""
            )

        # pyproject.toml
        pyproject_path = self.repo_path / "pyproject.toml"
        if pyproject_path.exists():
            samples["pyproject.toml"] = pyproject_path.read_text(encoding="utf-8")

        return samples


class ClaudeImprover:
    """Uses Claude API to suggest improvements."""

    def __init__(self, api_key: str):
        self.client = anthropic.Anthropic(api_key=api_key)

    def suggest_improvements(self, analysis: dict) -> str:
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
            model="claude-haiku-4-5-20251001",
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}],
        )

        return message.content[0].text


class GitHubIntegration:
    """Handles GitHub API interactions."""

    def __init__(self, token: str, repo_owner: str, repo_name: str):
        self.token = token
        self.repo_owner = repo_owner
        self.repo_name = repo_name
        self.base_url = "https://api.github.com"
        self.headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json",
        }

    def get_repo_info(self) -> dict:
        """Get repository information."""
        url = f"{self.base_url}/repos/{self.repo_owner}/{self.repo_name}"
        response = requests.get(url, headers=self.headers)
        return response.json()

    def create_branch(self, branch_name: str) -> bool:
        """Create a new branch for improvements."""
        try:
            # Get the default branch's latest commit
            repo_info = self.get_repo_info()
            default_branch = repo_info["default_branch"]

            # Get the SHA of the latest commit
            url = f"{self.base_url}/repos/{self.repo_owner}/{self.repo_name}/commits/{default_branch}"
            response = requests.get(url, headers=self.headers)
            sha = response.json()["sha"]

            # Create new branch
            url = f"{self.base_url}/repos/{self.repo_owner}/{self.repo_name}/git/refs"
            data = {
                "ref": f"refs/heads/{branch_name}",
                "sha": sha,
            }
            response = requests.post(url, json=data, headers=self.headers)
            return response.status_code == 201
        except Exception as e:
            print(f"Error creating branch: {e}")
            return False

    def create_file_in_branch(
        self, branch_name: str, file_path: str, content: str
    ) -> bool:
        """Create a file in a specific branch via GitHub API."""
        try:
            url = f"{self.base_url}/repos/{self.repo_owner}/{self.repo_name}/contents/{file_path}"

            # Get the current commit SHA for the branch
            repo_info = self.get_repo_info()
            default_branch = repo_info["default_branch"]

            commits_url = f"{self.base_url}/repos/{self.repo_owner}/{self.repo_name}/commits/{branch_name}"
            commits_response = requests.get(commits_url, headers=self.headers)

            if commits_response.status_code != 200:
                # Branch might not have commits yet, use default branch
                commits_url = f"{self.base_url}/repos/{self.repo_owner}/{self.repo_name}/commits/{default_branch}"
                commits_response = requests.get(commits_url, headers=self.headers)

            parent_sha = commits_response.json()["commit"]["tree"]["sha"]

            # Create file
            data = {
                "message": f"🤖 Add improvement suggestions from Claude",
                "content": content,
                "branch": branch_name,
            }

            response = requests.put(url, json=data, headers=self.headers)
            return response.status_code in [201, 200]
        except Exception as e:
            print(f"Warning: Could not create file in branch: {e}")
            return False

    def create_pull_request(
        self, branch_name: str, title: str, body: str, suggestions: str
    ) -> Optional[str]:
        """Create a pull request with improvements."""
        try:
            # First, create a file with suggestions in the branch
            import base64
            encoded_suggestions = base64.b64encode(f"# Improvement Suggestions\n\n{suggestions}".encode()).decode()
            self.create_file_in_branch(branch_name, "IMPROVEMENTS.md", encoded_suggestions)

            # Now create the PR
            url = f"{self.base_url}/repos/{self.repo_owner}/{self.repo_name}/pulls"
            repo_info = self.get_repo_info()
            default_branch = repo_info["default_branch"]

            data = {
                "title": title,
                "head": branch_name,
                "base": default_branch,
                "body": body,
            }

            response = requests.post(url, json=data, headers=self.headers)

            if response.status_code == 201:
                pr_data = response.json()
                return pr_data["html_url"]
            else:
                print(f"Error creating PR: {response.text}")
                return None
        except Exception as e:
            print(f"Error creating pull request: {e}")
            return None


def get_git_config():
    """Get git user configuration."""
    try:
        name = subprocess.check_output(
            ["git", "config", "user.name"], text=True
        ).strip()
        email = subprocess.check_output(
            ["git", "config", "user.email"], text=True
        ).strip()
        return name, email
    except subprocess.CalledProcessError:
        return "Self-Improvement Agent", "agent@self-improvement.local"


def main():
    parser = argparse.ArgumentParser(
        description="Self-Improving Repository Agent"
    )
    parser.add_argument(
        "--api-key", required=True, help="Claude API key"
    )
    parser.add_argument(
        "--github-token", required=True, help="GitHub Personal Access Token"
    )
    parser.add_argument(
        "--repo-path", default=".", help="Path to repository"
    )
    parser.add_argument(
        "--repo-owner",
        help="GitHub repository owner (auto-detected from git if not provided)",
    )
    parser.add_argument(
        "--repo-name",
        help="GitHub repository name (auto-detected from git if not provided)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Don't actually create a PR, just show suggestions",
    )

    args = parser.parse_args()

    # Auto-detect repo owner and name if not provided
    if not args.repo_owner or not args.repo_name:
        try:
            remote_url = subprocess.check_output(
                ["git", "-C", args.repo_path, "config", "--get", "remote.origin.url"],
                text=True,
            ).strip()

            # Parse https://github.com/owner/repo.git or git@github.com:owner/repo.git
            if "github.com" in remote_url:
                parts = remote_url.split("github.com")[-1].strip("/:").split("/")
                args.repo_owner = parts[0]
                args.repo_name = parts[1].replace(".git", "")
        except subprocess.CalledProcessError:
            print("Error: Could not auto-detect repo owner/name. Please provide --repo-owner and --repo-name")
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
        print("\n✅ Dry run completed. No PR created.")
        return

    # Create PR if not dry-run
    print("\n📝 Creating pull request...")

    github = GitHubIntegration(args.github_token, args.repo_owner, args.repo_name)

    branch_name = f"improve/{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    if not github.create_branch(branch_name):
        print(f"❌ Failed to create branch: {branch_name}")
        sys.exit(1)

    pr_title = f"🤖 Auto-improvements from Claude analysis"
    pr_body = f"""## 🚀 Automated Repository Improvements

This PR contains improvements suggested by Claude AI analysis.

### Analysis Summary
- Repository: {args.repo_owner}/{args.repo_name}
- Analysis time: {analysis['timestamp']}
- Python files analyzed: {len(analysis['python_files'])}

### Suggested Improvements

{suggestions}

### Next Steps
1. Review the suggestions above
2. Merge this PR if improvements look good
3. Next auto-improvement will run in 2 hours

---
*This PR was automatically generated by the Self-Improvement Agent*
"""

    pr_url = github.create_pull_request(branch_name, pr_title, pr_body, suggestions)
    if pr_url:
        print(f"✅ Pull request created: {pr_url}")
    else:
        print("❌ Failed to create pull request")
        sys.exit(1)


if __name__ == "__main__":
    main()
