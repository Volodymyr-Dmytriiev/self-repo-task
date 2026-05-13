# 📋 Deployment Guide - Task 1: Self-Improving Repository

This guide will help you set up the self-improving repository from scratch.

## ⏱️ Expected Time: 10-15 minutes

---

## Step 1: Create GitHub Repository

### 1.1 Create new repository on GitHub

1. Go to https://github.com/new
2. **Repository name**: `self-improvement`
3. **Description**: "Autonomous repository self-improvement using Claude AI"
4. **Visibility**: Public (recommended for showcase)
5. **Initialize with**:
   - ✅ Add a README file
   - ✅ Add .gitignore (Python)
6. Click **Create repository**

### 1.2 Clone the repository locally

```bash
git clone https://github.com/YOUR_USERNAME/self-improvement.git
cd self-improvement
```

---

## Step 2: Add Project Files

Copy these files to your local repository:

### Files to add:
1. **README.md** - Already provided, replace default one
2. **self-improve.py** - Main agent script
3. **requirements.txt** - Python dependencies
4. **pyproject.toml** - Project configuration
5. **.github/workflows/self-improve.yml** - GitHub Actions workflow

### Directory structure:
```
self-improvement/
├── .github/
│   └── workflows/
│       └── self-improve.yml
├── README.md
├── self-improve.py
├── requirements.txt
├── pyproject.toml
└── .gitignore
```

### Commands to set up:

```bash
# Create directories
mkdir -p .github/workflows

# Copy all files to your repository
# (Copy the content from outputs folder into these files)

# Add and commit
git add .
git commit -m "Initial commit: Add self-improvement agent"
git push origin main
```

---

## Step 3: Configure GitHub Secrets

These are required for the agent to work.

### 3.1 Add CLAUDE_API_KEY

1. Go to your repository: **Settings** → **Secrets and variables** → **Actions**
2. Click **New repository secret**
3. **Name**: `CLAUDE_API_KEY`
4. **Value**: Your Claude API key (starts with `sk-ant-`)
5. Click **Add secret**

### 3.2 Add GITHUB_TOKEN

⚠️ **GitHub provides this automatically**, but verify it has correct permissions:

1. Go to **Settings** → **Actions** → **General**
2. Scroll to **Workflow permissions**
3. Ensure it's set to **Read and write permissions**
4. ✅ Enable **Allow GitHub Actions to create and approve pull requests**

### 3.3 Verify Secrets

```bash
# You can check secrets are set (values hidden for security)
# In GitHub UI: Settings → Secrets and variables → Actions
```

---

## Step 4: Enable GitHub Actions

1. Go to repository **Settings**
2. **Actions** → **General**
3. Under "Actions permissions":
   - ✅ Enable "Allow all actions and reusable workflows"
4. Click **Save**

---

## Step 5: Test the Workflow

### 5.1 Manual Trigger (Recommended first test)

1. Go to **Actions** tab in your repository
2. Find **🤖 Self-Improvement Agent** workflow
3. Click **Run workflow** → **Branch: main**
4. Wait ~2 minutes for it to complete

### 5.2 Monitor the run

- ✅ Green checkmark = Success
- ❌ Red X = Failed (check logs)

### 5.3 Check the results

If successful, you should see:
- A new Pull Request in the **Pull requests** tab
- Title: "🤖 Auto-improvements from Claude analysis"
- Contains Claude's suggestions for improvements

---

## Step 6: Review First PR

The first PR will contain improvement suggestions. Review:

1. **Go to Pull Requests** tab
2. Click the auto-improvement PR
3. Review the suggestions in the PR body
4. Click **Files changed** to see what was modified
5. If happy: Click **Merge pull request**
6. If not satisfied: Leave feedback or close PR

---

## Step 7: Automatic Schedule Setup

The workflow will automatically run every 2 hours via cron schedule.

### Current Schedule:
- **Frequency**: Every 2 hours (cron: `0 */2 * * *`)
- **Timezone**: UTC
- **Next run**: Check Actions tab for scheduled times

### To modify frequency:

Edit `.github/workflows/self-improve.yml`:

```yaml
on:
  schedule:
    # Change the cron expression
    - cron: '0 */4 * * *'  # Every 4 hours
    # or
    - cron: '0 9,17 * * *'  # At 9 AM and 5 PM
```

---

## 🧪 Testing Locally (Optional)

### Test without creating PR (dry-run):

```bash
pip install -r requirements.txt

python self-improve.py \
  --api-key sk-ant-YOUR_KEY \
  --github-token ghp_YOUR_TOKEN \
  --repo-path . \
  --repo-owner YOUR_USERNAME \
  --repo-name self-improvement \
  --dry-run
```

This will:
- ✅ Analyze your repository
- ✅ Get Claude suggestions
- ✅ Display improvements
- ❌ NOT create a PR

### Actually create PR:

```bash
python self-improve.py \
  --api-key sk-ant-YOUR_KEY \
  --github-token ghp_YOUR_TOKEN \
  --repo-path . \
  --repo-owner YOUR_USERNAME \
  --repo-name self-improvement
```

---

## 🐛 Troubleshooting

### Issue: GitHub Actions shows red X (failed)

**Solution**: Check the logs:
1. Go to **Actions** tab
2. Click the failed workflow run
3. Click **self-improve** job
4. Scroll down to see error details

Common issues:
- **`CLAUDE_API_KEY not found`**: Add secret in Settings
- **`GITHUB_TOKEN invalid`**: Check workflow permissions
- **`No repository found`**: Check `--repo-owner` and `--repo-name` parameters

### Issue: No PRs being created

**Solution**: Enable Actions:
1. **Settings** → **Actions** → **General**
2. Ensure "Allow all actions" is enabled
3. Manually trigger workflow to test

### Issue: Workflow runs but no PR appears

**Solution**: Check GitHub token permissions:
1. Go to https://github.com/settings/tokens
2. Verify token has `repo` and `workflow` scopes
3. Regenerate token if needed

---

## 📊 What to Show the CTO

### Key Points:

1. **Autonomous Improvement**
   - Shows agent can analyze and improve code
   - Creates proper PRs for review (not auto-merge)
   - Demonstrates responsible AI usage

2. **Real Integration**
   - Uses actual GitHub API
   - Uses actual Claude API
   - Scheduled automation (cron)
   - Proper error handling

3. **Scalability**
   - Can be applied to any repository
   - Configurable improvement categories
   - Rate-limited to avoid API abuse
   - Cost-effective (minimal API calls)

4. **Security**
   - Secrets properly stored
   - No hardcoded credentials
   - PR-based workflow (all changes reviewable)
   - Git audit trail maintained

---

## ✅ Success Criteria

- [x] Repository created and cloned
- [x] All files added to repository
- [x] GitHub secrets configured
- [x] Actions enabled
- [x] Workflow runs successfully
- [x] Auto-improvement PR created with Claude suggestions
- [x] Scheduled to run every 2 hours

---

## 🚀 Next Steps

Once Task 1 is complete and working, move to **Task 2: Hetzner VPS Deployment**

---

## 📞 Questions?

If anything fails:
1. Check GitHub Actions logs
2. Verify all secrets are set correctly
3. Ensure you have GitHub Actions enabled
4. Make sure Claude and GitHub tokens are valid

Good luck! 🎉
