# 🛠️ PyFU Ultimate: God-Tier Python Code Agent

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Code Style: Black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![Linter: Ruff](https://img.shields.io/badge/linter-ruff-red.svg)](https://github.com/astral-sh/ruff)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

> **The all-knowing, auto-fixing, self-healing code optimization system.**

PyFU Ultimate is not just a linter; it is an intelligent agent that orchestrates the best tools in the Python ecosystem (`Ruff`, `Black`, `Mypy`, `Bandit`) combined with a custom **AST Intelligence Engine**. It analyzes, refactors, secures, and generates tests for your codebase in seconds.

---

## ⚡ Key Capabilities

### 1. 🧬 **The AST Intelligence Brain**
Unlike standard linters, PyFU parses your code's Abstract Syntax Tree (AST) to perform deep analysis:
- **Complexity Analysis:** Calculates Cyclomatic Complexity per function to identify maintenance nightmares.
- **Bug Detection:** Identifies dangerous patterns like **Mutable Default Arguments** (`def foo(x=[]):`).
- **Test Generation:** Automatically writes `pytest` scaffolds based on your function signatures and complexity scores.

### 2. 🛡️ **Advanced Security & Linting**
- **Security Audits:** Integrates `Bandit` to detect SQL injections, hardcoded secrets, and weak cryptography.
- **Aggressive Refactoring:** Uses `Ruff` to auto-fix imports, simplify logic, remove unused variables, and modernize legacy syntax.

### 3. 💎 **Pristine Formatting & Typing**
- **Zero-Config Formatting:** Enforces `Black` standards strictly.
- **Type Enforcement:** Runs `Mypy` to ensure type safety without the visual clutter of standard error logs.

### 4. 📺 **God-Tier Developer Experience**
- **Rich UI:** Beautiful, real-time dashboard with progress bars, live logs, and summary tables.
- **Watchdog Mode:** Monitors files for changes and auto-heals code instantly on save.

---

## 📦 Installation

PyFU Ultimate is a self-contained agent, but it relies on industry-standard power tools.

### 1. Install Dependencies
```bash
pip install rich ruff black mypy bandit pytest
```

### 2. Install PyFU
Download the `pyfu.py` script to your project root or add it to your PATH.
```bash
# Option B: Clone repository
git clone https://github.com/pro-grammer-SD/pyfu.git
```

---

## 🚀 Usage

### Standard Refactor
The default mode runs the full pipeline: Linting, Fixing, Formatting, Typing, and AST Analysis.
```bash
python pyfu.py .
```

### 🧪 Auto-Generate Unit Tests
PyFU will scan your code, determine which functions need testing, and generate a `test_*.py` file with placeholders.
```bash
python pyfu.py src/ --generate-tests
```

### 🔒 Deep Security Audit
Run standard checks plus deep vulnerability scanning (Bandit).
```bash
python pyfu.py . --security-audit
```

### 👀 Watchdog Mode (Dev Loop)
Keep PyFU running in the background. It will detect file saves and instantly re-process the changed files.
```bash
python pyfu.py . --watch
```

---

## 📊 The "God-Tier" Dashboard

PyFU replaces the messy output of standard tools with a unified, structured dashboard.

```text
🚀 PyFU Ultimate processing 12 files in /projects/backend

⚡ Pipeline Execution
⠋ Running God-Tier Pipeline... ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 50%

📝 Execution Log
───────────────────────────────────────────────────────────────────
✅ Ruff (Deep Refactor): 0.42s
✅ Black (Formatter): 0.15s
⚠️ Mypy (Type Enforcer): 1.20s
   Error: argument "x" has incompatible type "int"; expected "str"
🧠 Running AST Intelligence Engine...
  ⚠️ Mutable default argument detected in 'user_list' in main.py:45
  🧪 Created tests for utils.py
```

---

## ⚙️ Configuration

PyFU is opinionated by default, but you can tweak the internal `DEFAULT_CONFIG` dictionary in `pyfu.py`:

```python
DEFAULT_CONFIG = {
    "line_length": 100,            # Black/Ruff line length
    "target_version": "py310",     # Target Python version
    "complexity_threshold": 10,    # Max Cyclomatic Complexity allowed
    "security_strictness": "medium"
}
```

---

## 🏗️ Architecture

PyFU operates in three phases:

1.  **Phase 1: Structure & Security** (`Ruff` + `Bandit`)
    *   Fixes syntax, imports, and style violations.
    *   Scans for vulnerabilities.
2.  **Phase 2: Consistency** (`Black` + `Mypy`)
    *   Formats code to a canonical style.
    *   Checks type consistency.
3.  **Phase 3: Intelligence** (`ASTBrain`)
    *   Parses the resulting clean code.
    *   Analyzes algorithmic complexity.
    *   Generates missing assets (tests/docs).

---

## 🤝 Contributing

PyFU Ultimate is open for business. We welcome PRs that add new "God-Tier" capabilities:
*   AI-based docstring generation (LLM integration).
*   Automatic dependency version pinning.
*   Docker containerization support.

---

## 📄 License

Distributed under the MIT License. See `LICENSE` for more information.
