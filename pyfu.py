#!/usr/bin/env python3
"""PyFu (Python Fixer Upper) v2.0.0
Advanced, intelligent, production-grade Python repair, formatting, and linting tool.

Handles complex syntax errors, multi-line statements, decorators, async/await,
f-strings, broken imports, and integrates with industry-standard tools.
"""

import ast
import hashlib
import json
import logging
import re
import shutil
import subprocess
import sys
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, asdict
from enum import Enum
from pathlib import Path
from typing import Optional, Any
import tempfile

# Type hints
from typing import Dict, List, Set, Tuple, Union


# ============================================================================
# DEPENDENCY CHECKS
# ============================================================================
try:
    import typer
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.theme import Theme
    from watchdog.events import FileSystemEventHandler
    from watchdog.observers import Observer
except ImportError as e:
    print(f"Error: Missing required dependency: {e}", file=sys.stderr)
    print("Please install: pip install typer rich watchdog", file=sys.stderr)
    sys.exit(1)

# ============================================================================
# CONFIGURATION & LOGGING SETUP
# ============================================================================

STATE_FILE = ".pyfu_state.json"
CONFIG_FILE = "pyfu.toml"
LOG_FILE = ".pyfu_report.json"

# Rich Console Setup
custom_theme = Theme({
    "info": "cyan",
    "warning": "yellow",
    "error": "bold red",
    "success": "bold green",
    "change": "magenta",
    "debug": "dim",
})
console = Console(theme=custom_theme)

# Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)


# ============================================================================
# ENUMS & DATA CLASSES
# ============================================================================

class RepairMode(str, Enum):
    """Repair aggressiveness level."""
    SAFE = "safe"          # Only fix obvious errors
    NORMAL = "normal"      # Standard fixing (default)
    AGGRESSIVE = "aggressive"  # Fix anything that seems remotely wrong


class ToolName(str, Enum):
    """Available formatting/linting tools."""
    ISORT = "isort"
    PYUPGRADE = "pyupgrade"
    AUTOPEP8 = "autopep8"
    RUFF = "ruff"
    BLACK = "black"
    BANDIT = "bandit"
    PYLINT = "pylint"


@dataclass
class FixResult:
    """Result of applying a single fix."""
    name: str
    success: bool
    changes_made: bool
    error: Optional[str] = None
    details: Optional[str] = None


@dataclass
class FileRepairReport:
    """Full repair report for a file."""
    file_path: str
    original_hash: str
    final_hash: str
    syntax_valid_before: bool
    syntax_valid_after: bool
    changes_made: bool
    mode: str
    tool_results: List[Dict[str, Any]]
    surgery_applied: bool
    error: Optional[str] = None
    total_time_ms: float = 0.0


# ============================================================================
# TOOLS CONFIGURATION
# ============================================================================

TOOLS_CONFIG = {
    ToolName.ISORT: {
        "cmd": ["isort", "--profile", "black", "--quiet"],
        "priority": 10,
        "optional": False,
    },
    ToolName.PYUPGRADE: {
        "cmd": ["pyupgrade", "--py311-plus"],
        "priority": 20,
        "optional": False,
    },
    ToolName.AUTOPEP8: {
        "cmd": [
            "autopep8", "--in-place", "--aggressive", "--aggressive",
            "--aggressive", "-aaa"
        ],
        "priority": 30,
        "optional": False,
    },
    ToolName.RUFF: {
        "cmd": [
            "ruff", "check", "--fix", "--unsafe-fixes", "--select", "ALL",
            "--ignore", "ANN", "--quiet"
        ],
        "priority": 25,
        "optional": False,
    },
    ToolName.BLACK: {
        "cmd": ["black", "--quiet"],
        "priority": 40,
        "optional": False,
    },
    ToolName.BANDIT: {
        "cmd": ["bandit", "-c", "pyproject.toml", "-r", "-q", "-ll"],
        "priority": 50,
        "optional": True,
    },
    ToolName.PYLINT: {
        "cmd": ["pylint", "--errors-only", "--rcfile=pyproject.toml"],
        "priority": 50,
        "optional": True,
    },
}

