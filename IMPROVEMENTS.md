# 🤖 Automated Improvements from Claude Analysis

**Generated**: 2026-05-16T10:56:09.599205
**Repository**: Volodymyr-Dmytriiev/self-repo-task
**Python Files Analyzed**: 5

## Suggested Improvements



```json
{
  "improvements": [
    {
      "id": 1,
      "category": "Project Structure",
      "title": "Create a proper Python package directory",
      "what": "The pyproject.toml references a `self_improvement` package directory (`packages = [\"self_improvement\"]`), but no such directory exists. The main scripts (`hetzner_deploy.py`, `self-improve.py`) are loose files at the root.",
      "why": "Without a proper package directory, `pip install -e .` will fail, imports between modules won't work cleanly, and the project doesn't follow standard Python packaging conventions. This also prevents reuse of shared utilities across scripts.",
      "how": "Create `self_improvement/` directory with `__init__.py`, refactor shared logic into modules, and keep thin CLI entry points at the root or use `[project.scripts]` console entry points.",
      "code_snippet": "# Directory structure:\n# self_improvement/\n#   __init__.py\n#   analyzer.py       # Code analysis logic\n#   improver.py        # Self-improvement orchestration\n#   deployer.py        # Hetzner deployment logic\n#   config.py          # Shared configuration/constants\n#\n# pyproject.toml addition:\n# [project.scripts]\n# self-improve = \"self_improvement.improver:main\"\n# hetzner-deploy = \"self_improvement.deployer:main\"",
      "estimated_effort": "medium",
      "files_to_modify": ["pyproject.toml", "self-improve.py", "hetzner_deploy.py"]
    },
    {
      "id": 2,
      "category": "Code Quality",
      "title": "Rename `self-improve.py` to use valid Python module naming",
      "what": "Rename `self-improve.py` to `self_improve.py` (underscore instead of hyphen).",
      "why": "Hyphens in Python filenames prevent direct imports (`import self-improve` is a syntax error). This also causes the test file `test_self_improve.py` to need workarounds like `importlib` to import the module under test, making testing fragile.",
      "how": "Rename the file and update all references in CI workflows, README, and test imports.",
      "code_snippet": "# In shell/CI:\n# mv self-improve.py self_improve.py\n#\n# In tests/test_self_improve.py, change from:\n# import importlib; mod = importlib.import_module('self-improve')\n# To:\n# import self_improve\n# or\n# from self_improve import main",
      "estimated_effort": "quick",
      "files_to_modify": ["self-improve.py", "tests/test_self_improve.py", ".github/workflows/"]
    },
    {
      "id": 3,
      "category": "Code Quality",
      "title": "Add comprehensive type hints to all public functions",
      "what": "Add type annotations to all function signatures and enable `disallow_untyped_defs = true` in mypy config.",
      "why": "The mypy config currently has `disallow_untyped_defs = false`, meaning type checking is effectively opt-in and provides minimal value. Type hints catch bugs at static analysis time, improve IDE autocomplete, and serve as living documentation for function contracts.",
      "how": "Annotate all functions, use `TypedDict` or `dataclasses` for structured data, and tighten mypy settings incrementally.",
      "code_snippet": "# Before:\ndef create_server(name, token, runner_token):\n    ...\n\n# After:\nfrom typing import Any\n\ndef create_server(\n    name: str,\n    token: str,\n    runner_token: str,\n    server_type: str = \"cx22\",\n) -> dict[str, Any]:\n    \"\"\"Create a Hetzner Cloud server with GitHub runner configuration.\n    \n    Args:\n        name: Server name in Hetzner Cloud.\n        token: Hetzner API token.\n        runner_token: GitHub Actions runner registration token.\n        server_type: Hetzner server type identifier.\n    \n    Returns:\n        Server creation response from Hetzner API.\n    \n    Raises:\n        HetznerAPIError: If server creation fails.\n    \"\"\"\n    ...\n\n# In pyproject.toml:\n# [tool.mypy]\n# disallow_untyped_defs = true\n# disallow_incomplete_defs = true\n# check_untyped_defs = true\n# strict_optional = true",
      "estimated_effort": "medium",
      "files_to_modify": ["hetzner_deploy.py", "self-improve.py", "pyproject.toml"]
    },
    {
      "id": 4,
      "category": "Best Practices",
      "title": "Add structured error handling with custom exceptions",
      "what": "Create custom exception classes instead of using bare `Exception` or letting raw `requests` exceptions propagate.",
      "why": "Custom exceptions make error handling more precise, allow callers to catch specific failure modes (API errors vs. configuration errors vs. timeout errors), and produce more actionable error messages. This is especially important for a deployment script where understanding *what* failed is critical.",
      "how": "Create an exceptions module with a hierarchy, and wrap API calls with appropriate error handling.",
      "code_snippet": "# self_improvement/exceptions.py\nclass SelfImprovementError(Exception):\n    \"\"\"Base exception for all self-improvement errors.\"\"\"\n\nclass HetznerAPIError(SelfImprovementError):\n    \"\"\"Raised when Hetzner Cloud API returns an error.\"\"\"\n    def __init__(self, message: str, status_code: int, response_body: dict | None = None):\n        super().__init__(message)\n        self.status_code = status_code\n        self.response_body = response_body\n\nclass ConfigurationError(SelfImprovementError):\n    \"\"\"Raised when required configuration is missing or invalid.\"\"\"\n\nclass AnalysisError(SelfImprovementError):\n    \"\"\"Raised when code analysis fails.\"\"\"\n\n# Usage in hetzner_deploy.py:\ndef _api_request(method: str, endpoint: str, token: str, **kwargs) -> dict:\n    resp = requests.request(method, f\"{BASE_URL}/{endpoint}\", **kwargs)\n    if not resp.ok:\n        raise HetznerAPIError(\n            f\"API {method} {endpoint} failed\",\n            status_code=resp.status_code,\n            response_body=resp.json() if resp.content else None,\n        )\n    return resp.json()",
      "estimated_effort": "medium",
      "files_to_modify": ["hetzner_deploy.py", "self-improve.py"]
    },
    {
      "id": 5,
      "category": "Best Practices",
      "title": "Use environment variable validation at startup with pydantic or a config dataclass",
      "what": "Validate all required environment variables (API tokens, repo info) at startup instead of failing mid-execution.",
      "why": "Deployment scripts that fail halfway through (e.g., server created but runner registration fails due to missing token) leave orphaned resources. Fail-fast validation prevents partial execution and gives clear error messages about what's missing.",
      "how": "Create a configuration class that validates on construction.",
      "code_snippet": "import os\nfrom dataclasses import dataclass, field\n\n@dataclass(frozen=True)\nclass DeployConfig:\n    hetzner_token: str\n    github_token: str\n    github_repo: str\n    server_type: str = \"cx22\"\n    location: str = \"fsn1\"\n    image: str = \"ubuntu-22.04\"\n    \n    @classmethod\n    def from_env(cls) -> 'Deploy

---
*Auto-generated by Self-Improvement Agent - Runs every 2 hours*
