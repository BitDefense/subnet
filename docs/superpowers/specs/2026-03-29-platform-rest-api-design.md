# Design Spec: Platform Service REST API

**Date:** 2026-03-29
**Status:** Approved
**Topic:** Security Dashboard REST API Implementation

## Overview
This specification defines the REST API for the Platform Service to manage security dashboards, smart contract profiles, invariants, and defense actions. It supports decentralized security monitoring for the BitDefense subnet.

## Architecture
The system follows a modular FastAPI approach, utilizing SQLAlchemy for ORM and Pydantic for data validation.

### Database Models
We will implement the following tables (SQLAlchemy):

1.  **Dashboard (`dashboard`)**
    - `id`: BIGINT (PK)
    - `name`: TEXT (Required)
2.  **Contract (`contracts`)**
    - `id`: BIGINT (PK)
    - `variables`: JSON (Required)
    - `address`: TEXT (Required)
    - `network`: TEXT (Required)
3.  **Invariant (`invariants`)**
    - `id`: BIGINT (PK)
    - `contract`: TEXT (Required)
    - `type`: TEXT (Required)
    - `target`: TEXT (Required)
    - `storage`: TEXT (Required)
    - `slot_type`: TEXT (Required)
    - `created_at`: TIMESTAMP (Auto)
    - `is_active`: BOOLEAN (Default: True)
    - `network`: TEXT (Required)
4.  **Defense Action (`defense_action`)**
    - `id`: BIGINT (PK)
    - `type`: TEXT (Required)
    - `tg_api_key`: TEXT (Optional)
    - `tg_chat_id`: TEXT (Optional)
    - `role_id`: TEXT (Optional)
    - `function_sig`: TEXT (Optional)
    - `calldata`: TEXT (Optional)
    - `network`: TEXT (Required)

### Relationships (Many-to-Many)
Implemented via association tables:
- `dashboard_contracts`: Links dashboards to contracts.
- `dashboard_invariants`: Links dashboards to invariants.
- `dashboard_defense_actions`: Links dashboards to defense actions.
- `contract_invariants`: Links contracts to their invariants.
- `invariant_defense_actions`: Links invariants to their defense actions.

## API Endpoints

### CRUD Operations
- `/dashboards`: `GET`, `POST`, `PUT`, `DELETE`
- `/contracts`: `GET`, `POST`, `PUT`, `DELETE`
- `/invariants`: `GET`, `POST`, `PUT`, `DELETE`
- `/defense-actions`: `GET`, `POST`, `PUT`, `DELETE`

### Relationship Management
Endpoints to link/unlink entities (e.g., `POST /contracts/{id}/invariants/{inv_id}`).

### Dashboard Retrieval Pattern
`GET /dashboards/{id}` will return a **Flat Hierarchy**:
- `contracts`: List of full contract objects, each with `invariant_ids`.
- `invariants`: List of full invariant objects, each with `defense_action_ids`.
- `defense_actions`: List of full defense action objects.

## Success Criteria
1.  All CRUD operations are functional and validated.
2.  Nested dashboard retrieval returns the correct flat hierarchy with IDs.
3.  Database constraints (FKs) are correctly enforced in SQLAlchemy.
4.  Documentation is updated to reflect the new API surface.

## Testing Strategy
- **Unit Tests:** Verify Pydantic validation and CRUD logic in isolation.
- **Integration Tests:** Verify complex relationship management and the flat hierarchy retrieval.
- **Database Tests:** Use a test database to verify SQLAlchemy migrations and FK constraints.