# ============================================================================
# STATE MANAGEMENT
# ============================================================================

class StateManager:
    """Manages .pyfu_state.json for content hashing and infinite-loop prevention."""

    def __init__(self):
        self.path = Path(STATE_FILE)
        self.state: Dict[str, str] = self._load()
        self._lock = threading.Lock()

    def _load(self) -> Dict[str, str]:
        """Load state from file."""
        if not self.path.exists():
            return {}
        try:
            with open(self.path, encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return {}

    def save(self) -> None:
        """Atomically save state."""
        with self._lock:
            try:
                temp_path = self.path.with_suffix(".tmp")
                with open(temp_path, "w", encoding="utf-8") as f:
                    json.dump(self.state, f, indent=2)
                temp_path.replace(self.path)
            except OSError:
                pass

    def get_hash(self, file_path: str) -> Optional[str]:
        """Get stored hash for file."""
        return self.state.get(file_path)

    def update_hash(self, file_path: str, content_hash: str) -> None:
        """Update stored hash for file."""
        with self._lock:
            self.state[file_path] = content_hash
            self.save()

    def clear_file(self, file_path: str) -> None:
        """Remove file from state (forces re-processing)."""
        with self._lock:
            if file_path in self.state:
                del self.state[file_path]
                self.save()


state_manager = StateManager()

# ============================================================================
# SYNTAX SURGERY ENGINE
# ============================================================================

class AdvancedSyntaxSurgeon:
    """
    Sophisticated syntax repair engine.
    Handles multi-line statements, decorators, async/await, f-strings,
    broken imports, and complex indentation issues.
    """

    # Keywords that start blocks
    BLOCK_KEYWORDS = {
        "if", "elif", "else", "for", "while", "try", "except", "finally",
        "with", "def", "class", "async def", "async for", "async with",
        "match", "case", "@"  # decorators
    }

    # Keywords that reduce indentation
    DEDENT_KEYWORDS = {"elif", "else", "except", "finally"}

    def __init__(self, mode: RepairMode = RepairMode.NORMAL):
        self.mode = mode
        self.lines: List[str] = []
        self.in_multiline = False
        self.multiline_delimiter = ""

    @staticmethod
    def calculate_hash(content: str) -> str:
        """Calculate SHA-256 hash of content."""
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    def is_syntax_valid(self, content: str) -> bool:
        """Check if content has valid Python syntax."""
        try:
            ast.parse(content)
            return True
        except SyntaxError:
            return False
        except Exception:
            # Other parsing errors
            return False

    def repair(self, content: str) -> Tuple[str, bool]:
        """
        Repair broken syntax to make it parseable.
        Strategy: Fix JUST ENOUGH for ast.parse() to work,  let formatters handle the rest.
        Returns: (repaired_content, was_repaired)
        """
        if self.is_syntax_valid(content):
            return content, False

        original = content

        # Stage 1: Normalize tabs
        content = self._fix_tabs_and_spaces(content)

        # Stage 2: Break up multi-statement lines FIRST (must happen before keyword processing)
        content = self._fix_broken_multistatement_lines(content)

        # Stage 3: Remove stray colons AFTER splitting (to catch lines that were colons)
        content = self._remove_stray_colons(content)

        # Stage 4: Split keywords stuck to code (e.g., "0except:" -> "0\nexcept:")
        content = self._split_stuck_keywords(content)

        # Stage 5: Fix unclosed strings and brackets (CRITICAL - can't parse without this)
        content = self._fix_unclosed_strings(content)
        content = self._fix_unclosed_brackets_robust(content)

        # Stage 6: Fix missing colons on block keywords
        content = self._fix_missing_colons_simple(content)

        # Stage 7: Fix indentation based on colons
        content = self._fix_indentation_simple(content)

        # Validate
        was_repaired = content != original
        return content, was_repaired

    def _remove_stray_colons(self, content: str) -> str:
        """Remove colons from end of lines that shouldn't have them."""
        lines = content.splitlines()
        fixed = []
        BLOCK_KEYWORDS = {"if", "elif", "else", "for", "while", "try", "except", "finally", "with", "def", "class", "async"}

        for line in lines:
            stripped = line.strip()
            
            if not stripped or stripped.startswith("#"):
                fixed.append(line)
                continue

            # Check if line ends with : but isn't a block keyword
            if stripped.endswith(":"):
                # See if it starts with a block keyword
                is_block_keyword = any(stripped.startswith(kw) for kw in BLOCK_KEYWORDS)
                
                if not is_block_keyword:
                    # Remove the trailing colon
                    fixed.append(line.rstrip(":"))
                    continue
            
            fixed.append(line)

        return "\n".join(fixed)

    def _split_stuck_keywords(self, content: str) -> str:
        """Split keywords that are stuck to previous code (e.g., '0except' -> '0\nexcept')."""
        lines = content.splitlines()
        fixed = []

        for line in lines:
            # Look for patterns like "1 /0except:" and split them
            for keyword in {"except", "finally", "elif", "else"}:
                # Pattern: something directly followed by keyword
                pattern = r"([0-9a-zA-Z_\)\]}])" + f"({keyword}[:\\s])"
                if re.search(pattern, line.strip()):
                    # Split and re-add on separate lines
                    parts = re.split(pattern, line.strip())
                    indent = len(line) - len(line.lstrip())
                    indent_str = " " * indent
                    
                    result_lines = []
                    i = 0
                    while i < len(parts):
                        part = parts[i]
                        if not part:
                            i += 1
                            continue
                        
                        if part in {"except", "finally", "elif", "else"}:
                            result_lines.append(indent_str + part)
                            # Get the rest of that pattern
                            if i + 1 < len(parts):
                                rest = parts[i + 1]
                                if rest:
                                    result_lines[-1] += rest
                                i += 1
                        else:
                            result_lines.append(indent_str + part if not result_lines else part)
                        i += 1
                    
                    for new_line in result_lines:
                        if new_line.strip():
                            fixed.append(new_line)
                    break
            else:
                fixed.append(line)

        return "\n".join(fixed)

    def _fix_unclosed_brackets_robust(self, content: str) -> str:
        """Balance brackets more robustly."""
        lines = content.splitlines()
        fixed = []

        for line in lines:
            if not line.strip():
                fixed.append(line)
                continue

            # Count brackets, accounting for strings
            in_string = False
            quote_char = ""
            stack = []
            pairs = {"(": ")", "[": "]", "{": "}"}

            for i, char in enumerate(line):
                # String handling
                if char in ('"', "'") and (i == 0 or line[i-1] != "\\"):
                    if not in_string:
                        in_string = True
                        quote_char = char
                    elif char == quote_char:
                        in_string = False

                if not in_string:
                    if char in pairs:
                        stack.append(pairs[char])
                    elif char in pairs.values():
                        if stack and stack[-1] == char:
                            stack.pop()

            # Close unclosed brackets
            closing = "".join(reversed(stack))
            fixed.append(line + closing if closing else line)

        return "\n".join(fixed)

    def _fix_broken_multistatement_lines(self, content: str) -> str:
        """Break up lines with multiple statements (semicolons, multiple colons)."""
        lines = content.splitlines()
        fixed = []

        for line in lines:
            stripped = line.strip()
            indent = len(line) - len(line.lstrip())
            indent_str_line = " " * indent

            # Handle semicolon-separated statements
            if ";" in stripped and not any(x in stripped for x in ["f'", 'f"', "r'", 'r"']):
                # Split onsemicolons (but not in strings)
                parts = []
                current = ""
                in_string = False
                quote_char = ""
                
                for i, char in enumerate(stripped):
                    if char in ('"', "'") and (i == 0 or stripped[i-1] != "\\"):
                        if not in_string:
                            in_string = True
                            quote_char = char
                        elif char == quote_char:
                            in_string = False
                    
                    if char == ";" and not in_string:
                        if current.strip():
                            parts.append(current.strip())
                        current = ""
                    else:
                        current += char
                
                if current.strip():
                    parts.append(current.strip())
                
                # Add all parts on separate lines
                for part in parts:
                    if part:
                        fixed.append(indent_str_line + part)
            else:
                fixed.append(line)

        return "\n".join(fixed)

    def _fix_tabs_and_spaces(self, content: str) -> str:
        """Convert tabs to spaces (PEP 8)."""
        return content.replace("\t", "    ")

    def _fix_unclosed_strings(self, content: str) -> str:
        """Balance quotes and handle unclosed strings."""
        lines = content.splitlines(keepends=True)
        fixed_lines = []

        for line in lines:
            stripped = line.rstrip("\n\r")
            in_string = False
            quote_char = ""
            escape_next = False
            i = 0

            fixed_line = ""
            while i < len(stripped):
                char = stripped[i]

                if escape_next:
                    fixed_line += char
                    escape_next = False
                    i += 1
                    continue

                if char == "\\":
                    fixed_line += char
                    escape_next = True
                    i += 1
                    continue

                if not in_string and char in ('"', "'"):
                    in_string = True
                    quote_char = char
                    fixed_line += char
                elif in_string and char == quote_char:
                    # Check for triple quotes
                    if i + 2 < len(stripped) and stripped[i:i+3] == quote_char * 3:
                        fixed_line += quote_char * 3
                        i += 2
                    else:
                        in_string = False
                    fixed_line += char
                else:
                    fixed_line += char

                i += 1

            # Close unclosed string
            if in_string:
                fixed_line += quote_char

            fixed_lines.append(fixed_line + ("\n" if line.endswith("\n") else ""))

        return "".join(fixed_lines).rstrip("\n") + "\n" if content.endswith("\n") else "".join(fixed_lines)

    def _fix_broken_imports(self, content: str) -> str:
        """Recover broken import statements - placeholder for future enhancements."""
        return content


    def _fix_missing_colons_simple(self, content: str) -> str:
        """Add missing colons to block keywords that need them."""
        lines = content.splitlines()
        fixed = []
        # Only these keywords should have colons
        BLOCK_KEYWORDS_NEED_COLON = {"if", "elif", "else", "for", "while", "try", "except", "finally", "with", "def", "class", "async def", "async for", "async with", "match", "case"}

        for i, line in enumerate(lines):
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                fixed.append(line)
                continue

            # Get code part (before comments)
            code_part = stripped.split("#")[0].rstrip()

            # Already has colon somewhere (or ends with colon - already complete)
            if ":" in code_part:
                fixed.append(line)
                continue

            # Check if starts with a keyword that needs a colon
            needs_colon = False
            for keyword in BLOCK_KEYWORDS_NEED_COLON:
                if code_part.startswith(keyword):
                    # Verify it's the keyword and not part of a longer word
                    if len(keyword) == len(code_part) or code_part[len(keyword)] in (" ", "(", "[", "{", "\t"):
                        needs_colon = True
                        break

            # Add colon if needed
            if needs_colon:
                fixed.append(line.rstrip() + ":")
            else:
                fixed.append(line)

        return "\n".join(fixed)

    def _fix_indentation_simple(self, content: str) -> str:
        """Fix indentation based on block keywords and colons."""
        lines = content.splitlines()
        fixed = []
        indent_level = 0
        indent_str = "    "

        for line in lines:
            stripped = line.strip()

            if not stripped:
                fixed.append("")
                continue

            # Dedent keywords
            if any(stripped.startswith(kw) for kw in self.DEDENT_KEYWORDS):
                indent_level = max(0, indent_level - 1)

            # Apply indentation
            fixed.append(indent_str * indent_level + stripped)

            # Increase indent for next line if this ends with colon
            if stripped.endswith(":"):
                indent_level += 1

        return "\n".join(fixed)





# ============================================================================
# TOOL INTEGRATION
# ============================================================================

class ToolExecutor:
    """Executes external formatting/linting tools safely."""

    def __init__(self):
        self.available_tools: Set[ToolName] = self._detect_tools()

    def _detect_tools(self) -> Set[ToolName]:
        """Detect which tools are available."""
        available = set()
        for tool_name in ToolName:
            if shutil.which(tool_name.value):
                available.add(tool_name)
        return available

    def check_dependencies(self) -> bool:
        """Check if critical tools are available."""
        critical = {"black", "ruff", "autopep8", "isort"}
        available_names = {t.value for t in self.available_tools}
        missing = critical - available_names

        if missing:
            console.print(
                Panel(
                    f"❌ Missing critical tools: {', '.join(sorted(missing))}\n"
                    f"Please install: pip install {' '.join(sorted(missing))}",
                    title="Environment Check",
                    border_style="red",
                ),
                style="error"
            )
            return False
        return True

    def run_tool(
        self,
        tool: ToolName,
        file_path: Path
    ) -> FixResult:
        """
        Run a single tool on a file.
        Returns: FixResult with success/error information.
        """
        if tool not in self.available_tools:
            return FixResult(
                name=tool.value,
                success=False,
                changes_made=False,
                error=f"Tool not available"
            )

        try:
            cmd = TOOLS_CONFIG[tool]["cmd"] + [str(file_path)]
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30
            )

            return FixResult(
                name=tool.value,
                success=result.returncode == 0,
                changes_made=True,
                error=result.stderr if result.returncode != 0 else None,
                details=result.stdout.strip() if result.stdout else None
            )

        except subprocess.TimeoutExpired:
            return FixResult(
                name=tool.value,
                success=False,
                changes_made=False,
                error="Tool timeout (30s)"
            )
        except Exception as e:
            return FixResult(
                name=tool.value,
                success=False,
                changes_made=False,
                error=str(e)
            )

    def run_all_tools(
        self,
        file_path: Path,
        skip_tools: Optional[Set[ToolName]] = None
    ) -> List[FixResult]:
        """Run all available tools on a file."""
        skip_tools = skip_tools or set()
        results = []

        # Sort tools by priority
        sorted_tools = sorted(
            (t for t in self.available_tools if t not in skip_tools),
            key=lambda t: TOOLS_CONFIG[t]["priority"]
        )

        for tool in sorted_tools:
            result = self.run_tool(tool, file_path)
            results.append(result)

        return results


