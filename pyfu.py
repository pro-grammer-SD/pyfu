#!/usr/bin/env python3
"""pyfu (Python Fixer Upper) v0.1.0
Aggressive, deterministic, hash-based, loop-safe, brutally honest Python repair tool.
"""

import ast
import hashlib
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

# -----------------------------------------------------------------------------
# DEPENDENCY CHECKS
# -----------------------------------------------------------------------------
try:
    import typer
    from rich.console import Console
    from rich.panel import Panel
    from rich.theme import Theme
    from watchdog.events import FileSystemEventHandler
    from watchdog.observers import Observer
except ImportError:
    sys.exit(1)

# -----------------------------------------------------------------------------
# CONFIGURATION & CONSTANTS
# -----------------------------------------------------------------------------
STATE_FILE = ".pyfu_state.json"

# Rich Console Setup
custom_theme = Theme(
    {
        "info": "cyan",
        "warning": "yellow",
        "error": "bold red",
        "success": "bold green",
        "change": "magenta",
    }
)
console = Console(theme=custom_theme)

# Tools Configuration
TOOLS = {
    "isort": ["isort", "--profile", "black", "--quiet"],
    "pyupgrade": ["pyupgrade", "--py311-plus"],
    "autopep8": [
        "autopep8",
        "--in-place",
        "--aggressive",
        "--aggressive",
        "--aggressive",
        "-aaa",
    ],
    "ruff": [
        "ruff",
        "check",
        "--fix",
        "--unsafe-fixes",
        "--select",
        "ALL",
        "--ignore",
        "ANN",
        "--quiet",
    ],
    "black": ["black", "--quiet"],
    "bandit": ["bandit", "-c", "pyproject.toml", "-r", "-q", "-ll"],
    "pylint": ["pylint", "--errors-only", "--rcfile=pyproject.toml"],
}

app = typer.Typer(add_completion=False)

# -----------------------------------------------------------------------------
# STATE MANAGEMENT
# -----------------------------------------------------------------------------


class StateManager:
    """Manages the .pyfu_state.json file for content hashing."""

    def __init__(self):
        self.path = Path(STATE_FILE)
        self.state: dict[str, str] = self._load()

    def _load(self) -> dict[str, str]:
        if not self.path.exists():
            return {}
        try:
            with open(self.path) as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return {}

    def save(self):
        """Atomic save."""
        temp_path = self.path.with_suffix(".tmp")
        try:
            with open(temp_path, "w") as f:
                json.dump(self.state, f, indent=2)
            temp_path.replace(self.path)
        except OSError:
            pass

    def get_hash(self, file_path: str) -> str | None:
        return self.state.get(file_path)

    def update_hash(self, file_path: str, content_hash: str):
        self.state[file_path] = content_hash
        self.save()


# Global State
state_manager = StateManager()

# -----------------------------------------------------------------------------
# HEURISTIC REPAIR ENGINE
# -----------------------------------------------------------------------------


