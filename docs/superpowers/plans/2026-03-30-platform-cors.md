# Platform Service CORS Support Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enable Cross-Origin Resource Sharing (CORS) in the FastAPI platform service to allow web frontends to interact with the API.

**Architecture:** Utilize FastAPI's built-in `CORSMiddleware` configured to allow all origins, methods, and headers for initial development.

**Tech Stack:** Python, FastAPI.

---

### Task 1: Add Failing CORS Test

**Files:**
- Create: `tests/platform_service/test_cors.py`

- [ ] **Step 1: Write the failing test**

```python
from fastapi.testclient import TestClient
from platform_service.main import app

client = TestClient(app)

def test_cors_headers():
    # Simulate a CORS preflight request
    response = client.options(
        "/",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
        },
    )
    # If CORS is not enabled, this usually returns a 405 or 404 depending on the route,
    # and won't include the expected CORS headers.
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "*"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/platform_service/test_cors.py -v`
Expected: FAIL (likely 405 Method Not Allowed or 404, and missing headers)

- [ ] **Step 3: Commit**

```bash
git add tests/platform_service/test_cors.py
git commit -m "test: add failing CORS verification test"
```

---

### Task 2: Implement CORSMiddleware

**Files:**
- Modify: `platform_service/main.py`

- [ ] **Step 1: Add CORSMiddleware to FastAPI app**

```python
# platform_service/main.py

# ... existing imports ...
from fastapi.middleware.cors import CORSMiddleware

# ... after app = FastAPI(lifespan=lifespan) ...

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

- [ ] **Step 2: Run the test to verify it passes**

Run: `pytest tests/platform_service/test_cors.py -v`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add platform_service/main.py
git commit -m "feat: enable CORS with allow-all policy"
```

---

### Task 3: Final Verification

- [ ] **Step 1: Run all platform service tests**

Run: `pytest tests/platform_service/`
Expected: PASS (ensure no regressions in existing API tests)

- [ ] **Step 2: Commit any necessary final adjustments**

```bash
# (If any adjustments were needed, otherwise skip)
# git commit -m "chore: final platform service verification"
```
