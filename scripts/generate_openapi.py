import json
from platform_service.main import app
from fastapi.openapi.utils import get_openapi

def generate_spec():
    openapi_schema = get_openapi(
        title="BitDefense Platform API",
        version="1.0.0",
        description="Real-time on-chain analysis and security monitoring API",
        routes=app.routes,
    )
    with open("docs/openapi.json", "w") as f:
        json.dump(openapi_schema, f, indent=2)
    print("OpenAPI spec generated at docs/openapi.json")

if __name__ == "__main__":
    generate_spec()
