#!/usr/bin/env python3
"""git-summarise – Inspect and summarise recent Git activity from the CLI."""

import argparse
import ast
import html
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

import git as gitmodule
from git import Repo, InvalidGitRepositoryError
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table  # Rich Table preserved for CLI rendering
from xhtml2pdf import pisa

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
# Aliased ReportLab Table to prevent collision with Rich Table
from reportlab.platypus import HRFlowable, Paragraph, SimpleDocTemplate, Spacer, Table as RLTable, TableStyle, Preformatted

# SHA of the empty tree – used to diff against for the very first commit.
EMPTY_TREE_SHA = "4b825dc642cb6eb9a060e54bf899d15f3f4b0eab"

TOOL_VERSION = "1.0.0"

# Rich console instance (shared across the module).
console = Console()

# Style mapping for Git change types.
CHANGE_STYLES = {
    "A": ("added", "green"),
    "D": ("deleted", "red"),
    "M": ("modified", "yellow"),
    "R": ("renamed", "cyan"),
    "T": ("type-changed", "magenta"),
    "C": ("copied", "cyan"),
}


# ── Repository helpers ──────────────────────────────────────────────────────

def open_repo(path="."):
    """Open the Git repository at *path*, searching parent directories."""
    try:
        return Repo(path, search_parent_directories=True)
    except InvalidGitRepositoryError:
        console.print("[bold red]Error:[/] not inside a Git repository.")
        sys.exit(1)


# ── Data collection ──────────────────────────────────────────────────────────

def collect_commit_data(repo, count=5):
    """Return a list of dicts describing the last *count* commits."""
    try:
        commits = list(repo.iter_commits(max_count=count))
    except ValueError:
        return []

    results = []
    for commit in commits:
        sha = commit.hexsha[:7]
        author = str(commit.author)
        date_str = datetime.fromtimestamp(
            commit.committed_date, tz=timezone.utc,
        ).strftime("%Y-%m-%d %H:%M UTC")
        subject = commit.message.strip().splitlines()[0]

        parent = commit.parents[0].hexsha if commit.parents else EMPTY_TREE_SHA
        try:
            diff_index = commit.diff(parent)
        except Exception:
            diff_index = []

        files = []
        for d in diff_index:
            label, _ = CHANGE_STYLES.get(d.change_type, (d.change_type, "white"))
            path = d.b_path or d.a_path
            files.append({"type": d.change_type, "label": label, "path": path})

        results.append({
            "sha": sha,
            "author": author,
            "date": date_str,
            "subject": subject,
            "files": files,
        })
    return results


def collect_staged_data(repo):
    """Return a list of dicts describing staged (index) changes."""
    try:
        diff = repo.index.diff("HEAD")
    except gitmodule.exc.BadName:
        diff = repo.index.diff(EMPTY_TREE_SHA)

    results = []
    for d in diff:
        label, _ = CHANGE_STYLES.get(d.change_type, (d.change_type, "white"))
        path = d.b_path or d.a_path

        stat = ""
        if d.change_type == "M" and d.a_blob and d.b_blob:
            try:
                a_lines = d.a_blob.data_stream.read().decode(
                    "utf-8", errors="replace",
                ).splitlines()
                b_lines = d.b_blob.data_stream.read().decode(
                    "utf-8", errors="replace",
                ).splitlines()
                added = max(0, len(b_lines) - len(a_lines))
                removed = max(0, len(a_lines) - len(b_lines))
                stat = f"+{added} -{removed}"
            except Exception:
                pass

        results.append({
            "type": d.change_type,
            "label": label,
            "path": path,
            "stat": stat,
        })
    return results


def _collect_repo_meta(repo, commit_data=None, staged_data=None):
    """Gather lightweight repo metadata for the PDF header / stats bar."""
    try:
        branch = str(repo.active_branch)
    except TypeError:
        branch = "HEAD (detached)"

    try:
        tracked = len(repo.git.ls_files().splitlines())
    except Exception:
        tracked = 0

    ext_counts: dict[str, int] = {}
    try:
        for path in repo.git.ls_files().splitlines():
            ext = Path(path).suffix.lower()
            if ext:
                ext_counts[ext] = ext_counts.get(ext, 0) + 1
    except Exception:
        pass
    top_ext = max(ext_counts, key=ext_counts.get) if ext_counts else "—"
    ext_label_map = {
        ".py": "Python", ".js": "JavaScript", ".ts": "TypeScript",
        ".go": "Go", ".rs": "Rust", ".java": "Java", ".rb": "Ruby",
        ".c": "C", ".cpp": "C++", ".cs": "C#", ".swift": "Swift",
        ".kt": "Kotlin", ".html": "HTML", ".css": "CSS", ".md": "Markdown",
        ".toml": "TOML", ".yaml": "YAML", ".yml": "YAML", ".json": "JSON",
        ".sh": "Shell", ".txt": "Text",
    }
    primary_stack = ext_label_map.get(top_ext, top_ext)

    staged_count = len(staged_data) if staged_data else 0
    try:
        unstaged = len(repo.index.diff(None))
        untracked = len(repo.untracked_files)
    except Exception:
        unstaged = untracked = 0

    if staged_count + unstaged + untracked == 0:
        git_status = "Clean"
    else:
        parts = []
        if staged_count:
            parts.append(f"{staged_count} staged")
        if unstaged:
            parts.append(f"{unstaged} mod")
        if untracked:
            parts.append(f"{untracked} untrk")
        git_status = ", ".join(parts)

    return {
        "branch": branch,
        "tracked_files": tracked,
        "primary_stack": primary_stack,
        "commit_count": len(commit_data) if commit_data else 0,
        "git_status": git_status,
    }