class SyntaxSurgeon:
    """Performs regex-based surgery on code that fails AST parsing.
    Goal: Make it parseable so tools like Black/Ruff can take over.
    """

    BLOCK_START_KEYWORDS = {
        "def",
        "class",
        "if",
        "elif",
        "else",
        "for",
        "while",
        "try",
        "except",
        "finally",
        "with",
        "async def",
        "async for",
        "async with",
        "match",
        "case",
    }

    @staticmethod
    def fix_colons(lines: list[str]) -> list[str]:
        """Ensures block statements end with a colon."""
        fixed = []
        for line in lines:
            stripped = line.strip()
            # Skip empty
            if not stripped:
                fixed.append(line)
                continue

            first_word = stripped.split(" ")[0]

            # Heuristic: If it starts with a keyword, isn't a variable
            # assignment, and missing colon
            if first_word in SyntaxSurgeon.BLOCK_START_KEYWORDS:
                if (
                    not stripped.endswith(":")
                    and not stripped.endswith("\\")
                    and not stripped.endswith("(")
                ):
                    # Avoid accidentally adding colons to variable names like "class_ = 1"
                    # Simple check: if there is an '=' before the end, likely assignment (unless 'if x == y')
                    # This is imperfect but statistical.
                    if (
                        "=" in stripped
                        and "==" not in stripped
                        and "<=" not in stripped
                        and ">=" not in stripped
                        and "!=" not in stripped
                    ):
                        fixed.append(line)
                    else:
                        fixed.append(line + ":")
                    continue
            fixed.append(line)
        return fixed

    @staticmethod
    def fix_indentation(lines: list[str]) -> list[str]:
        """Aggressively rebuilds indentation based on block depth.
        Replaces 'IndentationError: unexpected indent' by forcing logic.
        """
        fixed = []
        depth = 0
        indent_str = "    "

        for line in lines:
            stripped = line.strip()
            if not stripped:
                fixed.append("")
                continue

            # Handle dedent keywords (elif, else, etc)
            if stripped.startswith(
                ("elif ", "elif:", "else:", "except ", "except:", "finally:")
            ):
                temp_depth = max(0, depth - 1)
            else:
                temp_depth = depth

            # Apply Indent
            fixed.append((indent_str * temp_depth) + stripped)

            # Calculate depth for NEXT line
            # Naive: Ends with colon -> indent next line
            if stripped.endswith(":"):
                depth += 1

            # Simple Pass/Return/Break dedent heuristic
            # This resets depth if we see a terminator.
            # While valid Python allows code after, it's usually a dedent point
            # in broken code.
            if (
                stripped.startswith(("return", "break", "raise", "continue", "pass"))
                and depth > 0
            ):
                # We don't force dedent here because Python allows 'if x: return; print(y)'
                # inside the block. But for auto-repairing garbage indentation,
                # maintaining depth is safer. We rely on autopep8 to dedent if
                # logically required.
                pass

        return fixed

    @staticmethod
    def balance_brackets(content: str) -> str:
        """Attempts to close unclosed parentheses/brackets per line to satisfy parser."""
        lines = content.splitlines()
        fixed_lines = []

        for line in lines:
            opens = {"(": ")", "[": "]", "{": "}"}
            stack = []
            for char in line:
                if char in opens:
                    stack.append(opens[char])
                elif char in opens.values():
                    if stack and stack[-1] == char:
                        stack.pop()

            if stack:
                fixed_lines.append(line + "".join(reversed(stack)))
            else:
                fixed_lines.append(line)

        return "\n".join(fixed_lines)

    @staticmethod
    def operate(content: str) -> str:
        """Run the full surgery suite."""
        lines = content.splitlines()

        # 1. Colon Injection
        lines = SyntaxSurgeon.fix_colons(lines)

        # 2. Indentation Recovery (Rebuilds structure from 0)
        lines = SyntaxSurgeon.fix_indentation(lines)

        # 3. Bracket Balancing
        content = "\n".join(lines)
        return SyntaxSurgeon.balance_brackets(content)


# -----------------------------------------------------------------------------
# CORE LOGIC
# -----------------------------------------------------------------------------


