# 🤖 Automated Improvements from Claude Analysis

**Generated**: 2026-05-21T19:44:21.902674
**Repository**: Volodymyr-Dmytriiev/self-repo-task
**Python Files Analyzed**: 5

## Suggested Improvements



```json
{
  "improvements": [
    {
      "id": 1,
      "category": "Project Structure",
      "title": "Create a proper Python package directory instead of top-level scripts",
      "what": "Move `self-improve.py` and `hetzner_deploy.py` into a proper `self_improvement/` package with `__init__.py`, `cli.py`, `analyzer.py`, `deployer.py` modules. The `pyproject.toml` already references `self_improvement` as a package but it doesn't exist.",
      "why": "The `pyproject.toml` declares `packages = [\"self_improvement\"]` but the actual code lives as top-level scripts with hyphens in the names (which aren't valid Python identifiers). This means `pip install` would install an empty package. A proper package structure enables importability, testability, and distribution.",
      "how": "```\nmkdir -p self_improvement/\n# Create self_improvement/__init__.py\n# Move logic from self-improve.py -> self_improvement/analyzer.py\n# Move logic from hetzner_deploy.py -> self_improvement/deployer.py\n# Create self_improvement/cli.py with entry points\n# Update pyproject.toml:\n[project.scripts]\nself-improve = \"self_improvement.cli:main_improve\"\nhetzner-deploy = \"self_improvement.cli:main_deploy\"\n```",
      "estimated_effort": "medium",
      "files_to_modify": ["self-improve.py", "hetzner_deploy.py", "pyproject.toml", "self_improvement/__init__.py", "self_improvement/analyzer.py", "self_improvement/deployer.py", "self_improvement/cli.py"]
    },
    {
      "id": 2,
      "category": "Code Quality",
      "title": "Add comprehensive type hints to all functions",
      "what": "Add type annotations to all function signatures, return types, and key variables in both `self-improve.py` and `hetzner_deploy.py`. Enable `disallow_untyped_defs = true` in mypy config.",
      "why": "The mypy configuration currently has `disallow_untyped_defs = false`, meaning type checking is essentially toothless. Type hints catch entire classes of bugs at development time, improve IDE support, and serve as machine-verified documentation.",
      "how": "```python\n# Before\ndef create_firewall(client, name):\n    ...\n\n# After\nfrom typing import Any\nimport requests\n\ndef create_firewall(client: requests.Session, name: str) -> dict[str, Any]:\n    \"\"\"Create a Hetzner Cloud firewall with no inbound rules.\"\"\"\n    ...\n\n# In pyproject.toml\n[tool.mypy]\ndisallow_untyped_defs = true\nstrict_optional = true\nwarn_redundant_casts = true\ncheck_untyped_defs = true\n```",
      "estimated_effort": "medium",
      "files_to_modify": ["self-improve.py", "hetzner_deploy.py", "pyproject.toml"]
    },
    {
      "id": 3,
      "category": "Security",
      "title": "Add input validation and secrets handling hardening",
      "what": "Validate all environment variables at startup with clear error messages. Ensure API tokens and secrets are never logged. Add a configuration class that validates required env vars.",
      "why": "The Hetzner deploy script handles API tokens and GitHub runner registration tokens. If these are accidentally logged, leaked, or missing, it can lead to security incidents or confusing runtime errors deep in the execution flow.",
      "how": "```python\nimport os\nfrom dataclasses import dataclass\n\n@dataclass(frozen=True)\nclass HetznerConfig:\n    api_token: str\n    github_token: str\n    runner_repo: str\n    server_type: str = \"cx22\"\n\n    @classmethod\n    def from_env(cls) -> \"HetznerConfig\":\n        missing = []\n        for var in [\"HETZNER_API_TOKEN\", \"GITHUB_TOKEN\", \"RUNNER_REPO\"]:\n            if not os.environ.get(var):\n                missing.append(var)\n        if missing:\n            raise SystemExit(\n                f\"Missing required environment variables: {', '.join(missing)}\"\n            )\n        return cls(\n            api_token=os.environ[\"HETZNER_API_TOKEN\"],\n            github_token=os.environ[\"GITHUB_TOKEN\"],\n            runner_repo=os.environ[\"RUNNER_REPO\"],\n        )\n\n    def __repr__(self) -> str:\n        return \"HetznerConfig(api_token=***, github_token=***, ...)\"\n```",
      "estimated_effort": "medium",
      "files_to_modify": ["hetzner_deploy.py"]
    },
    {
      "id": 4,
      "category": "Testing",
      "title": "Add meaningful test coverage with mocking for external APIs",
      "what": "Expand `tests/test_hetzner_deploy.py` and `tests/test_self_improve.py` with proper unit tests that mock HTTP calls (Hetzner API, Anthropic API), test error handling paths, and validate configuration parsing.",
      "why": "Having test files exist is not the same as having useful tests. Without mocked API tests, you can't verify behavior without making real API calls, and refactoring becomes dangerous. Mocked tests run fast and in CI without secrets.",
      "how": "```python\n# tests/test_hetzner_deploy.py\nimport pytest\nfrom unittest.mock import patch, MagicMock\n\n@pytest.fixture\ndef mock_env(monkeypatch):\n    monkeypatch.setenv(\"HETZNER_API_TOKEN\", \"test-token\")\n    monkeypatch.setenv(\"GITHUB_TOKEN\", \"ghp_test\")\n    monkeypatch.setenv(\"RUNNER_REPO\", \"owner/repo\")\n\ndef test_config_from_env_missing_vars():\n    with pytest.raises(SystemExit, match=\"HETZNER_API_TOKEN\"):\n        HetznerConfig.from_env()\n\n@patch(\"requests.post\")\ndef test_create_firewall_success(mock_post, mock_env):\n    mock_post.return_value.status_code = 201\n    mock_post.return_value.json.return_value = {\"firewall\": {\"id\": 123}}\n    result = create_firewall(\"test-fw\")\n    assert result[\"firewall\"][\"id\"] == 123\n    # Verify auth header sent\n    call_kwargs = mock_post.call_args\n    assert \"Bearer\" in call_kwargs.kwargs[\"headers\"][\"Authorization\"]\n\n@patch(\"requests.post\")\ndef test_create_firewall_api_error(mock_post, mock_env):\n    mock_post.return_value.status_code = 422\n    mock_post.return_value.json.return_value = {\"error\": {\"message\": \"quota\"}}\n    with pytest.raises(RuntimeError, match=\"quota\"):\n        create_firewall(\"test-fw\")\n```",
      "estimated_effort": "medium",
      "files_to_modify": ["tests/test_hetzner_deploy.py", "tests/test_self_improve.py", "tests/conftest.py"]
    },
    {
      "id": 5,
      "category": "Code Quality",
      "title": "Extract the self-improve analysis logic into composable, testable functions",
      "what": "Break `self-improve.py` into discrete functions: `collect_repo_metadata()`, `build_analysis_prompt()`, `call_claude_api()`,

---
*Auto-generated by Self-Improvement Agent - Runs every 2 hours*