# ── Phase 2: AST Code Inspector & Docs Generator ────────────────────────────

def parse_python_file(file_path):
    """Parse a Python file using AST to extract functions, classes, and docstrings."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            tree = ast.parse(f.read(), filename=str(file_path))
    except Exception:
        return None

    module_info = {
        "file": str(file_path),
        "docstring": ast.get_docstring(tree) or "",
        "classes": [],
        "functions": [],
    }

    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.ClassDef):
            methods = []
            for item in node.body:
                if isinstance(item, ast.FunctionDef):
                    methods.append({
                        "name": item.name,
                        "docstring": ast.get_docstring(item) or "",
                        "args": [arg.arg for arg in item.args.args],
                    })
            module_info["classes"].append({
                "name": node.name,
                "docstring": ast.get_docstring(node) or "",
                "methods": methods,
            })
        elif isinstance(node, ast.FunctionDef):
            module_info["functions"].append({
                "name": node.name,
                "docstring": ast.get_docstring(node) or "",
                "args": [arg.arg for arg in node.args.args],
            })

    return module_info


def generate_docs_suite(repo, output_dir="docs"):
    """Generate a multi-page Markdown documentation suite with visual enhancements."""
    docs_path = Path(repo.working_dir) / output_dir
    docs_path.mkdir(exist_ok=True)

    repo_name = Path(repo.working_dir).name
    try:
        py_files = [
            Path(repo.working_dir) / f 
            for f in repo.git.ls_files().splitlines() 
            if f.endswith(".py")
        ]
    except Exception:
        py_files = []

    parsed_modules = []
    for py_file in py_files:
        if py_file.is_file():
            info = parse_python_file(py_file)
            if info:
                parsed_modules.append(info)

    # ── 1. Visually Enhanced api-reference.md ────────────────────────────────
    api_ref_lines = [
        f"# 📚 API Reference – `{repo_name}`\n",
        "> Auto-generated API documentation extracted via Abstract Syntax Tree (AST) parsing.\n",
    ]

    if not parsed_modules:
        api_ref_lines.append("!!! warning \"No Python Modules Detected\"\n    *(No Python files found in repository)*\n")
    else:
        for mod in parsed_modules:
            try:
                rel_path = Path(mod["file"]).relative_to(repo.working_dir)
            except ValueError:
                rel_path = Path(mod["file"]).name

            api_ref_lines.append(f"## 📄 Module `{rel_path}`\n")
            if mod["docstring"]:
                api_ref_lines.append(f"!!! info \"Module Summary\"\n    {mod['docstring']}\n")

            if mod["classes"]:
                api_ref_lines.append("### 🏛️ Classes\n")
                for cls in mod["classes"]:
                    api_ref_lines.append(f"#### `class {cls['name']}`\n")
                    if cls["docstring"]:
                        api_ref_lines.append(f"*{cls['docstring']}*\n")
                    
                    if cls["methods"]:
                        api_ref_lines.append("| Method | Arguments | Description |")
                        api_ref_lines.append("| :--- | :--- | :--- |")
                        for m in cls["methods"]:
                            args_str = f"`{', '.join(m['args'])}`" if m['args'] else "*none*"
                            desc = m["docstring"] or "—"
                            api_ref_lines.append(f"| `{m['name']}()` | {args_str} | {desc} |")
                        api_ref_lines.append("")

            if mod["functions"]:
                api_ref_lines.append("### ⚙️ Functions\n")
                api_ref_lines.append("| Function | Arguments | Description |")
                api_ref_lines.append("| :--- | :--- | :--- |")
                for fn in mod["functions"]:
                    args_str = f"`{', '.join(fn['args'])}`" if fn['args'] else "*none*"
                    desc = fn["docstring"] or "—"
                    api_ref_lines.append(f"| `{fn['name']}()` | {args_str} | {desc} |")
                api_ref_lines.append("")

    (docs_path / "api-reference.md").write_text("\n".join(api_ref_lines), encoding="utf-8")

    # ── 2. Visually Enhanced architecture.md (with Mermaid Diagram) ─────────
    meta = _collect_repo_meta(repo)
    try:
        file_list = repo.git.ls_files().splitlines()
    except Exception:
        file_list = []

    # Build a Mermaid Graph for repository architecture
    mermaid_lines = ["```mermaid", "graph TD", f"    Root[{repo_name}]"]
    for f in file_list[:15]:  # Limit to top files for clean visual graph
        p = Path(f)
        node_id = re.sub(r'[^a-zA-Z0-9]', '_', f)
        if len(p.parts) > 1:
            parent_id = re.sub(r'[^a-zA-Z0-9]', '_', str(p.parent))
            mermaid_lines.append(f"    {parent_id} --> {node_id}[{p.name}]")
        else:
            mermaid_lines.append(f"    Root --> {node_id}[{p.name}]")
    mermaid_lines.append("```")

    arch_lines = [
        f"# 🏗️ Architecture Overview – `{repo_name}`\n",
        "### 📊 Repository Badges",
        f"- **Primary Tech Stack:** `{meta['primary_stack']}`",
        f"- **Tracked Files:** `{meta['tracked_files']}`",
        f"- **Active Branch:** `{meta['branch']}`\n",
        "---",
        "## 🧩 Visual Repository Diagram\n",
        "\n".join(mermaid_lines),
        "\n---",
        "## 📂 Complete File Tree\n",
        "```text",
        "\n".join(file_list),
        "```",
    ]
    (docs_path / "architecture.md").write_text("\n".join(arch_lines), encoding="utf-8")

    # ── 3. Visually Enhanced getting-started.md ─────────────────────────────
    getting_started_lines = [
        f"# 🚀 Getting Started with `{repo_name}`\n",
        "!!! tip \"Quick Start Tip\"\n    Ensure you have Python 3.9+ and Git installed before setting up the repository.\n",
        "## 📦 Step-by-Step Installation\n",
        "1. **Clone the Repository**",
        "   ```bash",
        "   git clone <repository-url>",
        "   ```\n",
        f"2. **Navigate to Project Root**",
        "   ```bash",
        f"   cd {repo_name}",
        "   ```\n",
        "3. **Install Dependencies**",
        "   ```bash",
        "   pip install -r requirements.txt",
        "   ```\n",
        "---",
        "## 🧭 Quick Links & Navigation\n",
        "| Documentation Guide | Description |",
        "| :--- | :--- |",
        "| 📚 [API Reference](api-reference.md) | Full breakdown of modules, classes, and methods |",
        "| 🏗️ [Architecture Overview](architecture.md) | Visual codebase graph and file hierarchy |",
    ]
    (docs_path / "getting-started.md").write_text("\n".join(getting_started_lines), encoding="utf-8")

    return str(docs_path.resolve())


# ── Rich terminal output ───────────────────────────────────────────────────

def print_commits(commit_data, count):
    """Render commit data to the terminal with Rich panels."""
    if not commit_data:
        console.print(
            Panel("[dim](no commits yet)[/dim]", title="Commits", border_style="blue"),
        )
        return

    table = Table(
        show_header=True,
        header_style="bold cyan",
        border_style="dim",
        title=f"Last {count} Commit(s)",
        title_style="bold",
        expand=True,
        pad_edge=True,
    )
    table.add_column("Hash", style="bold yellow", width=9)
    table.add_column("Message", ratio=3)
    table.add_column("Author", style="dim", ratio=1)
    table.add_column("Date", style="dim", width=20)
    table.add_column("Files", ratio=2)

    for c in commit_data:
        file_parts = []
        for f in c["files"]:
            _, colour = CHANGE_STYLES.get(f["type"], (f["type"], "white"))
            file_parts.append(f"[{colour}]{f['label']}[/] {f['path']}")
        files_str = "\n".join(file_parts) if file_parts else "[dim]-[/dim]"

        table.add_row(c["sha"], c["subject"], c["author"], c["date"], files_str)

    console.print()
    console.print(table)


def print_staged(staged_data):
    """Render staged-changes data to the terminal with Rich."""
    if not staged_data:
        console.print(
            Panel(
                "[dim](no staged changes)[/dim]",
                title="Staged Changes",
                border_style="green",
            ),
        )
        return

    table = Table(
        show_header=True,
        header_style="bold green",
        border_style="dim",
        title="Staged Changes",
        title_style="bold",
        expand=True,
    )
    table.add_column("Status", width=14)
    table.add_column("File", ratio=3)
    table.add_column("Lines", width=12)

    for s in staged_data:
        _, colour = CHANGE_STYLES.get(s["type"], (s["type"], "white"))
        table.add_row(
            f"[{colour}]{s['label']}[/]",
            s["path"],
            s.get("stat", "") or "[dim]-[/dim]",
        )

    console.print()
    console.print(table)


def print_ai_summary(text):
    """Render an AI-generated summary as Markdown inside a Rich panel."""
    md = Markdown(text)
    console.print()
    console.print(
        Panel(
            md,
            title="AI-Powered Summary",
            border_style="magenta",
            padding=(1, 2),
        ),
    )


# ── Raw diff text (for AI summarisation) ────────────────────────────────────

MAX_PATCH_CHARS = 12_000


def _collect_raw_diff(repo, commits_count=None, staged=False):
    """Gather raw diff text suitable for feeding to an LLM."""
    parts: list[str] = []

    if commits_count and commits_count > 0:
        try:
            commits = list(repo.iter_commits(max_count=commits_count))
        except ValueError:
            commits = []

        for commit in commits:
            date_str = datetime.fromtimestamp(
                commit.committed_date, tz=timezone.utc,
            ).strftime("%Y-%m-%d %H:%M UTC")
            parts.append(
                f"-- Commit {commit.hexsha[:7]} by {commit.author} "
                f"on {date_str} --"
            )
            parts.append(f"Message: {commit.message.strip()}")
            if commit.parents:
                stat = repo.git.diff(
                    commit.parents[0].hexsha, commit.hexsha, stat=True,
                )
                parts.append(stat)
                patch = repo.git.diff(
                    commit.parents[0].hexsha, commit.hexsha,
                )
                if len(patch) <= MAX_PATCH_CHARS:
                    parts.append(patch)
                else:
                    parts.append("(diff too large - stat only)")
            parts.append("")

    if staged:
        cached_stat = repo.git.diff("--cached", "--stat")
        if cached_stat:
            parts.append("-- Staged changes --")
            parts.append(cached_stat)
            cached_patch = repo.git.diff("--cached")
            if len(cached_patch) <= MAX_PATCH_CHARS:
                parts.append(cached_patch)
            else:
                parts.append("(diff too large - stat only)")

    return "\n".join(parts)


# ── Multi-Provider AI Summarisation ─────────────────────────────────────────

def ai_summarise(raw_diff, provider="gemini"):
    """Send *raw_diff* to the selected AI provider."""
    prompt = (
        "You are a senior software engineer reviewing Git changes.\n"
        "Provide a clear, concise summary of the following Git activity.\n"
        "* Group related changes by theme or component.\n"
        "* Call out any potentially breaking or high-impact modifications.\n"
        "* Use bullet points for readability.\n\n"
        f"{raw_diff}"
    )

    provider = provider.lower()

    # ── 1. Gemini (Google) ──────────────────────────────────────────────────
    if provider in ("gemini", "google"):
        api_key = os.environ.get("GEMINI_API_KEY", "")
        if not api_key:
            raise ValueError("GEMINI_API_KEY environment variable is not set.")
        from google import genai  # noqa: E402 – lazy import

        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt,
        )
        return response.text

    # ── 2. OpenAI (GPT) ─────────────────────────────────────────────────────
    elif provider in ("gpt", "openai"):
        api_key = os.environ.get("OPENAI_API_KEY", "")
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable is not set.")
        from openai import OpenAI  # noqa: E402 – lazy import

        client = OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
        )
        return response.choices[0].message.content

    # ── 3. Anthropic (Claude) ───────────────────────────────────────────────
    elif provider in ("claude", "anthropic"):
        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable is not set.")
        import anthropic  # noqa: E402 – lazy import

        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model="claude-3-5-haiku-20241022",
            max_tokens=1000,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text

    # ── 4. DeepSeek ─────────────────────────────────────────────────────────
    elif provider == "deepseek":
        api_key = os.environ.get("DEEPSEEK_API_KEY", "")
        if not api_key:
            raise ValueError("DEEPSEEK_API_KEY environment variable is not set.")
        from openai import OpenAI  # noqa: E402 – lazy import

        client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": prompt}],
        )
        return response.choices[0].message.content

    else:
        raise ValueError(
            f"Unsupported provider '{provider}'. Choose from: gemini, gpt, claude, deepseek."
        )


# ── Dark-Themed PDF Generator ──────────────────────────────────────────────────

BG_DARK = colors.HexColor("#0d1117")
CARD_BG = colors.HexColor("#161b22")
BORDER_CLR = colors.HexColor("#30363d")
TEXT_PRIMARY = colors.HexColor("#c9d1d9")
TEXT_MUTED = colors.HexColor("#8b949e")
BLUE_ACCENT = colors.HexColor("#58a6ff")
GREEN_ACCENT = colors.HexColor("#3fb950")
YELLOW_ACCENT = colors.HexColor("#d29222")
RED_ACCENT = colors.HexColor("#f85149")


def _draw_page_decorations(canvas, doc):
    """Draws dark background and fixes the footer at the bottom of every page."""
    canvas.saveState()
    # 1. Fill entire page background
    canvas.setFillColor(BG_DARK)
    canvas.rect(0, 0, doc.pagesize[0], doc.pagesize[1], fill=True, stroke=False)

    # 2. Draw fixed footer text at bottom margin (y = 20)
    canvas.setFillColor(TEXT_MUTED)
    canvas.setFont("Helvetica", 8)
    footer_text = "Generated automatically via git-summarise --pdf"
    canvas.drawCentredString(doc.pagesize[0] / 2.0, 20, footer_text)

    canvas.restoreState()


def _export_pdf(
    output_path,
    repo,
    commit_data=None,
    staged_data=None,
    ai_text=None,
    commits_requested=5,
):
    """Render a GitHub-dark PDF report using ReportLab Flowables."""
    repo_name = Path(repo.working_dir).name
    meta = _collect_repo_meta(repo, commit_data, staged_data)
    date_str = datetime.now().strftime("%B %d, %Y")

    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        leftMargin=36,
        rightMargin=36,
        topMargin=36,
        bottomMargin=45,  # Reserved space so story content doesn't overlap footer
    )

    styles = getSampleStyleSheet()

    # Typography Styles
    title_style = ParagraphStyle(
        "HeaderTitle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=15,
        leading=18,
        textColor=BLUE_ACCENT,
    )
    badge_style = ParagraphStyle(
        "BadgeText",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8,
        leading=10,
        textColor=TEXT_MUTED,
    )
    stat_val_style = ParagraphStyle(
        "StatVal",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=10,
        leading=12,
        alignment=1,
        textColor=BLUE_ACCENT,
    )
    stat_lbl_style = ParagraphStyle(
        "StatLbl",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=7,
        leading=9,
        alignment=1,
        textColor=TEXT_MUTED,
    )
    h2_style = ParagraphStyle(
        "SectionH2",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=11,
        leading=14,
        textColor=colors.HexColor("#f0f6fc"),
        spaceBefore=10,
        spaceAfter=4,
    )
    body_style = ParagraphStyle(
        "BodyDark",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8.5,
        leading=11,
        textColor=TEXT_PRIMARY,
    )

    story = []

    # ── 1. Header Card ────────────────────────────────────────────────────────
    header_title = Paragraph(f"📦 <b>{repo_name}</b> <font color='#8b949e'>/ repository-report</font>", title_style)
    badges = Paragraph(
        f"<font color='#3fb950'><b>Branch:</b> {meta['branch']}</font> &nbsp;&nbsp;|&nbsp;&nbsp; "
        f"<b>Generated:</b> {date_str} &nbsp;&nbsp;|&nbsp;&nbsp; "
        f"<b>Tool:</b> git-summarise PDF v1.0",
        badge_style,
    )

    header_table = RLTable([[header_title], [Spacer(1, 2)], [badges]], colWidths=[523])
    header_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), CARD_BG),
        ('BOX', (0, 0), (-1, -1), 1, BORDER_CLR),
        ('PADDING', (0, 0), (-1, -1), 8),
    ]))
    story.append(header_table)
    story.append(Spacer(1, 8))

    # ── 2. Stat Cards Grid ───────────────────────────────────────────────────
    c1 = [Paragraph(str(meta['tracked_files']), stat_val_style), Paragraph("TOTAL FILES", stat_lbl_style)]
    c2 = [Paragraph(str(meta['primary_stack']), stat_val_style), Paragraph("PRIMARY STACK", stat_lbl_style)]
    c3 = [Paragraph(str(meta['commit_count']), stat_val_style), Paragraph(f"COMMITS ({commits_requested})", stat_lbl_style)]

    status_val_style = ParagraphStyle("StatusVal", parent=stat_val_style, textColor=GREEN_ACCENT)
    c4 = [Paragraph(str(meta['git_status']), status_val_style), Paragraph("GIT STATUS", stat_lbl_style)]

    stats_table = RLTable([[c1, c2, c3, c4]], colWidths=[130, 130, 130, 133])
    stats_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), CARD_BG),
        ('BOX', (0, 0), (-1, -1), 1, BORDER_CLR),
        ('INNERGRID', (0, 0), (-1, -1), 1, BORDER_CLR),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(stats_table)
    story.append(Spacer(1, 10))

    # ── 3. Commits Section ───────────────────────────────────────────────────
    if commit_data is not None:
        story.append(Paragraph("Recent Activity", h2_style))
        story.append(HRFlowable(width="100%", thickness=1, color=BORDER_CLR, spaceAfter=6))

        if not commit_data:
            story.append(Paragraph("<i>(no commits yet)</i>", body_style))
        else:
            for c in commit_data:
                sha_p = Paragraph(f"<font color='#d29222'><b>{c['sha']}</b></font> &nbsp;&nbsp; <b>{c['subject']}</b>", body_style)
                meta_p = Paragraph(f"<font color='#8b949e'>{c['author']} &bull; {c['date']}</font>", badge_style)

                card_content = [[sha_p], [meta_p]]
                for f in c["files"]:
                    clr = "#3fb950" if f["type"] == "A" else ("#f85149" if f["type"] == "D" else "#d29222")
                    file_p = Paragraph(f"<font color='{clr}'><b>{f['label']}</b></font> &nbsp; <font face='Courier' color='#c9d1d9'>{f['path']}</font>", body_style)
                    card_content.append([file_p])

                commit_card = RLTable(card_content, colWidths=[503])
                commit_card.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, -1), CARD_BG),
                    ('BOX', (0, 0), (-1, -1), 1, BORDER_CLR),
                    ('PADDING', (0, 0), (-1, -1), 6),
                ]))
                story.append(commit_card)
                story.append(Spacer(1, 6))

    # ── 4. Staged Changes Section ────────────────────────────────────────────
    if staged_data is not None:
        story.append(Paragraph("Staged Changes", h2_style))
        story.append(HRFlowable(width="100%", thickness=1, color=BORDER_CLR, spaceAfter=6))

        if not staged_data:
            story.append(Paragraph("<i>(no staged changes)</i>", body_style))
        else:
            rows = [[
                Paragraph("<b>Status</b>", badge_style),
                Paragraph("<b>File</b>", badge_style),
                Paragraph("<b>Lines</b>", badge_style)
            ]]
            for s in staged_data:
                clr = "#3fb950" if s["type"] == "A" else ("#f85149" if s["type"] == "D" else "#d29222")
                lbl = Paragraph(f"<font color='{clr}'><b>{s['label']}</b></font>", body_style)
                path_p = Paragraph(f"<font face='Courier'>{s['path']}</font>", body_style)
                stat_p = Paragraph(f"<font color='#8b949e'>{s.get('stat', '') or '—'}</font>", body_style)
                rows.append([lbl, path_p, stat_p])

            staged_table = RLTable(rows, colWidths=[80, 323, 100])
            staged_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), CARD_BG),
                ('BOX', (0, 0), (-1, -1), 1, BORDER_CLR),
                ('LINEBELOW', (0, 0), (-1, 0), 1, BORDER_CLR),
                ('PADDING', (0, 0), (-1, -1), 6),
            ]))
            story.append(staged_table)
            story.append(Spacer(1, 8))

    # ── 5. AI Overview Section ───────────────────────────────────────────────
    if ai_text:
        story.append(Paragraph("AI-Powered Overview", h2_style))
        story.append(HRFlowable(width="100%", thickness=1, color=BORDER_CLR, spaceAfter=6))

        ai_p = Paragraph(ai_text.replace("\n", "<br/>"), body_style)
        ai_table = RLTable([[ai_p]], colWidths=[503])
        ai_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), CARD_BG),
            ('BOX', (0, 0), (-1, -1), 1, BORDER_CLR),
            ('PADDING', (0, 0), (-1, -1), 8),
        ]))
        story.append(ai_table)

    # Build document using canvas decorations for background and locked footer
    doc.build(story, onFirstPage=_draw_page_decorations, onLaterPages=_draw_page_decorations)
    return str(Path(output_path).resolve())


# ── Markdown-to-PDF Conversion Helpers ─────────────────────────────────────

def _convert_md_to_pdf_story(md_text, styles):
    """Convert basic Markdown elements (including tables) into ReportLab Flowables."""
    story = []

    h1_style = ParagraphStyle("MD_H1", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=14, leading=17, textColor=BLUE_ACCENT, spaceBefore=10, spaceAfter=6)
    h2_style = ParagraphStyle("MD_H2", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=11, leading=14, textColor=colors.HexColor("#f0f6fc"), spaceBefore=8, spaceAfter=4)
    h3_style = ParagraphStyle("MD_H3", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=9.5, leading=12, textColor=YELLOW_ACCENT, spaceBefore=6, spaceAfter=2)
    body_style = ParagraphStyle("MD_Body", parent=styles["Normal"], fontName="Helvetica", fontSize=8.5, leading=11, textColor=TEXT_PRIMARY)
    quote_style = ParagraphStyle("MD_Quote", parent=styles["Normal"], fontName="Helvetica-Oblique", fontSize=8.5, leading=11, textColor=TEXT_MUTED, leftIndent=12)
    code_style = ParagraphStyle("MD_Code", parent=styles["Normal"], fontName="Courier", fontSize=7.5, leading=9.5, textColor=GREEN_ACCENT)
    hdr_table_style = ParagraphStyle("MD_TblHdr", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=8, leading=10, textColor=BLUE_ACCENT)

    lines = md_text.splitlines()
    in_code_block = False
    code_buffer = []

    i = 0
    while i < len(lines):
        line = lines[i]
        raw_line = line.strip()

        # Handle Code Blocks
        if raw_line.startswith("```"):
            if in_code_block:
                code_text = "\n".join(code_buffer)
                p = Preformatted(code_text, code_style)
                tbl = RLTable([[p]], colWidths=[503])
                tbl.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, -1), CARD_BG),
                    ('BOX', (0, 0), (-1, -1), 1, BORDER_CLR),
                    ('PADDING', (0, 0), (-1, -1), 6),
                ]))
                story.append(tbl)
                story.append(Spacer(1, 4))
                code_buffer = []
                in_code_block = False
            else:
                in_code_block = True
            i += 1
            continue

        if in_code_block:
            code_buffer.append(line)
            i += 1
            continue

        if not raw_line:
            i += 1
            continue

        # ── Parse Markdown Tables ──────────────────────────────────────────
        if raw_line.startswith("|"):
            table_rows = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                row_str = lines[i].strip()
                # Skip divider rows like | :--- | :--- |
                if not re.match(r'^\|[\s:\|-]+\|$', row_str):
                    cells = [c.strip() for c in row_str.strip("|").split("|")]
                    table_rows.append(cells)
                i += 1

            if table_rows:
                formatted_data = []
                for row_idx, row in enumerate(table_rows):
                    formatted_row = []
                    for cell in row:
                        style_to_use = hdr_table_style if row_idx == 0 else body_style
                        formatted_row.append(Paragraph(cell, style_to_use))
                    formatted_data.append(formatted_row)

                # Determine column widths dynamically
                col_count = len(table_rows[0])
                col_w = 503 / col_count if col_count > 0 else 503

                rl_tbl = RLTable(formatted_data, colWidths=[col_w] * col_count)
                rl_tbl.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, -1), CARD_BG),
                    ('BOX', (0, 0), (-1, -1), 1, BORDER_CLR),
                    ('INNERGRID', (0, 0), (-1, -1), 1, BORDER_CLR),
                    ('LINEBELOW', (0, 0), (-1, 0), 1, BLUE_ACCENT),
                    ('PADDING', (0, 0), (-1, -1), 5),
                ]))
                story.append(rl_tbl)
                story.append(Spacer(1, 6))
            continue

        # Headers & Formatting
        if raw_line.startswith("# "):
            story.append(Paragraph(f"<b>{raw_line[2:]}</b>", h1_style))
            story.append(HRFlowable(width="100%", thickness=1, color=BORDER_CLR, spaceAfter=6))
        elif raw_line.startswith("## "):
            story.append(Paragraph(f"<b>{raw_line[3:]}</b>", h2_style))
        elif raw_line.startswith("### "):
            story.append(Paragraph(f"<b>{raw_line[4:]}</b>", h3_style))
        elif raw_line.startswith(">"):
            story.append(Paragraph(raw_line[1:].strip(), quote_style))
            story.append(Spacer(1, 2))
        elif raw_line.startswith("- ") or raw_line.startswith("* "):
            story.append(Paragraph(f"• {raw_line[2:]}", body_style))
        elif raw_line == "---":
            story.append(HRFlowable(width="100%", thickness=1, color=BORDER_CLR, spaceBefore=4, spaceAfter=6))
        else:
            story.append(Paragraph(raw_line, body_style))
            story.append(Spacer(1, 2))

        i += 1

    return story


def export_docs_to_pdf(docs_dir):
    """Converts generated Markdown files in docs_dir into GitHub-Dark PDFs."""
    docs_path = Path(docs_dir)
    md_files = list(docs_path.glob("*.md"))
    generated_pdfs = []

    styles = getSampleStyleSheet()

    for md_file in md_files:
        pdf_file = md_file.with_suffix(".pdf")
        md_content = md_file.read_text(encoding="utf-8")

        doc = SimpleDocTemplate(
            str(pdf_file),
            pagesize=A4,
            leftMargin=36,
            rightMargin=36,
            topMargin=36,
            bottomMargin=45,
        )

        story = _convert_md_to_pdf_story(md_content, styles)
        doc.build(story, onFirstPage=_draw_page_decorations, onLaterPages=_draw_page_decorations)
        generated_pdfs.append(str(pdf_file.name))

    return generated_pdfs


# ── CLI ─────────────────────────────────────────────────────────────────────

def build_parser():
    """Construct and return the :class:`argparse.ArgumentParser`."""
    parser = argparse.ArgumentParser(
        prog="git-summarise",
        description="Summarise recent Git repository activity.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "examples:\n"
            "  git-summarise.py                           show last 5 commits\n"
            "  git-summarise.py -n 10                     show last 10 commits\n"
            "  git-summarise.py --staged                  show staged changes\n"
            "  git-summarise.py --docs                    generate /docs Markdown suite\n"
            "  git-summarise.py --docs --pdf              generate /docs Markdown + PDF suite\n"
            "  git-summarise.py --ai                      AI summary (default: gemini)\n"
            "  git-summarise.py --ai --provider gpt       AI summary via GPT-4o-mini\n"
            "  git-summarise.py --pdf                     export a PDF report\n"
            "  git-summarise.py --pdf --out report.pdf    export to a custom path\n"                                      
        ),
    )
    parser.add_argument(
        "-n", "--commits",
        type=int,
        default=5,
        metavar="N",
        help="number of recent commits to summarise (default: 5)",
    )
    parser.add_argument(
        "-s", "--staged",
        action="store_true",
        help="include staged (index) changes in the summary",
    )
    parser.add_argument(
        "--docs",
        action="store_true",
        help="generate a multi-page Markdown documentation suite in /docs",
    )
    parser.add_argument(
        "--ai",
        action="store_true",
        help="use AI for a natural-language summary",
    )
    parser.add_argument(
        "--provider",
        type=str,
        default="gemini",
        choices=["gemini", "gpt", "claude", "deepseek"],
        help="AI provider for summary (default: gemini)",
    )
    parser.add_argument(
        "--pdf",
        action="store_true",
        help="export the summary or documentation suite as styled PDF report(s)",
    )
    parser.add_argument(
        "--out",
        type=str,
        default="git_summary.pdf",
        metavar="FILE",
        help="output path for the PDF report (default: git_summary.pdf)",
    )
    parser.add_argument(
        "--path",
        default=".",
        metavar="DIR",
        help="path to the Git repository (default: current directory)",
    )
    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    repo = open_repo(args.path)

    # ── Check for Phase 2 Docs Generation Flag ──────────────────────────────
    if args.docs:
        with console.status("[cyan]Parsing codebase and generating documentation suite...[/]"):
            out_docs = generate_docs_suite(repo)

            pdf_msg = ""
            if args.pdf:
                created_pdfs = export_docs_to_pdf(out_docs)
                pdf_list_str = "\n".join([f" • [yellow]docs/{pdf}[/yellow]" for pdf in created_pdfs])
                pdf_msg = f"\n\nPDF Documentation Manuals:\n{pdf_list_str}"

        console.print(
            Panel(
                f"[green]Documentation suite generated successfully in:[/green]\n[bold]{out_docs}[/bold]\n\n"
                f"Generated Markdown files:\n"
                f" • [cyan]docs/api-reference.md[/cyan]\n"
                f" • [cyan]docs/architecture.md[/cyan]\n"
                f" • [cyan]docs/getting-started.md[/cyan]"
                f"{pdf_msg}",
                border_style="green",
                title="Docs Suite Expansion",
            )
        )
        return

    show_commits = args.commits > 0
    show_staged = args.staged

    commit_data = collect_commit_data(repo, args.commits) if show_commits else None
    staged_data = collect_staged_data(repo) if show_staged else None
    ai_text = None

    if args.ai:
        raw = _collect_raw_diff(
            repo,
            commits_count=args.commits if show_commits else None,
            staged=show_staged,
        )
        if not raw.strip():
            console.print("[dim]Nothing to summarise.[/dim]")
            return

        try:
            with console.status(f"[magenta]Generating AI summary via {args.provider}...[/]"):
                ai_text = ai_summarise(raw, provider=args.provider)
        except Exception as exc:
            console.print(f"[bold yellow]Warning:[/] Could not generate AI summary ({exc}). Proceeding without AI text.")
            ai_text = None  # PDF will still render commit details & staged stats

    if args.pdf:
        out_path = _export_pdf(
            output_path=args.out,
            repo=repo,
            commit_data=commit_data,
            staged_data=staged_data,
            ai_text=ai_text,
            commits_requested=args.commits,
        )
        console.print(
            Panel(
                f"[green]PDF report saved to:[/green]  [bold]{out_path}[/bold]",
                border_style="green",
            ),
        )

    if ai_text:
        print_ai_summary(ai_text)
    else:
        if show_commits:
            print_commits(commit_data, args.commits)
        if show_staged:
            print_staged(staged_data)


if __name__ == "__main__":
    main()