# Contributing to Git Summarise

Thank you for taking the time to contribute to `git-summarise`! 🎉

We welcome contributions of all kinds—whether you are fixing a bug, improving the documentation, suggesting new features, or adding integrations for new AI providers.

---

## 🚀 Quick Start Guide

### 1. Prerequisites
Before getting started, make sure you have:
* **Python 3.10+** installed.
* **Git** installed and added to your system PATH.
* A GitHub account.

---

## 🛠️ Setting Up Your Development Environment

1. **Fork the Repository:**
   Click the **Fork** button at the top-right corner of the [`git-summarise` GitHub repository](https://github.com/Armaan245/git-summarise).

2. **Clone Your Fork:**
   ```bash
   git clone https://github.com/<your-username>/git-summarise.git
   cd git-summarise
   ```

3. **Set Up a Virtual Environment:**
   * **Windows (PowerShell):**
     ```powershell
     python -m venv .venv
     .\.venv\Scripts\Activate.ps1
     ```
   * **Linux / macOS:**
     ```bash
     python3 -m venv .venv
     source .venv/bin/activate
     ```

4. **Install Dependencies & Editable CLI Package:**
   Install the project in "editable" mode so your code changes immediately reflect when running the CLI:
   ```bash
   pip install -e .
   ```

5. **Verify Installation:**
   ```bash
   git-summarise --help
   ```

---

## 🌿 Branching Strategy & Workflow

1. **Sync with Main:**
   Ensure your local `main` branch is up to date:
   ```bash
   git checkout main
   git pull origin main
   ```

2. **Create a Feature Branch:**
   Use a clear naming convention (`feature/`, `bugfix/`, or `docs/`):
   ```bash
   git checkout -b feature/add-ollama-support
   ```

3. **Make Your Changes & Test:**
   Test your CLI changes against sample local repositories to ensure no regressions occur.

4. **Commit Your Changes:**
   Write clear, descriptive commit messages:
   ```bash
   git commit -m "feat: add local Ollama support to --provider option"
   ```

5. **Push to GitHub:**
   ```bash
   git push origin feature/add-ollama-support
   ```

6. **Submit a Pull Request (PR):**
   * Go to your fork on GitHub and click **Compare & pull request**.
   * Provide a clear title and description of the changes you made.
   * Link any related issues (e.g., `Fixes #12`).

---

## 🎯 Good First Issues & Ideas

Looking for ways to contribute? Here are great starting points:
* 🐛 **CLI Bug Fixes:** Fixing help string formatting or output alignment.
* 🤖 **AI Providers:** Adding support for local models (Ollama, LM Studio) or extra cloud providers.
* 📄 **Markdown & PDF Templates:** Improving the visual styling of generated Markdown or PDF exports.
* 🧪 **Testing:** Adding unit tests using `pytest` for repository parsing logic.

---

## 📜 Code Style & Quality

* Keep code clean, readable, and well-commented.
* Use standard Python type hinting where appropriate.
* Handle missing API keys or invalid directory paths gracefully with clear CLI warning messages.

---

## 💬 Questions or Suggestions?

If you run into any problems or have feature requests, feel free to open an issue on the repository's **Issues** tab!

Thank you for helping make `git-summarise` better! 🚀
