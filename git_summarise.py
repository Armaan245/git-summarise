#!/usr/bin/env python3
"""git-summarise – Inspect and summarise recent Git activity from the CLI."""

import argparse
import os
import re
import sys
from datetime import datetime, timezone

import git as gitmodule
from git import Repo, InvalidGitRepositoryError

# SHA of the empty tree – used to diff against for the very first commit.
EMPTY_TREE_SHA = "4b825dc642cb6eb9a060e54bf899d15f3f4b0eab"

# ── ANSI helpers ────────────────────────────────────────────────────────────

BOLD = "\033[1m"
DIM = "\033[2m"
GREEN = "\033[32m"
RED = "\033[31m"
YELLOW = "\033[33m"
CYAN = "\033[36m"
MAGENTA = "\033[35m"
RESET = "\033[0m"

CHANGE_LABELS = {
    "A": f"{GREEN}added{RESET}",
    "D": f"{RED}deleted{RESET}",
    "M": f"{YELLOW}modified{RESET}",
    "R": f"{CYAN}renamed{RESET}",
    "T": f"{MAGENTA}type-changed{RESET}",
    "C": f"{CYAN}copied{RESET}",
}


def _supports_color():
    """Return True if the terminal is likely to support ANSI colours."""
    if os.environ.get("NO_COLOR"):
        return False
    if sys.platform == "win32":
        # Windows Terminal, VS Code, or ANSICON all support ANSI.
        return bool(
            os.environ.get("WT_SESSION")
            or os.environ.get("ANSICON")
            or os.environ.get("TERM_PROGRAM")
        )
    return hasattr(sys.stdout, "isatty") and sys.stdout.isatty()


def _strip_ansi(text):
    """Remove ANSI escape sequences."""
    return re.sub(r"\033\[[0-9;]*m", "", text)


def _disable_colors():
    """Turn off all ANSI formatting globally."""
    global BOLD, DIM, GREEN, RED, YELLOW, CYAN, MAGENTA, RESET, CHANGE_LABELS
    BOLD = DIM = GREEN = RED = YELLOW = CYAN = MAGENTA = RESET = ""
    CHANGE_LABELS = {k: _strip_ansi(v) for k, v in CHANGE_LABELS.items()}


# ── Repository helpers ──────────────────────────────────────────────────────

def open_repo(path="."):
    """Open the Git repository at *path*, searching parent directories."""
    try:
        return Repo(path, search_parent_directories=True)
    except InvalidGitRepositoryError:
        print(f"{RED}Error:{RESET} not inside a Git repository.", file=sys.stderr)
        sys.exit(1)


# ── Commit summary ──────────────────────────────────────────────────────────

def format_commits(repo, count=5):
    """Return a coloured, human-readable summary of the last *count* commits."""
    try:
        commits = list(repo.iter_commits(max_count=count))
    except ValueError:
        # Empty repo – no commits at all.
        return f"  {DIM}(no commits yet){RESET}\n"

    if not commits:
        return f"  {DIM}(no commits yet){RESET}\n"

    blocks = []
    for commit in commits:
        sha = commit.hexsha[:7]
        author = str(commit.author)
        date_str = datetime.fromtimestamp(
            commit.committed_date, tz=timezone.utc,
        ).strftime("%Y-%m-%d %H:%M UTC")
        subject = commit.message.strip().splitlines()[0]

        # Diff against parent (or the empty tree for the initial commit).
        parent = commit.parents[0].hexsha if commit.parents else EMPTY_TREE_SHA
        try:
            diff_index = commit.diff(parent)
        except Exception:
            diff_index = []

        file_lines = []
        for d in diff_index:
            label = CHANGE_LABELS.get(d.change_type, d.change_type)
            path = d.b_path or d.a_path
            file_lines.append(f"      {label}  {path}")

        header = f"  {BOLD}{YELLOW}{sha}{RESET}  {subject}"
        meta = f"  {DIM}{author} · {date_str}{RESET}"
        block = header + "\n" + meta
        if file_lines:
            block += "\n" + "\n".join(file_lines)
        blocks.append(block)

    return "\n\n".join(blocks) + "\n"


# ── Staged-changes summary ─────────────────────────────────────────────────

