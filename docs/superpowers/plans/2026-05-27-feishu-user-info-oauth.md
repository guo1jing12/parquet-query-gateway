# Feishu User Info OAuth Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Parquet Query Gateway fetch Feishu `open_id`, `name`, and optional `email` from the Feishu user info endpoint during OAuth login.

**Architecture:** Keep OpenCLI as a thin client that sends only the authorization code to the gateway. The gateway exchanges the code for a Feishu user access token, calls Feishu user info with that token, maps the resulting `open_id` or `email` to `auth.feishu_users`, and includes identity details in the gateway login response.

**Tech Stack:** FastAPI, Pydantic, urllib.request, Pytest.

---

### Task 1: Add Failing Tests

**Files:**
- Modify: `tests/test_feishu_auth.py`

- [x] **Step 1: Require the fake client to expose `get_user_info`**

Make `FakeFeishuOAuthClient.exchange_code()` return only the Feishu access token, and add `get_user_info()` returning `open_id`, `email`, and `name`.

- [x] **Step 2: Assert the login response includes user identity**

Assert `payload["user"]["name"] == "Alice Zhang"` and `payload["user"]["open_id"] == "ou_alice"`.

- [x] **Step 3: Run test to verify it fails**

Run: `pytest tests/test_feishu_auth.py -q`
Expected: FAIL because the current implementation does not call `get_user_info`.

### Task 2: Implement Gateway User Info Lookup

**Files:**
- Modify: `parquet_gateway/feishu.py`

- [x] **Step 1: Update protocol**

Add `get_user_info(access_token: str) -> dict` to `FeishuOAuthClientProtocol`.

- [x] **Step 2: Make `exchange_code` return the Feishu user access token**

Keep token exchange isolated in `FeishuOAuthClient.exchange_code()`.

- [x] **Step 3: Add `get_user_info`**

Call `https://open.feishu.cn/open-apis/authen/v1/user_info` with `Authorization: Bearer <access_token>`, validate `code == 0`, and return normalized `open_id`, `email`, and `name`.

- [x] **Step 4: Use the fetched profile for mapping**

In `exchange_feishu_code_for_gateway_token()`, call `client.get_user_info(feishu_token["access_token"])`, resolve the user from that profile, and include `open_id`, `email`, and `name` in the response user object.

### Task 3: Verify And Deploy

**Files:**
- Remote deploy target: `/home/ai_ds/parquet-query-gateway`

- [x] **Step 1: Run local tests**

Run: `pytest tests/test_feishu_auth.py -q`

- [x] **Step 2: Copy changed files to `intranet-184`**

Copy `parquet_gateway/feishu.py` and `tests/test_feishu_auth.py`.

- [x] **Step 3: Run remote target tests**

Run remote `pytest tests/test_feishu_auth.py -q`.

- [x] **Step 4: Restart uvicorn**

Restart the existing gateway process with the same `PARQUET_GATEWAY_CONFIG` and `PARQUET_GATEWAY_AUDIT_DB` environment variables.

- [x] **Step 5: Verify health**

Run remote `curl http://127.0.0.1:8080/health`.