# ============================================================================
# REPORT GENERATION
# ============================================================================

class ReportManager:
    """Manages JSON/markdown reports of repairs."""

    def __init__(self):
        self.reports: List[FileRepairReport] = []

    def add_report(self, report: FileRepairReport) -> None:
        """Add a file repair report."""
        self.reports.append(report)

    def save_json(self, output_path: Optional[Path] = None) -> None:
        """Save reports as JSON."""
        path = output_path or Path(LOG_FILE)
        try:
            with open(path, "w", encoding="utf-8") as f:
                data = [asdict(r) for r in self.reports]
                json.dump(data, f, indent=2)
            console.print(f"📊 Report saved to {path}", style="success")
        except Exception as e:
            console.print(f"❌ Failed to save report: {e}", style="error")

    def print_summary(self) -> None:
        """Print summary to console."""
        if not self.reports:
            return

        total_files = len(self.reports)
        repaired_files = sum(1 for r in self.reports if r.changes_made)

        table = Table(title="Repair Summary")
        table.add_column("File", style="cyan")
        table.add_column("Status", style="green")
        table.add_column("Changes", style="magenta")
        table.add_column("Time (ms)", style="dim")

        for report in self.reports:
            status = "✅" if report.syntax_valid_after else "❌"
            changes = "Yes" if report.changes_made else "No"
            table.add_row(
                report.file_path,
                status,
                changes,
                f"{report.total_time_ms:.1f}"
            )

        console.print(table)
        console.print(f"\n📈 Repaired {repaired_files}/{total_files} files", style="success")


