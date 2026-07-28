# Git Summarise 🚀

A Python CLI tool that scans a Git repository, generates clean Markdown documentations, and exports them to PDF reports.

---

## 📦 Prerequisites

* **Python 3.10+**
* **Git** installed and added to your System PATH

---

## ⚡ Installation

Install directly from GitHub using `pip`:

```bash
pip install git+[https://github.com/Armaan245/git-summarise.git](https://github.com/Armaan245/git-summarise.git)
```

> **Note for Windows Users:**  
> Make sure Python and its `Scripts` directory are added to your system environment variables (`PATH`). If `git-summarise` is not recognized, run:
> ```powershell
> python -m pip install git+[https://github.com/Armaan245/git-summarise.git](https://github.com/Armaan245/git-summarise.git)
> ```

---

## 🛠️ Usage

Run the tool inside any Git repository folder:

```bash
# Generate Markdown summaries
git-summarise

# Generate Markdown summaries AND export to PDF
git-summarise --pdf
```

---

## ⚙️ Configuration & Features

* **Ignores Dependencies Automatically:** Automatically ignores heavy directories like `node_modules`, `venv`, `.dart_tool`, and `.git` to keep report sizes lightweight.
* **Custom Output:** Generates reports directly in your project's `docs/` directory.

---

## 🤝 Contributing & Feedback

If you run into PDF layout issues or execution errors, feel free to open an issue or submit a Pull Request!