def calculate_hash(content: str) -> str:
    """Returns SHA-256 hash of content."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def check_dependencies():
    """Verifies external tools exist."""
    missing = []
    for tool in ["isort", "autopep8", "black", "ruff", "pyupgrade", "bandit", "pylint"]:
        if not shutil.which(tool):
            missing.append(tool)

    if missing:
        console.print(
            Panel(
                f"❌ Missing external tools: {
                    ', '.join(missing)}\nPlease install them via pip.",
                title="Environment Check",
                border_style="red",
            )
        )
        sys.exit(1)


def is_syntax_valid(content: str) -> bool:
    """Parses AST to check syntax validity.
    NEVER CRASHES. Returns False on any error.
    """
    try:
        ast.parse(content)
        return True
    except Exception:
        # Catching Exception is necessary here because ast.parse can raise
        # SyntaxError, IndentationError, ValueError (null bytes), and
        # TokenError (from internal tokenizer).
        # We don't care *why* it failed, only that it is invalid.
        return False


def generate_tests_for_file(file_path: Path):
    """Generates a test file with skeletons for public functions."""
    if file_path.name.startswith("test_"):
        return

    try:
        content = file_path.read_text(encoding="utf-8")
        tree = ast.parse(content)
    except Exception:
        return

    functions = [
        node.name
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and not node.name.startswith("_")
    ]

    if not functions:
        return

    test_file = file_path.parent / f"test_{file_path.name}"

    existing_tests = set()
    if test_file.exists():
        try:
            test_tree = ast.parse(test_file.read_text(encoding="utf-8"))
            existing_tests = {
                node.name
                for node in ast.walk(test_tree)
                if isinstance(node, ast.FunctionDef)
            }
        except BaseException:
            pass

    new_tests = []
    header_needed = not test_file.exists()

    for func in functions:
        test_name = f"test_{func}"
        if test_name not in existing_tests:
            new_tests.append(
                f"\ndef {test_name}():\n    # TODO: Test for {func}\n    assert True\n"
            )

    if new_tests:
        mode = "a" if test_file.exists() else "w"
        with open(test_file, mode, encoding="utf-8") as f:
            if header_needed:
                f.write("import pytest\nfrom . import " + file_path.stem + "\n")
            f.writelines(new_tests)
        console.print(f"🧪 Generated tests for [bold]{file_path.name}[/bold]")


def repair_pipeline(file_path: Path, run_tools: bool = True) -> bool:
    """The aggressive repair pipeline.
    Returns True if file was modified (written to disk), False otherwise.
    """
    s_path = str(file_path)

    # 1. READ
    try:
        original_content = file_path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        console.print(f"⚠️  Skipping binary/unreadable: {s_path}", style="warning")
        return False
    except Exception as e:
        console.print(f"❌ Read Error {s_path}: {e}", style="error")
        return False

    # 2. HASH CHECK (Pre-flight)
    current_hash = calculate_hash(original_content)
    stored_hash = state_manager.get_hash(s_path)

    if current_hash == stored_hash:
        return False  # No-op protection

    working_content = original_content

    # 3. NORMALIZE (Tabs -> Spaces)
    if "\t" in working_content:
        working_content = working_content.replace("\t", "    ")

    # 4. SYNTAX CHECK & SURGERY
    if not is_syntax_valid(working_content):
        # Syntax is broken. We MUST fix it before tools like Black will work.
        # console.print(f"😷 Applying surgery to broken file: {s_path}", style="dim")
        working_content = SyntaxSurgeon.operate(working_content)

    # 5. EXTERNAL TOOLS
    # Write to disk temporarily so tools can see it
    try:
        file_path.write_text(working_content, encoding="utf-8")
    except Exception:
        return False

    if run_tools:
        # 5a. Ruff (Structure & Imports)
        subprocess.run(TOOLS["ruff"] + [s_path], check=False, capture_output=True)

        # 5b. Autopep8 (Formatting & Aggressive Indent Fixes)
        subprocess.run(TOOLS["autopep8"] + [s_path], check=False, capture_output=True)

        # 5c. PyUpgrade (Modernize)
        subprocess.run(TOOLS["pyupgrade"] + [s_path], check=False, capture_output=True)

        # 5d. ISort
        subprocess.run(TOOLS["isort"] + [s_path], check=False, capture_output=True)

        # 5e. Black (Final Standardizer)
        subprocess.run(TOOLS["black"] + [s_path], check=False, capture_output=True)

    # 6. READ BACK
    try:
        final_content = file_path.read_text(encoding="utf-8")
    except Exception:
        return False

    final_hash = calculate_hash(final_content)

    # 7. FINAL DECISION
    changes_made = final_hash != stored_hash

    if changes_made:
        # Validate syntax one last time
        valid = is_syntax_valid(final_content)

        if not valid:
            console.print(
                f"💥 Repair FAILED (Syntax Still Broken): [bold red]{s_path}[/bold red]"
            )
            # Update hash to prevent infinite loops on the same broken file
            state_manager.update_hash(s_path, final_hash)
            return True

        state_manager.update_hash(s_path, final_hash)
        console.print(f"🔧 Repaired: [bold green]{s_path}[/bold green]")
        return True
    # Sync state if external change happened but resulted in same logic
    if current_hash != stored_hash:
        state_manager.update_hash(s_path, current_hash)
    return False


# -----------------------------------------------------------------------------
# WATCH MODE
# -----------------------------------------------------------------------------


class PyFuHandler(FileSystemEventHandler):
    def __init__(self, generate_tests: bool):
        self.last_event: dict[str, float] = {}
        self.generate_tests = generate_tests

    def on_modified(self, event):
        if event.is_directory or not event.src_path.endswith(".py"):
            return

        # Debounce (1s)
        now = time.time()
        last = self.last_event.get(event.src_path, 0)
        if now - last < 1.0:
            return

        self.last_event[event.src_path] = now

        # Loop Safety Check
        try:
            with open(event.src_path, encoding="utf-8") as f:
                content = f.read()
            current_hash = calculate_hash(content)
            stored_hash = state_manager.get_hash(event.src_path)

            if current_hash == stored_hash:
                return
        except Exception:
            pass

        # Process
        path = Path(event.src_path)
        try:
            changed = repair_pipeline(path)

            if self.generate_tests and (
                changed or not state_manager.get_hash(event.src_path)
            ):
                generate_tests_for_file(path)
        except Exception as e:
            # Catch unexpected crashes in pipeline to keep watcher alive
            console.print(f"🔥 Critical Error processing {path}: {e}", style="error")


# -----------------------------------------------------------------------------
# CLI COMMANDS
# -----------------------------------------------------------------------------


@app.command()
def main(
    path: Path = typer.Argument(..., help="Path to file or directory", exists=True),
    watch: bool = typer.Option(False, "--watch", help="Enable watch mode"),
    generate_tests: bool = typer.Option(
        False, "--generate-tests", help="Generate missing tests"
    ),
    recursive: bool = typer.Option(
        True, "--recursive/--no-recursive", help="Process directories recursively"
    ),
):
    """pyfu: Aggressive Python Fix Utility."""
    check_dependencies()

    target_files: list[Path] = []

    if path.is_file():
        if path.suffix == ".py":
            target_files.append(path)
    elif recursive:
        target_files = list(path.rglob("*.py"))
    else:
        target_files = list(path.glob("*.py"))

    # Exclude venv and hidden
    target_files = [
        p
        for p in target_files
        if ".venv" not in p.parts
        and ".git" not in p.parts
        and "__pycache__" not in p.parts
    ]

    # Initial Run
    if not watch:
        changes_count = 0
        for p in target_files:
            if repair_pipeline(p):
                changes_count += 1
                if generate_tests:
                    generate_tests_for_file(p)

        sys.exit(0 if changes_count == 0 else 0)

    # Watch Mode
    else:
        console.print(Panel(f"👀 Watching [bold]{path}[/bold]", border_style="blue"))

        # Initial scan to sync state
        for p in target_files:
            repair_pipeline(p)
            if generate_tests:
                generate_tests_for_file(p)

        observer = Observer()
        handler = PyFuHandler(generate_tests=generate_tests)

        observer.schedule(handler, str(path), recursive=recursive)
        observer.start()

        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            observer.stop()
            console.print("\n🛑 Watch mode stopped.")

        observer.join()


if __name__ == "__main__":
    app()
    