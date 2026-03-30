# Design Spec: CORS Support for Platform Service

**Date:** 2026-03-30
**Status:** Approved
**Topic:** Adding Cross-Origin Resource Sharing (CORS) support to the FastAPI platform service.

## 1. Purpose
The BitDefense Platform Service provides a REST API for managing invariants, contracts, and dashboards. To allow web-based frontends (running on different domains/ports) to interact with this API, CORS must be enabled.

## 2. Success Criteria
- Web applications can make cross-origin requests to the Platform Service API.
- All HTTP methods (GET, POST, PUT, DELETE, etc.) are supported for cross-origin requests.
- All headers are allowed.
- The implementation follows FastAPI best practices using built-in middleware.

## 3. Architecture
The implementation will use FastAPI's `CORSMiddleware`.

### 3.1. Middleware Configuration
The following settings will be applied to the `CORSMiddleware`:

- **allow_origins:** `["*"]` (Allow all origins for initial development/testing).
- **allow_credentials:** `True` (Allow cookies/authentication headers in cross-origin requests).
- **allow_methods:** `["*"]` (Allow all HTTP methods).
- **allow_headers:** `["*"]` (Allow all headers).

## 4. Implementation Plan
1.  Modify `platform_service/main.py`.
2.  Import `CORSMiddleware` from `fastapi.middleware.cors`.
3.  Add the middleware to the `app` instance immediately after its creation.

## 5. Security Considerations
Allowing all origins (`"*"`) is suitable for development and initial testing. However, for production deployment, this should be restricted to specific trusted domains. This design prioritizes ease of integration for the current phase of the project.

## 6. Testing
Verification will be performed by:
1.  Running the platform service.
2.  Sending a `POST` or `GET` request with an `Origin` header from a different domain (e.g., using `curl` or a browser-based tool).
3.  Confirming the presence of `Access-Control-Allow-Origin: *` in the response headers.