def format_staged(repo):
    """Return a coloured summary of staged (index) changes."""
    try:
        diff = repo.index.diff("HEAD")
    except gitmodule.exc.BadName:
        # HEAD doesn't exist yet (brand-new repo).
        diff = repo.index.diff(EMPTY_TREE_SHA)

    if not diff:
        return f"  {DIM}(no staged changes){RESET}\n"

    lines = []
    for d in diff:
        label = CHANGE_LABELS.get(d.change_type, d.change_type)
        path = d.b_path or d.a_path
        stat = ""

        # Try to provide a quick +/- line count.
        if d.change_type == "M" and d.a_blob and d.b_blob:
            try:
                a_lines = d.a_blob.data_stream.read().decode(
                    "utf-8", errors="replace"
                ).splitlines()
                b_lines = d.b_blob.data_stream.read().decode(
                    "utf-8", errors="replace"
                ).splitlines()
                added = max(0, len(b_lines) - len(a_lines))
                removed = max(0, len(a_lines) - len(b_lines))
                stat = (
                    f"  {DIM}({GREEN}+{added}{RESET}"
                    f" {RED}-{removed}{RESET}{DIM}){RESET}"
                )
            except Exception:
                pass

        lines.append(f"  {label}  {path}{stat}")

    return "\n".join(lines) + "\n"


# ── Raw diff text (for AI summarisation) ────────────────────────────────────

MAX_PATCH_CHARS = 12_000  # Keep prompt size manageable.


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
                f"── Commit {commit.hexsha[:7]} by {commit.author} "
                f"on {date_str} ──"
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
                    parts.append("(diff too large – stat only)")
            parts.append("")

    if staged:
        cached_stat = repo.git.diff("--cached", "--stat")
        if cached_stat:
            parts.append("── Staged changes ──")
            parts.append(cached_stat)
            cached_patch = repo.git.diff("--cached")
            if len(cached_patch) <= MAX_PATCH_CHARS:
                parts.append(cached_patch)
            else:
                parts.append("(diff too large – stat only)")

    return "\n".join(parts)


# ── AI summarisation via Gemini ─────────────────────────────────────────────

def ai_summarise(raw_diff, api_key):
    """Send *raw_diff* to Gemini and return a natural-language summary."""
    # Import lazily so the dependency is optional at runtime.
    from google import genai  # noqa: E402

    client = genai.Client(api_key=api_key)

    prompt = (
        "You are a senior software engineer reviewing Git changes.\n"
        "Provide a clear, concise summary of the following Git activity.\n"
        "• Group related changes by theme or component.\n"
        "• Call out any potentially breaking or high-impact modifications.\n"
        "• Use bullet points for readability.\n\n"
        f"{raw_diff}"
    )

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
    )
    return response.text


# ── CLI ─────────────────────────────────────────────────────────────────────

def _section(title):
    """Print a formatted section header."""
    bar = "─" * 50
    print(f"\n{BOLD}{bar}{RESET}")
    print(f"  {BOLD}{title}{RESET}")
    print(f"{BOLD}{bar}{RESET}")


def build_parser():
    """Construct and return the :class:`argparse.ArgumentParser`."""
    parser = argparse.ArgumentParser(
        prog="git-summarise",
        description="Summarise recent Git repository activity.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "examples:\n"
            "  git_summarise.py                  "
            "show last 5 commits\n"
            "  git_summarise.py -n 10            "
            "show last 10 commits\n"
            "  git_summarise.py --staged          "
            "show staged changes\n"
            "  git_summarise.py -n 3 --staged     "
            "show last 3 commits + staged changes\n"
            "  git_summarise.py --ai              "
            "AI-powered summary via Gemini\n"
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
        "--ai",
        action="store_true",
        help=(
            "use Gemini AI for a natural-language summary "
            "(requires GEMINI_API_KEY env var)"
        ),
    )
    parser.add_argument(
        "--path",
        default=".",
        metavar="DIR",
        help="path to the Git repository (default: current directory)",
    )
    return parser


def main():
    # Enable ANSI escape sequences on Windows 10+.
    if sys.platform == "win32":
        os.system("")

    if not _supports_color():
        _disable_colors()

    parser = build_parser()
    args = parser.parse_args()

    repo = open_repo(args.path)

    show_commits = args.commits > 0
    show_staged = args.staged

    # ── AI mode ──────────────────────────────────────────────────────────
    if args.ai:
        api_key = os.environ.get("GEMINI_API_KEY", "")
        if not api_key:
            print(
                f"{RED}Error:{RESET} --ai requires the GEMINI_API_KEY "
                "environment variable.",
                file=sys.stderr,
            )
            sys.exit(1)

        raw = _collect_raw_diff(
            repo,
            commits_count=args.commits if show_commits else None,
            staged=show_staged,
        )
        if not raw.strip():
            print("Nothing to summarise.")
            return

        _section("AI-Powered Summary (Gemini)")
        print()
        try:
            print(ai_summarise(raw, api_key))
        except Exception as exc:
            print(
                f"{RED}Error calling Gemini API:{RESET} {exc}",
                file=sys.stderr,
            )
            sys.exit(1)
        return

    # ── Standard mode ────────────────────────────────────────────────────
    if show_commits:
        _section(f"Last {args.commits} Commit(s)")
        print()
        print(format_commits(repo, args.commits))

    if show_staged:
        _section("Staged Changes")
        print()
        print(format_staged(repo))


if __name__ == "__main__":
    main()