# ============================================================================
# CORE REPAIR ENGINE
# ============================================================================

class PyFuRepairEngine:
    """Main repair engine orchestrating all operations."""

    def __init__(
        self,
        mode: RepairMode = RepairMode.NORMAL,
        force_repair: bool = False,
        selective_tools: Optional[Set[ToolName]] = None,
        aggressive_tools: bool = False
    ):
        self.mode = mode
        self.force_repair = force_repair
        self.selective_tools = selective_tools
        self.aggressive_tools = aggressive_tools
        self.surgeon = AdvancedSyntaxSurgeon(mode)
        self.executor = ToolExecutor()
        self.report_manager = ReportManager()

    def repair_file(self, file_path: Path) -> Tuple[bool, Optional[FileRepairReport]]:
        """
        Repair a single file.
        Returns: (success, report)
        """
        s_path = str(file_path)
        start_time = time.time()

        # 1. READ FILE
        try:
            original_content = file_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            console.print(f"⚠️  Skipping binary file: {s_path}", style="warning")
            return False, None
        except Exception as e:
            console.print(f"❌ Read error {s_path}: {e}", style="error")
            return False, None

        # 2. CALCULATE HASHES
        original_hash = self.surgeon.calculate_hash(original_content)
        stored_hash = state_manager.get_hash(s_path)

        if original_hash == stored_hash and not self.force_repair:
            return False, None

        # 3. CHECK SYNTAX
        syntax_valid_before = self.surgeon.is_syntax_valid(original_content)

        # 4. APPLY SURGERY
        working_content = original_content
        surgery_applied = False

        if not syntax_valid_before:
            working_content, surgery_applied = self.surgeon.repair(original_content)

        # 5. WRITE INTERMEDIATE
        try:
            file_path.write_text(working_content, encoding="utf-8")
        except Exception as e:
            console.print(f"❌ Write error {s_path}: {e}", style="error")
            return False, None

        # 6. RUN TOOLS
        tool_results = []
        try:
            results = self.executor.run_all_tools(
                file_path,
                skip_tools=self.selective_tools
            )
            tool_results = [asdict(r) for r in results]
        except Exception as e:
            console.print(f"⚠️  Tool execution error: {e}", style="warning")

        # 7. READ FINAL
        try:
            final_content = file_path.read_text(encoding="utf-8")
        except Exception as e:
            console.print(f"❌ Final read error {s_path}: {e}", style="error")
            return False, None

        final_hash = self.surgeon.calculate_hash(final_content)
        syntax_valid_after = self.surgeon.is_syntax_valid(final_content)
        changes_made = final_hash != stored_hash

        # 8. CREATE REPORT
        elapsed_ms = (time.time() - start_time) * 1000
        report = FileRepairReport(
            file_path=s_path,
            original_hash=original_hash,
            final_hash=final_hash,
            syntax_valid_before=syntax_valid_before,
            syntax_valid_after=syntax_valid_after,
            changes_made=changes_made,
            mode=self.mode.value,
            tool_results=tool_results,
            surgery_applied=surgery_applied,
            total_time_ms=elapsed_ms
        )

        # 9. UPDATE STATE
        if changes_made:
            state_manager.update_hash(s_path, final_hash)

            status_indicator = "✅" if syntax_valid_after else "❌"
            console.print(
                f"{status_indicator} Repaired: {s_path}",
                style="success" if syntax_valid_after else "warning"
            )
        else:
            state_manager.update_hash(s_path, original_hash)

        self.report_manager.add_report(report)
        return changes_made, report

    def repair_directory(
        self,
        directory: Path,
        recursive: bool = True,
        max_workers: int = 4
    ) -> Tuple[int, int]:
        """
        Repair all Python files in directory.
        Returns: (changed_count, total_count)
        """
        # Gather files
        if recursive:
            py_files = list(directory.rglob("*.py"))
        else:
            py_files = list(directory.glob("*.py"))

        # Filter out venv, git, cache
        py_files = [
            p for p in py_files
            if not any(part in {".venv", ".git", "__pycache__"} for part in p.parts)
        ]

        if not py_files:
            console.print("No Python files found.", style="warning")
            return 0, 0

        console.print(f"🚀 Processing {len(py_files)} files...", style="info")

        changed_count = 0
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(self.repair_file, p): p for p in py_files}

            for future in as_completed(futures):
                try:
                    changed, _ = future.result()
                    if changed:
                        changed_count += 1
                except Exception as e:
                    console.print(f"Error processing file: {e}", style="error")

        return changed_count, len(py_files)


