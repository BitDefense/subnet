# Platform Service REST API Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement a full REST API for managing dashboards, contracts, invariants, and defense actions with a flat-hierarchy retrieval pattern.

**Architecture:** Modular FastAPI implementation with SQLAlchemy ORM. Relationships are managed via association tables to support many-to-many connections between all entities.

**Tech Stack:** Python, FastAPI, SQLAlchemy, Pydantic, SQLite (current project default).

---

### Task 1: Update Database Models

**Files:**
- Modify: `platform_service/database.py`
- Test: `tests/platform_service/test_db_models.py` (New)

- [ ] **Step 1: Create a failing test for new models**
Create `tests/platform_service/test_db_models.py` to verify all tables can be created and relationships work.

- [ ] **Step 2: Run test to verify it fails**
Run: `pytest tests/platform_service/test_db_models.py`
Expected: FAIL (ImportError or AttributeError)

- [ ] **Step 3: Update `platform_service/database.py` with all models**
Include association tables and new models: `Dashboard`, `Contract`, `DefenseAction`. Update `InvariantRecord` with `network`.

- [ ] **Step 4: Run test to verify it passes**
Run: `pytest tests/platform_service/test_db_models.py`
Expected: PASS

### Task 2: Implement Pydantic Schemas

**Files:**
- Modify: `platform_service/main.py`
- Test: `tests/platform_service/test_schemas.py` (New)

- [ ] **Step 1: Define Schemas in `main.py`**
Create Pydantic models for `Contract`, `Dashboard`, `Invariant`, and `DefenseAction` including Create and Response versions.

- [ ] **Step 2: Verify schemas with a mock test**
Create `tests/platform_service/test_schemas.py` to ensure validation works as expected for complex types (JSON).

### Task 3: Implement CRUD Endpoints

**Files:**
- Modify: `platform_service/main.py`
- Test: `tests/platform_service/test_api_crud.py` (New)

- [ ] **Step 1: Implement basic CRUD for each entity**
Add `POST`, `GET`, `PUT`, `DELETE` for `/contracts`, `/dashboards`, `/defense-actions`. Refactor existing `/invariants`.

- [ ] **Step 2: Verify CRUD operations with tests**
Run: `pytest tests/platform_service/test_api_crud.py`

### Task 4: Relationship Management Endpoints

**Files:**
- Modify: `platform_service/main.py`
- Test: `tests/platform_service/test_api_relationships.py` (New)

- [ ] **Step 1: Implement linking endpoints**
Add endpoints like `POST /contracts/{id}/invariants/{inv_id}`, `POST /dashboards/{id}/contracts/{c_id}`, etc.

- [ ] **Step 2: Verify relationships in DB after linking**
Run: `pytest tests/platform_service/test_api_relationships.py`

### Task 5: Flat Hierarchy Dashboard Retrieval

**Files:**
- Modify: `platform_service/main.py`
- Test: `tests/platform_service/test_dashboard_hierarchy.py` (New)

- [ ] **Step 1: Update `GET /dashboards/{id}`**
Implement the logic to gather all related entities and format them into the flat hierarchy with ID arrays.

- [ ] **Step 2: Verify the final JSON structure matches the spec**
Run: `pytest tests/platform_service/test_dashboard_hierarchy.py`
