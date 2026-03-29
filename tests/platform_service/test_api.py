import pytest
from fastapi.testclient import TestClient
from platform_service.main import app
from platform_service.database import Base, engine, SessionLocal

# Setup for testing
client = TestClient(app)

@pytest.fixture(scope="module")
def setup_db():
    Base.metadata.create_all(bind=engine)
    yield
    # No cleanup for now, as we use platform.db in implementation too.
    # In a real setup, we would use an in-memory db.

def test_root():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "BitDefense Platform API"}

def test_create_and_get_invariants():
    test_inv = {
        "contract": "0x1234567890123456789012345678901234567890",
        "type": "storage_check",
        "target": "balance",
        "storage": "0x1",
        "slot_type": "uint256"
    }
    
    # Create
    response = client.post("/invariants", json=test_inv)
    assert response.status_code == 200
    data = response.json()
    assert data["contract"] == test_inv["contract"]
    assert "id" in data
    
    # Get
    response = client.get("/invariants")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
    assert any(inv["contract"] == test_inv["contract"] for inv in data)