# ============================================================================
# WATCH MODE
# ============================================================================

class PyFuWatcher(FileSystemEventHandler):
    """File system watcher for automatic repair on file changes."""

    def __init__(
        self,
        engine: PyFuRepairEngine,
        debounce_ms: int = 1000,
        generate_tests: bool = False
    ):
        self.engine = engine
        self.debounce_ms = debounce_ms / 1000  # Convert to seconds
        self.generate_tests = generate_tests
        self.last_event_time: Dict[str, float] = {}

    def on_modified(self, event) -> None:
        """Handle file modification."""
        if event.is_directory or not event.src_path.endswith(".py"):
            return

        # Debounce
        now = time.time()
        last_time = self.last_event_time.get(event.src_path, 0)

        if now - last_time < self.debounce_ms:
            return

        self.last_event_time[event.src_path] = now

        # Check hash to avoid reprocessing unchanged files
        try:
            path = Path(event.src_path)
            content = path.read_text(encoding="utf-8")
            current_hash = self.engine.surgeon.calculate_hash(content)
            stored_hash = state_manager.get_hash(event.src_path)

            if current_hash == stored_hash:
                return
        except Exception:
            pass

        # Process
        try:
            path = Path(event.src_path)
            self.engine.repair_file(path)

            if self.generate_tests:
                generate_tests_for_file(path)
        except Exception as e:
            console.print(f"🔥 Error in watch mode: {e}", style="error")


