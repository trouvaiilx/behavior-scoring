# Behavior Scoring — Task Tracker

## Phase 1: Foundation (Week 1-2)

- [ ] Verify all 12 existing APIs work correctly (TUI 5)
- [ ] Set up Playwright for API testing (TUI 3)
- [ ] Write E2E tests for health, score, and batch endpoints (TUI 3: T3.1-T3.3)
- [ ] Router naming & schema consistency review (TUI 2: T2.1-T2.4)
- [ ] Choose and install TUI orchestrator (You)
- [ ] Set up `tests/unit/`, `tests/integration/`, `tests/e2e/` directory structure (TUI 3)
- [ ] Create `requirements-dev.txt` with Playwright + test deps (TUI 1)
- [ ] Create `docs/` directory and initial `api_reference.md` (TUI 4)

## Phase 2: Core New APIs (Week 3-4) — ✅ COMPLETED

- [x] Implement Webhook API — `POST /api/webhooks` (TUI 1: T1.1)
- [x] Implement Auth/API Key — `POST /api/auth/token` (TUI 1: T1.2)
- [x] Implement Candidate Import — `POST /api/candidates/import` (TUI 1: T1.4)
- [x] Router validation for new endpoints (TUI 2: T2.6)
- [x] Write tests for webhook, auth, import APIs via Playwright (TUI 3)
- [x] Update API reference documentation & scraper bridge script (TUI 4)
- [x] Create Playwright scraper bridge for candidate-import JSON (TUI 4; awaits import endpoint)

## Phase 3: Advanced APIs + Integration (Week 5-6)

- [ ] Implement Rubric Versioning — `POST /api/rubric/versions` (TUI 1: T1.3)
- [ ] Implement Usage Stats — `GET /api/usage/stats` (TUI 1: T1.5)
- [ ] Implement Report Generation — `POST /api/reports/generate` (TUI 1)
- [ ] Bridge Playwright scraper (iSpy) with scoring API (TUI 5)
- [ ] Set up Windmill or Activepieces for workflow automation (You)
- [ ] Full integration test suite (TUI 5: T5.1-T5.5)

## Phase 4: Polish & Report (Week 7-8)

- [ ] Implement Multi-Model comparison API (TUI 1: T1.6)
- [ ] Implement Audit Log API (TUI 1)
- [ ] Complete Playwright E2E test suite (TUI 3: T3.6)
- [ ] Generate final PDF report (TUI 4: T4.6)
- [ ] Demo preparation and walkthrough (You)
