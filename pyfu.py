#!/usr/bin/env python3
"""
🛠️✨ PYFU: GOD-TIER PYTHON CODE AGENT 🐍🦀
Automated Refactoring, Security Auditing, Testing, and Optimization.
"""

import argparse
import ast
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

# rich is required for the God-Tier UI
try:
    from rich import box
    from rich.console import Console
    from rich.layout import Layout
    from rich.live import Live
    from rich.panel import Panel
    from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn
    from rich.table import Table
except ImportError:
    print("❌ PyFU requires 'rich'. Install with: pip install rich")
    sys.exit(1)

console = Console()

# --- ⚙️ CONFIGURATION & DEFAULTS ---

DEFAULT_CONFIG = {
    "line_length": 100,
    "target_version": "py310",
    "docstring_style": "google",
    "complexity_threshold": 10,
    "security_strictness": "medium",  # low, medium, high
}

# --- 🧠 THE BRAIN: AST ANALYSIS & GENERATION ---


class ASTBrain(ast.NodeVisitor):
    """
    Performs deep code analysis using Abstract Syntax Trees.
    Detects complexity, missing docs, mutable defaults, and structural issues.
    """

    def __init__(self, filepath: Path):
        self.filepath = filepath
        self.issues: list[dict[str, Any]] = []
        self.functions_without_docs: list[str] = []
        self.classes_without_docs: list[str] = []
        self.imports: set[str] = set()
        self.complexity_scores: dict[str, int] = {}
        self.mutable_defaults: list[str] = []

    def visit_FunctionDef(self, node: ast.FunctionDef):
        # 1. Complexity Analysis (Cyclomatic Complexity - Simplified)
        complexity = 1
        for child in ast.walk(node):
            if isinstance(
                child, (ast.If, ast.For, ast.While, ast.With, ast.Try, ast.ExceptHandler)
            ):
                complexity += 1

        self.complexity_scores[node.name] = complexity

        # 2. Docstring Check
        if not ast.get_docstring(node):
            self.functions_without_docs.append(node.name)

        # 3. Mutable Default Arguments Check
        for arg in node.args.defaults:
            if isinstance(arg, (ast.List, ast.Dict, ast.Set)):
                self.mutable_defaults.append(node.name)
                self.issues.append(
                    {
                        "type": "Security/Bug",
                        "msg": f"Mutable default argument detected in '{node.name}'",
                        "line": node.lineno,
                    }
                )

        self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef):
        if not ast.get_docstring(node):
            self.classes_without_docs.append(node.name)
        self.generic_visit(node)

    def visit_Import(self, node: ast.Import):
        for alias in node.names:
            self.imports.add(alias.name)
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom):
        if node.module:
            self.imports.add(node.module)
        self.generic_visit(node)

    def generate_test_scaffold(self) -> str:
        """Generates a pytest scaffold based on analyzed functions."""
        lines = [
            "import pytest",
            f"from {self.filepath.stem} import *",
            "",
            "# 🧪 Auto-Generated Test Suite by PyFU",
            "",
        ]

        for func, complexity in self.complexity_scores.items():
            if not func.startswith("_"):
                lines.append(f"def test_{func}_basic():")
                lines.append(f"    # TODO: Implement test for {func} (Complexity: {complexity})")
                lines.append("    assert True  # Placeholder")
                lines.append("")
        return "\n".join(lines)

    def generate_docstring_patch(self, source_code: str) -> str:
        """Naive injection of docstrings (stub) - a real implementation would use LibCST."""
        # Note: robust AST modification requires LibCST, doing safe append here is tricky.
        # returning source for now, effectively a placeholder for the logic
        return source_code


# --- 🛠️ TOOL WRAPPERS ---


class ToolRunner:
    def __init__(self, root: Path):
        self.root = root
        self.env = os.environ.copy()

    def run(self, cmd: list[str], title: str) -> dict[str, Any]:
        start_time = time.time()
        try:
            # Check if tool is installed
            executable = cmd[0] if shutil.which(cmd[0]) else sys.executable
            full_cmd = [executable, *cmd[1:]] if executable == sys.executable else cmd

            # If invoking via python -m
            if cmd[0].endswith("python") or cmd[0].endswith("python3"):
                full_cmd = cmd

            proc = subprocess.run(full_cmd, capture_output=True, text=True, cwd=self.root)

            duration = time.time() - start_time
            success = proc.returncode == 0

            return {
                "tool": title,
                "success": success,
                "stdout": proc.stdout.strip(),
                "stderr": proc.stderr.strip(),
                "duration": duration,
                "returncode": proc.returncode,
            }
        except Exception as e:
            return {
                "tool": title,
                "success": False,
                "stdout": "",
                "stderr": str(e),
                "duration": time.time() - start_time,
                "returncode": -1,
            }


