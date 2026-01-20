# 🥋 pyfu (Python Fixer Upper)

> **Aggressive. Deterministic. Hash-Based. Brutally Honest.**

**pyfu** is not a linter. It is a **forceful Python auto-repair engine** built to fix code that ordinary tools refuse to touch.

It performs **syntax-first repair** before formatting, using a surgical heuristic engine to recover broken files with bad indentation, missing colons, and malformed blocks — *then* hands them off to the formatter stack.

No lies. No loops. No mass rewrites.
If nothing changed, **pyfu stays silent**.

---

## ⚡ Key Features

* **🛡️ Idempotent & Hash-Based**
  Uses **SHA-256 content hashing**. Ignores timestamps, mtimes, and metadata. If logic didn’t change, the file is not rewritten. Ever.

* **🚑 Syntax Surgery**
  Repairs `IndentationError`, missing `:` in blocks, malformed dedents, and structurally broken code *before* formatting.

* **👀 Adult Watch Mode**
  Debounced, loop-safe, self-aware. Detects its own writes and refuses to spiral into infinite fix loops.

* **🧪 Auto Test Generation**
  Generates `pytest` skeletons for public functions without overwriting existing tests.

* **🧰 Full Formatter Arsenal**
  Deterministically orchestrates:

  * `ruff` (unsafe fixes)
  * `autopep8` (aggressive repair)
  * `pyupgrade`
  * `isort`
  * `black`
  * `bandit`

---

## 📦 Installation

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Make executable (Linux / macOS)

```bash
chmod +x pyfu.py
```

---

## 🚀 Usage

### 1. One-Shot Fix (Standard)

Fixes Python files recursively. Silent unless it actually modifies code.

```bash
python pyfu.py .
```

---

### 2. Watch Mode — *The Guardian*

Continuously watches files and repairs on save. Loop-safe by design.

```bash
python pyfu.py . --watch
```

---

### 3. Generate Tests

Fixes code **and** generates `test_<module>.py` for public functions.

```bash
python pyfu.py src/ --generate-tests
```

---

### 4. Single File Surgery

```bash
python pyfu.py broken_script.py
```

---

## 🔧 The Repair Pipeline

pyfu follows a strict **survival-first** pipeline:

1. **Read & Hash**
   Compute SHA-256. If unchanged → **STOP**.

2. **Normalize**
   Convert tabs → 4 spaces.

3. **Syntax Check**
   Attempt `ast.parse`.

4. **🚑 Surgery (if invalid)**

   * Inject missing colons (`if x` → `if x:`)
   * Rebuild indentation hierarchy
   * Repair malformed block structure

5. **External Tools (only if needed)**

   * `ruff --fix --unsafe-fixes`
   * `autopep8 -aaa`
   * `pyupgrade`
   * `isort`
   * `black`

6. **Verify**
   Re-hash. If content changed → write & report. Otherwise → silence.

---

## 🚫 Zero-Tolerance Output Policy

pyfu will **never** print:

* ❌ `Processing 10 files...`
* ❌ `No changes needed`
* ❌ `All files verified`

pyfu **only** prints real events:

* 🔧 `Repaired: <file>`
* 💥 `Failed: <file>`
* 🧪 `Generated tests: <file>`

No noise. No lies.

---

## ⚠️ Requirements

* Python **3.10+**
* Formatter tools installed and available in PATH
* The courage to let a script rewrite your bad code

---

## 🧠 Philosophy

pyfu is deterministic.
Run it twice — the second run should do **nothing**.

If a tool says it fixed something, **the hash must prove it**.

---

Welcome to grown-up auto-repair.
