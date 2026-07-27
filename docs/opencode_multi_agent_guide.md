# OpenCode Multi-Agent Terminal Setup & Orchestration Guide

This guide explains how to run **multiple OpenCode TUI instances** in separate terminal windows to work on different API tasks simultaneously **without file conflicts or race conditions**.

---

## 1. Why Git Worktrees are Essential for Multi-OpenCode Workflows

If you open multiple `opencode` terminals in the **exact same directory**, they will overwrite each other's code edits, causing git merge conflicts and corrupted code.

**Solution**: Use `git worktree` to create isolated working directories linked to the same Git repository. Each OpenCode terminal operates in its own folder and branch:

```
behavior-scoring/                    (Main repo)
├── .git/
├── behavior-scoring-builder/        (Terminal 1: OpenCode API Builder)
├── behavior-scoring-validator/      (Terminal 2: OpenCode Router Validator)
├── behavior-scoring-tester/         (Terminal 3: OpenCode Test Writer)
└── behavior-scoring-docs/           (Terminal 4: OpenCode Docs & Integration)
```

---

## 2. One-Click Setup Script (`scripts/setup_worktrees.ps1`)

Run this command in PowerShell to instantly create 4 isolated worktrees for your OpenCode instances:

```powershell
# Create worktrees for each OpenCode agent
git worktree add -b feature/api-builder ../behavior-scoring-builder
git worktree add -b feature/router-validator ../behavior-scoring-validator
git worktree add -b feature/test-writer ../behavior-scoring-tester
git worktree add -b feature/docs-integration ../behavior-scoring-docs
```

---

## 3. Terminal Assignment & OpenCode Launch Commands

Open 4 terminal tabs or windows and run these commands:

### 🖥️ Terminal 1: OpenCode API Builder

> **Role**: Implements new backend routes, schemas, and database functions.

```powershell
cd ..\behavior-scoring-builder
opencode
```

**Copy-Paste Initial Prompt for OpenCode 1**:

```text
You are OpenCode Instance 1: API Builder.
Your assignment: Implement new API endpoints for the behavior-scoring project.

Current Task: Implement POST /api/webhooks
1. Open app/schemas.py and create WebhookRegisterRequest and WebhookResponse models.
2. Open app/db.py and add helper functions to insert/list registered webhooks.
3. Open app/main.py and create the POST /api/webhooks endpoint.
4. Do NOT modify tests or docs files.
5. Run `pytest` to ensure existing tests still pass.
```

---

### 🖥️ Terminal 2: OpenCode Router Validator

> **Role**: Audits routes, checks parameter formatting, schema adherence, and security.

```powershell
cd ..\behavior-scoring-validator
opencode
```

**Copy-Paste Initial Prompt for OpenCode 2**:

```text
You are OpenCode Instance 2: Router & Schema Auditor.
Your assignment: Audit and validate API routes in app/main.py and app/schemas.py.

Current Task: Audit existing 12 API endpoints
1. Check app/main.py for RESTful naming consistency, query parameter bounds (ge, le), and response models.
2. Ensure every endpoint raises standard HTTPException on error with helpful detail messages.
3. Check app/schemas.py to ensure all string fields have max_length constraints.
4. Create a summary of audit findings in docs/router_audit_notes.md.
5. Do NOT edit database or business scoring logic directly.
```

---

### 🖥️ Terminal 3: OpenCode Test Writer (Playwright + Pytest)

> **Role**: Writes Playwright API tests and pytest unit tests for every endpoint.

```powershell
cd ..\behavior-scoring-tester
opencode
```

**Copy-Paste Initial Prompt for OpenCode 3**:

```text
You are OpenCode Instance 3: Test Automation Specialist.
Your assignment: Build Playwright API testing suite and pytest fixtures.

Current Task: Set up Playwright API tests for FastAPI
1. Create `tests/e2e/test_api_playwright.py`.
2. Use Playwright's `APIRequestContext` to write tests for GET /api/health, GET /api/rubric, POST /api/score, GET /api/scores.
3. Add pytest fixtures in tests/conftest.py to manage API test contexts.
4. Run `pytest tests/e2e` to verify your Playwright API tests pass.
5. Do NOT edit app/ main application logic.
```

---

### 🖥️ Terminal 4: OpenCode Docs & Integration

> **Role**: Maintains project documentation, API reference, and progress reports.

```powershell
cd ..\behavior-scoring-docs
opencode
```

**Copy-Paste Initial Prompt for OpenCode 4**:

```text
You are OpenCode Instance 4: Documentation & Integration Manager.
Your assignment: Keep documentation, API specs, and project reports in sync.

Current Task: Generate API Reference & Track Progress
1. Inspect app/main.py and create/update `docs/api_reference.md` documenting all endpoints, parameters, request bodies, and responses.
2. Update `docs/project_report.md` with current implementation progress.
3. Create a python script `scripts/generate_pdf_report.py` to compile docs into PDF format when needed.
4. Do NOT touch application routing code.
```

---

## 4. How to Sync & Merge Progress Across Terminals

When an OpenCode instance finishes its task in its worktree branch:

1. **Commit changes in that worktree**:

   ```powershell
   git add .
   git commit -m "feat(api): implemented webhook endpoint"
   ```
2. **Merge into API from your primary terminal**:

   ```powershell
   # In your main behavior-scoring directory (on branch 'API'):
   git merge feature/api-builder
   ```

3. **Rebase/pull latest API branch into other worktrees**:

   ```powershell
   # In behavior-scoring-tester:
   git rebase API
   ```

---

## 5. Summary Matrix for Your OpenCode Setup

| Terminal             | Branch                       | Focused Files                                      | Primary Task                                       |
| -------------------- | ---------------------------- | -------------------------------------------------- | -------------------------------------------------- |
| **OpenCode 1** | `feature/api-builder`      | `app/main.py`, `app/schemas.py`, `app/db.py` | Building new API routes & schemas                  |
| **OpenCode 2** | `feature/router-validator` | `app/main.py`, `app/config.py`                 | Schema auditing, CORS, security & route validation |
| **OpenCode 3** | `feature/test-writer`      | `tests/*`                                        | Playwright API test suite & unit tests             |
| **OpenCode 4** | `feature/docs-integration` | `docs/*`, `scripts/*`                          | Documentation generation & progress reporting      |
