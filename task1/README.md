# 🚀 Self-Improving Repository

A proof-of-concept demonstrating **autonomous repository self-improvement** using Claude AI. This repository automatically enhances itself every 2 hours through intelligent code analysis and documentation improvements.

## 🎯 Purpose

This project showcases:
- **Autonomous Code Analysis**: Claude AI analyzes repository structure and code quality
- **Intelligent Suggestions**: Generates meaningful improvements (documentation, code quality, best practices)
- **Automated PRs**: Creates pull requests with improvements automatically
- **Self-Healing**: Identifies and fixes potential issues in the codebase
- **Scheduled Automation**: Runs every 2 hours via GitHub Actions

## 🏗️ Architecture

```
┌─────────────────────────────────────────┐
│     GitHub Actions (Every 2 hours)      │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│   self-improve.py (Main Agent)          │
│  - Analyzes repository content          │
│  - Consults Claude API for improvements │
│  - Generates improvement suggestions    │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│   Creates Automated Pull Requests       │
│  - With detailed commit messages        │
│  - Ready for review and merging         │
└─────────────────────────────────────────┘
```

## 📦 Key Features

### 1. **Code Quality Analysis**
- Detects missing type hints
- Suggests docstring improvements
- Identifies code complexity issues
- Recommends refactoring opportunities

### 2. **Documentation Enhancement**
- Updates README with latest examples
- Generates missing documentation
- Ensures consistency in docs
- Adds usage instructions

### 3. **Repository Health Checks**
- Analyzes project structure
- Checks for best practices
- Validates configuration files
- Suggests performance optimizations

### 4. **Intelligent Scheduling**
- Automatic runs every 2 hours
- Configurable via GitHub Secrets
- Rate-limited to avoid excessive PRs
- Tracks improvement history

## 🔧 Setup Instructions

### Prerequisites
- GitHub account with Personal Access Token
- Claude API key
- Python 3.10+

### 1. Clone and Setup
```bash
git clone https://github.com/your-username/self-improvement.git
cd self-improvement
pip install -r requirements.txt
```

### 2. Configure GitHub Secrets
Go to **Settings → Secrets and Variables → Actions**:

- `CLAUDE_API_KEY`: Your Claude API key (from console.anthropic.com)
- `GITHUB_TOKEN`: GitHub Personal Access Token (with `repo` and `workflow` permissions)

### 3. Enable GitHub Actions
- Go to **Settings → Actions → General**
- Ensure "Allow all actions and reusable workflows" is enabled
- Enable workflows for this repository

## 🚀 How It Works

### Automatic Improvement Flow (Every 2 hours)

1. **GitHub Action Triggers** → Scheduled workflow runs
2. **Repository Analysis** → Script reads all code and documentation
3. **Claude Analysis** → AI analyzes and suggests improvements
4. **PR Generation** → Creates pull request with improvements
5. **Auto-commit** → Commits changes with detailed messages

### Manual Trigger (Testing)

```bash
python self-improve.py \
  --api-key YOUR_CLAUDE_API_KEY \
  --github-token YOUR_GITHUB_TOKEN \
  --repo-path . \
  --dry-run  # Remove for actual PR creation
```

## 📊 Improvement Categories

The agent focuses on:

| Category | Example Improvements |
|----------|----------------------|
| **Code Quality** | Add type hints, improve docstrings |
| **Documentation** | Update README, add examples |
| **Structure** | Organize files, improve naming |
| **Performance** | Suggest optimizations |
| **Security** | Identify potential vulnerabilities |
| **Testing** | Suggest test coverage improvements |

## 📈 Progress Tracking

Each improvement PR includes:
- Detailed commit message explaining changes
- Timestamp of improvement
- Categories of improvements made
- References to previous improvements

View all improvements in the **Pull Requests** tab.

## 🔐 Security Considerations

- **API Keys**: Stored securely in GitHub Secrets
- **PR Safety**: Improvements are PRs, not auto-merged
- **Rate Limiting**: Built-in delays to prevent API abuse
- **Code Review**: All changes reviewable before merging

## 💡 Use Cases

This pattern demonstrates:
- Autonomous code maintenance
- AI-powered development workflows
- Intelligent automation at scale
- Continuous repository improvement
- Monitoring and self-healing systems

## 🚦 Status

- ✅ Repository analysis implemented
- ✅ Claude API integration working
- ✅ GitHub Actions configured
- ✅ PR generation functional
- 🔄 Scheduled runs every 2 hours

## 📝 License

MIT License - Feel free to use and modify

## 🤝 Contributing

This is a demonstration project. Feel free to:
- Fork and experiment
- Add new improvement categories
- Enhance the analysis logic
- Share improvements with the community

---

**Last Improved**: Check the most recent PR for details!