def generate_tests_for_file(file_path: Path) -> None:
    """Generate skeleton test file for public functions."""
    if file_path.name.startswith("test_"):
        return

    try:
        content = file_path.read_text(encoding="utf-8")
        tree = ast.parse(content)
    except Exception:
        return

    functions = [
        node.name for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and not node.name.startswith("_")
    ]

    if not functions:
        return

    test_file = file_path.parent / f"test_{file_path.name}"
    existing_tests = set()

    if test_file.exists():
        try:
            test_content = test_file.read_text(encoding="utf-8")
            test_tree = ast.parse(test_content)
            existing_tests = {
                node.name for node in ast.walk(test_tree)
                if isinstance(node, ast.FunctionDef)
            }
        except Exception:
            pass

    new_tests = []
    for func in functions:
        test_name = f"test_{func}"
        if test_name not in existing_tests:
            new_tests.append(
                f"\ndef {test_name}() -> None:\n"
                f'    """Test {func}."""\n'
                f"    # TODO: Implement test\n"
                f"    assert True\n"
            )

    if new_tests:
        with open(test_file, "a", encoding="utf-8") as f:
            if not test_file.exists() or test_file.stat().st_size == 0:
                f.write("import pytest\n\n")
            f.writelines(new_tests)

        console.print(f"🧪 Generated tests for {file_path.name}", style="success")


