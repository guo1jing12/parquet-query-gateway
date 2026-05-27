# Dataset Discovery Editor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let admins discover Parquet datasets and field schemas from `settings.data_root`, then add them into the visual config editor.

**Architecture:** Add a backend discovery helper that scans first-level data directories under `data_root`, reads one Parquet file per directory with PyArrow, and returns candidate dataset ids, glob paths, columns, and whether the dataset is already configured. Add an admin-only endpoint for this helper. Extend the UI dataset tab with a discovery button and add-to-config action.

**Tech Stack:** FastAPI, PyArrow, PyYAML, vanilla HTML/CSS/JS.

---

### Task 1: Backend Discovery

**Files:**
- Modify: `tests/test_app.py`
- Modify: `parquet_gateway/admin_config.py`
- Modify: `parquet_gateway/app.py`

- [x] **Step 1: Write failing tests**

Add tests that an admin can discover Parquet directories and columns, and non-admins are rejected.

- [x] **Step 2: Implement scanner**

Scan direct child directories of `settings.data_root`; for each directory containing `.parquet`, read schema from the first file and return fields.

- [x] **Step 3: Add admin endpoint**

Add `GET /admin/config/discover-datasets`.

### Task 2: UI Discovery

**Files:**
- Modify: `parquet_gateway/admin_ui.py`

- [x] **Step 1: Add discovery controls**

Add a discover button and discovered dataset list to the dataset tab.

- [x] **Step 2: Add dataset to YAML**

When clicked, insert a dataset config with `roles: [analyst, admin]` and matching columns for both roles.

### Task 3: Verify And Deploy

**Files:**
- Remote deploy target: `/home/ai_ds/parquet-query-gateway`

- [x] **Step 1: Run local tests**

Run `pytest -q`.

- [x] **Step 2: Copy changed files to `intranet-184`**

Copy app, admin_config, admin_ui, tests, and plan.

- [x] **Step 3: Restart gateway**

Restart uvicorn.

- [x] **Step 4: Verify health and UI**

Check `/health` and `/admin/config-ui`.
