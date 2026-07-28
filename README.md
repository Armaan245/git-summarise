# git-summarise

A CLI tool that inspects recent Git commits and staged changes, then prints a clear, colour-coded summary — optionally powered by **Gemini AI**.

## Setup

```bash
# Create & activate a virtual environment
python -m venv venv
source venv/bin/activate        # Linux / macOS
venv\Scripts\activate           # Windows

# Install dependencies
pip install -r requirements.txt
```

### (Optional) AI summaries

Set the `GEMINI_API_KEY` environment variable to enable `--ai` mode:

```bash
export GEMINI_API_KEY="your-key-here"      # Linux / macOS
$env:GEMINI_API_KEY = "your-key-here"      # PowerShell
```

## Usage

```bash
# Show last 5 commits (default)
python git_summarise.py

# Show last 10 commits
python git_summarise.py -n 10

# Show staged changes
python git_summarise.py --staged

# Show last 3 commits + staged changes
python git_summarise.py -n 3 --staged

# AI-powered natural-language summary (requires GEMINI_API_KEY)
python git_summarise.py --ai

# Point at a different repo
python git_summarise.py --path /path/to/repo
```

### All options

| Flag | Description |
|------|-------------|
| `-n, --commits N` | Number of recent commits to show (default: 5) |
| `-s, --staged` | Include staged (index) changes |
| `--ai` | Use Gemini AI for a natural-language summary |
| `--path DIR` | Path to the Git repository (default: `.`) |