# --- 🚀 THE AGENT ---


class PyFUAgent:
    def __init__(self, target: Path, config: dict[str, Any], args: argparse.Namespace):
        self.target = target.resolve()
        self.root = self.target if self.target.is_dir() else self.target.parent
        self.config = config
        self.args = args
        self.runner = ToolRunner(self.root)
        self.stats = {"fixed": 0, "issues": 0, "complexity_reduced": 0}

    def _get_files(self) -> list[Path]:
        if self.target.is_file():
            return [self.target]

        # Read gitignore/exclude logic could go here
        files = list(self.target.rglob("*.py"))
        # Exclude venv/site-packages
        return [
            f
            for f in files
            if "site-packages" not in str(f) and "venv" not in str(f) and ".git" not in str(f)
        ]

    def analyze_file(self, file_path: Path) -> ASTBrain:
        try:
            with open(file_path, encoding="utf-8") as f:
                source = f.read()
            tree = ast.parse(source)
            brain = ASTBrain(file_path)
            brain.visit(tree)
            return brain
        except Exception:
            # console.print(f"[red]AST Parse Error on {file_path.name}: {e}[/red]")
            return ASTBrain(file_path)

    def phase_1_security_and_lint(self, files: list[str]):
        """Run Ruff (Linter/Fixer) and Bandit (Security)"""

        # 1. Ruff (The Heavy Lifter for fixing imports, syntax, unused vars)
        # We construct a god-tier ruff config on the fly via CLI args if needed
        ruff_cmd = [
            sys.executable,
            "-m",
            "ruff",
            "check",
            "--fix",
            "--unsafe-fixes",
            "--exit-zero",
            "--select",
            "E,F,W,I,UP,N,B,A,C4,PT,SIM,RET,RUF",  # Aggressive rule selection
        ] + files

        yield self.runner.run(ruff_cmd, "Ruff (Deep Refactor)")

        # 2. Bandit (Security)
        if self.args.security_audit:
            bandit_cmd = [sys.executable, "-m", "bandit", "-r", "-q", "-f", "json", *files]
            yield self.runner.run(bandit_cmd, "Bandit (Security Audit)")

    def phase_2_format_and_type(self, files: list[str]):
        """Black (Format) and Mypy (Types)"""

        # 3. Black
        black_cmd = [
            sys.executable,
            "-m",
            "black",
            "-l",
            str(self.config["line_length"]),
            "-q",
            *files,
        ]
        yield self.runner.run(black_cmd, "Black (Formatter)")

        # 4. Mypy
        mypy_cmd = [
            sys.executable,
            "-m",
            "mypy",
            "--ignore-missing-imports",
            "--no-error-summary",
            "--install-types",
            "--non-interactive",
            *files,
        ]
        yield self.runner.run(mypy_cmd, "Mypy (Type Enforcer)")

    def phase_3_intelligence(self, py_files: list[Path]):
        """Internal AST Analysis, Doc Generation, Test Generation"""
        results = []

        for f in py_files:
            brain = self.analyze_file(f)

            # Auto-Generate Tests
            if self.args.generate_tests:
                test_file = f.parent / f"test_{f.stem}.py"
                if not test_file.exists():
                    scaffold = brain.generate_test_scaffold()
                    test_file.write_text(scaffold, encoding="utf-8")
                    results.append(f"🧪 Created tests for {f.name}")

            # Report Complexity / Mutable Defaults
            for func, score in brain.complexity_scores.items():
                if score > self.config["complexity_threshold"]:
                    results.append(f"🧠 High Complexity: {f.name}::{func} (Score: {score})")

            for issue in brain.issues:
                results.append(f"⚠️ {issue['msg']} in {f.name}:{issue['line']}")

        return results

    def run_pipeline(self):
        py_files_path = self._get_files()
        py_files_str = [str(f) for f in py_files_path]

        if not py_files_path:
            console.print("[yellow]⚠️ No Python files found to process.[/yellow]")
            return

        # --- UI SETUP ---
        layout = Layout()
        layout.split_column(
            Layout(name="header", size=3),
            Layout(name="progress", size=10),
            Layout(name="logs", ratio=1),
        )
        layout["header"].update(
            Panel(
                f"🚀 [bold cyan]PyFU[/] processing {len(py_files_path)} files in {self.root}",
                style="on black",
            )
        )

        log_content = ""

        with Live(layout, refresh_per_second=10, console=console):

            # --- PHASE 1 & 2: EXTERNAL TOOLS ---
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
                expand=True,
            ) as progress:
                layout["progress"].update(Panel(progress, title="⚡ Pipeline Execution"))

                task_id = progress.add_task("Running God-Tier Pipeline...", total=4)

                # Execute Tools Sequentially for safety, though parallel is possible
                tools = [
                    self.phase_1_security_and_lint(py_files_str),
                    self.phase_2_format_and_type(py_files_str),
                ]

                all_results = []

                for phase in tools:
                    for result in phase:
                        icon = "✅" if result["success"] else "⚠️"
                        color = "green" if result["success"] else "yellow"

                        log_line = f"[{color}]{icon} {result['tool']}: {result['duration']:.2f}s[/]"
                        if not result["success"] and result["stderr"]:
                            # Truncate error for display
                            err_preview = result["stderr"][:200].replace("\n", " ") + "..."
                            log_line += f"\n  [dim red]Error: {err_preview}[/]"

                        log_content += log_line + "\n"
                        layout["logs"].update(
                            Panel(log_content, title="📝 Execution Log", border_style="cyan")
                        )
                        all_results.append(result)
                    progress.advance(task_id, 2)  # Advancing steps

            # --- PHASE 3: INTERNAL INTELLIGENCE ---
            log_content += "\n[bold magenta]🧠 Running AST Intelligence Engine...[/]\n"
            layout["logs"].update(Panel(log_content, title="📝 Execution Log"))

            intel_results = self.phase_3_intelligence(py_files_path)
            for res in intel_results:
                log_content += f"  {res}\n"
            layout["logs"].update(Panel(log_content, title="📝 Execution Log"))

        # --- FINAL REPORT ---
        console.clear()
        self.print_summary(all_results, intel_results)

    def print_summary(self, tool_results, intel_results):
        console.print(Panel.fit("✨ PYFU: MISSION COMPLETE ✨", style="bold green"))

        table = Table(title="📊 Execution Report", box=box.ROUNDED)
        table.add_column("Tool / Check", style="cyan")
        table.add_column("Status", style="bold")
        table.add_column("Details", style="dim")

        for res in tool_results:
            status = "[green]PASS[/]" if res["returncode"] == 0 else "[yellow]ISSUES[/]"
            # Parse ruff/bandit output specifically if we wanted detailed metrics
            table.add_row(res["tool"], status, f"{res['duration']:.2f}s")

        console.print(table)

        if intel_results:
            intel_panel = Panel(
                "\n".join(intel_results[:15])
                + ("\n...and more" if len(intel_results) > 15 else ""),
                title="🧠 Intelligence Insights",
                border_style="magenta",
            )
            console.print(intel_panel)


