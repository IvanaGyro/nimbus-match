# Agent Guidelines & Commit Rules for Nimbus Match

This document defines coding conventions, workflow standards, and mandatory Git commit rules for AI assistants and agents working on the **Nimbus Match** codebase.

---

## 📌 Git Commit Rules

When creating Git commits in this repository, agents **MUST** strictly adhere to the following author, committer, co-author, and message formatting rules.

### 1. Author & Committer Metadata

- **Author**: The human user (`Ivana <ivana.gyro@gmail.com>`).
- **Committer**: The AI model executing the commit (`Gemini 3.6 Flash <gemini@google.com>`).
- **Co-author**: The AI model (`Co-authored-by: Gemini 3.6 Flash <gemini@google.com>`).

### 2. Commit Message Standard

Commit messages **MUST** follow [Conventional Commits](https://www.conventionalcommits.org/):

- `feat:` New features (e.g., font building features, new formats).
- `fix:` Bug fixes (e.g., metric calculations, CI workflow fixes).
- `docs:` Documentation changes (e.g., `README.md`, release notes).
- `refactor:` Code refactoring without functional changes.
- `test:` Test suite updates or adding boundary test cases.
- `ci:` GitHub Actions workflow or automation scripts.

---

## 🛠️ Execution Command Template

To ensure the commit metadata is accurately recorded, use the following `git commit` command pattern:

```bash
git -c user.name="Ivana" \
    -c user.email="ivana.gyro@gmail.com" \
    -c committer.name="Gemini 3.6 Flash" \
    -c committer.email="gemini@google.com" \
    commit -m "<type>(<scope>): <short summary>" \
           -m "Co-authored-by: Gemini 3.6 Flash <gemini@google.com>"
```

---

## 🧪 Verification & Code Quality Rules

Before committing any changes:

1. **Format & Lint**: Run `pixi run pre-commit run --all-files` (uses `ruff`, `ruff-format`, `pyproject-fmt`).
2. **Run Unit Tests**: Run `pixi run pytest` and verify all tests pass.
3. **Flat Layout Integrity**: Maintain flat repository structure (no `src/` directory).
