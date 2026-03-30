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
