# Agent Guidelines & Commit Rules for Nimbus Match

This document defines coding conventions, workflow standards, and mandatory Git commit rules for AI assistants and agents working on the **Nimbus Match** codebase.

---

## 📌 Git Commit Rules

When creating Git commits in this repository, agents **MUST** strictly adhere to the following author, committer, co-author, and message formatting rules.

### 1. Author & Committer Metadata

- **Author**: The human user (`Ivana <ivana.gyro@gmail.com>`).
- **Committer & Co-author**: The AI model executing the commit (e.g., `<Model Name> <<model-email>>`).

### 2. Atomic Commits & Message Standards

- **One logical change per commit**: Keep commits focused and self-contained.
- **Conventional Commits**: Use `feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `ci:`, `chore:`.
- **Commit message body**: When non-trivial, include:
  - **Why**: The problem, motivation, or root cause (omit if self-evident from title).
  - **What**: Key changes and decisions made (especially design rationale or trade-offs not suited for code comments).

---

## 🛠️ Execution Command Template

To ensure the commit metadata is accurately recorded, use the following `git commit` command pattern:

```bash
git -c user.name="Ivana" \
    -c user.email="ivana.gyro@gmail.com" \
    -c committer.name="<Model Name>" \
    -c committer.email="<model-email>" \
    commit -m "<type>(<scope>): <short summary>" \
           -m "<Context on why/what if non-trivial>" \
           -m "Co-authored-by: <Model Name> <<model-email>>"
```

---

## 🧪 Verification & Code Quality Rules

Before committing any changes:

1. **Format & Lint**: Run `pixi run pre-commit run --all-files` (uses `ruff`, `ruff-format`, `pyproject-fmt`).
2. **Run Unit Tests**: Run `pixi run pytest` and verify all tests pass.
3. **Flat Layout Integrity**: Maintain flat repository structure (no `src/` directory).

---

## 🤖 Antigravity Agent Execution Rules

Rules in this section apply specifically to **Antigravity**:

1. **No Inline Python One-Liners (`-c`)**:
   Do **NOT** use `pixi run python -c "..."` with varying command-line strings.
2. **Fixed Scratch Script Execution**:
   Instead, write temporary inspection or test scripts to the fixed path `.run_temp.py`.
   Run them with a consistent, static command line (e.g. `pixi run python .run_temp.py`), so the command line remains identical across runs and can be automatically allowed by permission managers without prompting.


