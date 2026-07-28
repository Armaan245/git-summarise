# git-summarise

A CLI tool that inspects recent Git commits and staged changes, then prints a
rich, colour-coded summary in the terminal — optionally powered by **Gemini AI**
— and can export a styled **PDF report**.

## Setup

```bash
# Create & activate a virtual environment
python -m venv venv
source venv/bin/activate        # Linux / macOS
venv\Scripts\activate           # Windows

# Install as a local CLI tool (editable / development mode)
pip install -e .
```

This installs a `git-summarise` command into your venv so you can run it from
anywhere — no need to type `python git_summarise.py`.

> **Alternative:** if you only want the dependencies without installing the
> package itself, run `pip install -r requirements.txt` and invoke the script
> directly with `python git_summarise.py`.

### (Optional) AI summaries

Set the `GEMINI_API_KEY` environment variable to enable `--ai` mode:

```bash
export GEMINI_API_KEY="your-key-here"      # Linux / macOS
$env:GEMINI_API_KEY = "your-key-here"      # PowerShell
```

## Usage

```bash
# Show last 5 commits (default)
git-summarise

# Show last 10 commits
git-summarise -n 10

# Show staged changes
git-summarise --staged

# Show last 3 commits + staged changes
git-summarise -n 3 --staged

# AI-powered natural-language summary (requires GEMINI_API_KEY)
git-summarise --ai

# Export a PDF report
git-summarise --pdf

# Export PDF with a custom filename
git-summarise --pdf --out reports/weekly.pdf

# Combine flags: AI summary + PDF + staged changes
git-summarise --ai --pdf --staged

# Point at a different repo
git-summarise --path /path/to/repo
```

### All options

| Flag | Description |
|------|-------------|
| `-n, --commits N` | Number of recent commits to show (default: 5) |
| `-s, --staged` | Include staged (index) changes |
| `--ai` | Use Gemini AI for a natural-language summary |
| `--pdf` | Export the summary as a styled PDF report |
| `--out FILE` | Output path for the PDF (default: `git_summary.pdf`) |
| `--path DIR` | Path to the Git repository (default: `.`) |