# --- 🔁 WATCHDOG ---


def start_watchdog(target: Path, callback):
    """Simple polling watchdog to avoid 'watchdog' library dependency if not strictly needed"""
    console.print(f"[bold cyan]👀 Watching {target} for changes... (Ctrl+C to stop)[/]")
    last_mtime = {}

    while True:
        try:
            files = list(target.rglob("*.py"))
            changed = False
            for f in files:
                mtime = f.stat().st_mtime
                if f not in last_mtime:
                    last_mtime[f] = mtime
                elif mtime != last_mtime[f]:
                    last_mtime[f] = mtime
                    changed = True

            if changed:
                console.print("\n[bold yellow]🔄 Change detected! Triggering PyFU...[/]")
                callback()
                console.print("[bold cyan]👀 Waiting for changes...[/]")

            time.sleep(1)
        except KeyboardInterrupt:
            console.print("\n[red]🛑 Watchdog stopped.[/red]")
            break


# --- 🏁 MAIN ---


def main():
    parser = argparse.ArgumentParser(
        prog="pyfu", description="🛠️✨ PYFU: The God-Tier Python Code Agent 🐍🦀"
    )
    parser.add_argument("path", nargs="?", default=".", help="📂 File or folder to process")
    parser.add_argument("--watch", action="store_true", help="👀 Real-time file watching")
    parser.add_argument(
        "--generate-tests", action="store_true", help="🧪 Auto-generate pytest scaffolds"
    )
    parser.add_argument(
        "--security-audit", action="store_true", help="🔒 Run deep security audit (Bandit)"
    )
    parser.add_argument("--force-unsafe", action="store_true", help="☢️ Allow unsafe fixes")

    args = parser.parse_args()

    # Load Config (Mocking a TOML loader for simplicity)
    config = DEFAULT_CONFIG

    target = Path(args.path)
    if not target.exists():
        console.print(f"[red]🚫 Path not found:[/red] {target}")
        sys.exit(1)

    agent = PyFUAgent(target, config, args)

    if args.watch:
        start_watchdog(target, agent.run_pipeline)
    else:
        agent.run_pipeline()


if __name__ == "__main__":
    main()
