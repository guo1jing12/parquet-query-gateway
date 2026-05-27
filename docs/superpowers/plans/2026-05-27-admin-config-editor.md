# Admin Config Editor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an admin-only web editor for reading, validating, and saving `production.yml`.

**Architecture:** FastAPI serves a single-page admin UI and JSON endpoints under `/admin/config*`. A focused helper module reads the configured YAML file, redacts secrets for display, validates edited YAML through `GatewayConfig`, backs up the current file, saves the replacement, and clears the config cache so future app instances use the new config.

**Tech Stack:** FastAPI, PyYAML, Pydantic, vanilla HTML/CSS/JS.

---

### Task 1: Backend Config Endpoints

**Files:**
- Modify: `tests/test_app.py`
- Create: `parquet_gateway/admin_config.py`
- Modify: `parquet_gateway/app.py`

- [x] **Step 1: Write failing tests**

Add tests for admin-only config reads, non-admin rejection, redacted secrets, YAML validation, backup creation, and config cache reload.

- [x] **Step 2: Implement helper functions**

Create `read_admin_config`, `validate_admin_config_yaml`, and `save_admin_config_yaml`.

- [x] **Step 3: Add FastAPI routes**

Add `GET /admin/config`, `PUT /admin/config`, and `POST /admin/config/reload`.

### Task 2: Web UI

**Files:**
- Create: `parquet_gateway/admin_ui.py`
- Modify: `parquet_gateway/app.py`

- [x] **Step 1: Add page route**

Add `GET /admin/config-ui` that returns static HTML.

- [x] **Step 2: Build visual editor**

Build a TrendRadar-inspired single HTML page with token input, tabs for Feishu users/datasets/raw YAML, forms for adding users, editing roles and attributes, raw YAML preview, save, reload, and copy.

### Task 3: Verify And Deploy

**Files:**
- Remote deploy target: `/home/ai_ds/parquet-query-gateway`

- [x] **Step 1: Run local tests**

Run `pytest -q`.

- [x] **Step 2: Smoke test UI route**

Use FastAPI TestClient to check `/admin/config-ui` returns HTML.

- [x] **Step 3: Copy changed files to `intranet-184`**

Copy app, helper modules, tests, and docs.

- [x] **Step 4: Restart gateway**

Restart uvicorn with the existing environment variables.

- [x] **Step 5: Verify health and UI**

Run `curl http://127.0.0.1:8080/health` and fetch `/admin/config-ui`.
