# 🚀 Git Summarise

> **Transform raw Git history, staged diffs, and project structures into human-readable Markdown documentation & professional PDF reports.**

`git-summarise` is a lightweight, high-utility Command Line Interface (CLI) tool designed for developers, project leads, and open-source maintainers. It automates repository auditing, AI-powered commit summarization, and multi-page documentation suite generation—all exportable to styled PDFs in seconds.

---

## ✨ Features

* **🤖 AI-Powered Summaries:** Connects directly with LLMs (Gemini, GPT-4o-mini, Claude, DeepSeek) to analyze recent commits and produce concise, natural-language activity logs.
* **📄 Complete Docs Suite:** Automatically extracts and structures project documentation in a clean `/docs` directory.
* **📊 Professional PDF Export:** Generates clean, styled PDF reports—perfect for team syncs, client updates, or project handovers.
* **⚡ Smart Directory Filtering:** Automatically skips heavy metadata folders like `node_modules`, `venv`, `.git`, `.dart_tool`, and build artifacts to maintain fast scanning speeds.
* **🔍 Flexibility:** Inspect recent commit histories (N commits), staged diffs, or point to any remote/local repository directory.

---

## 📦 Prerequisites

* **Python 3.10** or higher
* **Git** installed and configured in your System `PATH`
* *(Optional)* API key for AI features (e.g., `GEMINI_API_KEY` or `OPENAI_API_KEY`)

---

## ⚡ Installation

### Option 1: Direct Install via `pip` (Recommended)

```bash
pip install git+https://github.com/Armaan245/git-summarise.git
```

> **Note for Windows PowerShell Users:**  
> If the global executable isn't automatically added to your PATH, run through your active Python environment:
> ```powershell
> python -m pip install git+https://github.com/Armaan245/git-summarise.git
> ```

### Option 2: Local Developer Setup

If you want to contribute or modify the tool locally:

```bash
# 1. Clone the repository
git clone https://github.com/Armaan245/git-summarise.git
cd git-summarise

# 2. Create and activate a virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1   # On Windows PowerShell
# source .venv/bin/activate    # On Linux/macOS

# 3. Install in editable mode
pip install -e .
```

---

## 🛠️ Usage & Examples

Run `git-summarise` from inside **any Git repository**.

### Basic Usage
```bash
# Summarize the last 5 commits (default)
git-summarise

# Summarize the last 15 commits
git-summarise -n 15

# Include staged changes currently in index
git-summarise --staged
```

### AI-Powered Summaries
```bash
# Generate an AI summary using the default provider (Gemini)
git-summarise --ai

# Use a specific AI model provider
git-summarise --ai --provider gpt
git-summarise --ai --provider claude
git-summarise --ai --provider deepseek
```

### Documentation & PDF Reports
```bash
# Build a multi-page Markdown documentation suite inside /docs
git-summarise --docs

# Generate Markdown suite AND compile to PDF
git-summarise --docs --pdf

# Export a quick summary PDF with a custom file path
git-summarise --pdf --out reports/weekly_summary.pdf

# Run against a different project directory
git-summarise --path C:\Users\YourName\Desktop\other-project
```

---

## 📋 Full Command-Line Options

| Flag | Short | Argument | Description | Default |
| :--- | :--- | :--- | :--- | :--- |
| `--help` | `-h` | None | Displays help message and exits | — |
| `--commits` | `-n` | `INT` | Number of recent commits to analyze | `5` |
| `--staged` | `-s` | None | Include uncommitted staged changes in summary | `False` |
| `--docs` | — | None | Generate multi-page `/docs` Markdown suite | `False` |
| `--ai` | — | None | Enable natural-language summary using an LLM | `False` |
| `--provider` | — | `{gemini,gpt,claude,deepseek}` | Choose the AI model backend | `gemini` |
| `--pdf` | — | None | Export output as a styled PDF report | `False` |
| `--out` | — | `FILE` | Custom output path for PDF file | `git_summary.pdf` |
| `--path` | — | `DIR` | Target Git repository directory path | Current Directory |

---

## 🔑 Environment Variables Setup

To use the `--ai` flag, set the relevant API key in your terminal or environment file (`.env`):

```bash
# Linux / macOS
export GEMINI_API_KEY="your-key-here"
export OPENAI_API_KEY="your-key-here"

# Windows PowerShell
$env:GEMINI_API_KEY="your-key-here"
$env:OPENAI_API_KEY="your-key-here"
```

---

## 🤝 Contributing

Contributions make open source an amazing place to learn, inspire, and create! Any contributions you make are **greatly appreciated**.

Check out our [CONTRIBUTING.md](./CONTRIBUTING.md) for step-by-step guidelines on setting up your environment and opening Pull Requests.

1. **Fork** the Project
2. Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3. Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the Branch (`git push origin feature/AmazingFeature`)
5. Open a **Pull Request**

---

## 📝 License

Distributed under the MIT License. See `LICENSE` for more information.