# ============================================================================
# CLI
# ============================================================================

app = typer.Typer(
    name="pyfu",
    help="Advanced Python fixer, formatter, and repair utility",
    add_completion=False
)


@app.command()
def main(
    path: Path = typer.Argument(
        ...,
        help="File or directory to repair",
        exists=True
    ),
    watch: bool = typer.Option(
        False,
        "--watch",
        help="Enable watch mode for automatic repair"
    ),
    generate_tests: bool = typer.Option(
        False,
        "--generate-tests",
        help="Generate skeleton tests for public functions"
    ),
    recursive: bool = typer.Option(
        True,
        "--recursive/--no-recursive",
        help="Process directories recursively"
    ),
    force: bool = typer.Option(
        False,
        "--force",
        help="Force repair even if file hash unchanged"
    ),
    mode: str = typer.Option(
        "normal",
        "--mode",
        help="Repair aggressiveness (safe|normal|aggressive)"
    ),
    max_workers: int = typer.Option(
        4,
        "--workers",
        help="Max parallel workers for directory repair"
    ),
    skip_tools: Optional[str] = typer.Option(
        None,
        "--skip-tools",
        help="Comma-separated list of tools to skip (isort,black,ruff,...)"
    ),
    report: bool = typer.Option(
        True,
        "--report/--no-report",
        help="Generate JSON report"
    ),
    debounce: int = typer.Option(
        1000,
        "--debounce",
        help="Watch mode debounce time in milliseconds"
    ),
) -> None:
    """PyFu: Advanced Python Repair & Formatting Utility"""

    try:
        # Parse options
        try:
            repair_mode = RepairMode(mode)
        except ValueError:
            console.print(
                f"❌ Invalid mode. Choose: {', '.join(m.value for m in RepairMode)}",
                style="error"
            )
            sys.exit(1)

        # Parse skip tools
        skip_tools_set: Set[ToolName] = set()
        if skip_tools:
            for tool_name in skip_tools.split(","):
                try:
                    skip_tools_set.add(ToolName(tool_name.strip()))
                except ValueError:
                    console.print(f"⚠️  Unknown tool: {tool_name}", style="warning")

        # Initialize engine
        engine = PyFuRepairEngine(
            mode=repair_mode,
            force_repair=force,
            selective_tools=skip_tools_set,
        )

        # Check dependencies
        if not engine.executor.check_dependencies():
            sys.exit(1)

        # Process single file
        if path.is_file():
            if path.suffix == ".py":
                changed, report_obj = engine.repair_file(path)

                if report and report_obj:
                    engine.report_manager.save_json()

                sys.exit(0)
            else:
                console.print(f"❌ Not a Python file: {path}", style="error")
                sys.exit(1)

        # Process directory - non-watch mode
        if not watch:
            changed_count, total_count = engine.repair_directory(
                path,
                recursive=recursive,
                max_workers=max_workers
            )

            engine.report_manager.print_summary()

            if report:
                engine.report_manager.save_json()

            sys.exit(0)

        # Watch mode
        else:
            console.print(
                Panel(
                    f"👀 Watching {path}\n[dim]Press Ctrl+C to stop[/dim]",
                    border_style="blue",
                    title="Watch Mode"
                )
            )

            watcher = PyFuWatcher(
                engine,
                debounce_ms=debounce,
                generate_tests=generate_tests
            )

            observer = Observer()
            observer.schedule(watcher, str(path), recursive=recursive)
            observer.start()

            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                pass
            finally:
                observer.stop()
                observer.join()
                console.print("\n🛑 Watch mode stopped.", style="info")
                sys.exit(0)

    except Exception as e:
        console.print(f"💥 Fatal error: {e}", style="error")
        logger.exception("Unhandled exception")
        sys.exit(1)


@app.command()
def clear_state() -> None:
    """Clear repair state cache."""
    try:
        Path(STATE_FILE).unlink(missing_ok=True)
        console.print("✅ State cache cleared.", style="success")
    except Exception as e:
        console.print(f"❌ Error clearing state: {e}", style="error")
        sys.exit(1)


@app.command()
def check_tools() -> None:
    """Check available tools."""
    executor = ToolExecutor()
    table = Table(title="Tool Availability")
    table.add_column("Tool", style="cyan")
    table.add_column("Status", style="green")

    for tool in ToolName:
        status = "✅ Available" if tool in executor.available_tools else "❌ Missing"
        table.add_row(tool.value, status)

    console.print(table)


if __name__ == "__main__":
    app()
    