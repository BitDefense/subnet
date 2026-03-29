import pytest
from platform_service.main import (
    InvariantSchema, ContractCreate, DefenseActionCreate, DashboardCreate
)

def test_invariant_schema():
    data = {
        "contract": "0x123",
        "type": "test",
        "target": "target",
        "storage": "storage",
        "slot_type": "uint256",
        "network": "ethereum",
        "defense_action_ids": [1, 2]
    }
    schema = InvariantSchema(**data)
    assert schema.contract == "0x123"
    assert schema.defense_action_ids == [1, 2]

def test_invariant_schema_defaults():
    data = {
        "contract": "0x123",
        "type": "test",
        "target": "target",
        "storage": "storage",
        "slot_type": "uint256"
    }
    schema = InvariantSchema(**data)
    assert schema.network == "ethereum"
    assert schema.defense_action_ids == []

def test_contract_schema():
    data = {
        "address": "0x123",
        "network": "ethereum",
        "variables": {"a": 1},
        "invariant_ids": [1]
    }
    schema = ContractCreate(**data)
    assert schema.variables == {"a": 1}
    assert schema.invariant_ids == [1]

def test_contract_schema_defaults():
    data = {
        "address": "0x123",
        "network": "ethereum"
    }
    schema = ContractCreate(**data)
    assert schema.variables == {}
    assert schema.invariant_ids == []

def test_defense_action_schema():
    data = {
        "type": "telegram",
        "network": "ethereum",
        "tg_api_key": "api",
        "tg_chat_id": "chat"
    }
    schema = DefenseActionCreate(**data)
    assert schema.type == "telegram"
    assert schema.tg_api_key == "api"
    assert schema.role_id is None

def test_dashboard_schema():
    data = {
        "name": "My Dashboard",
        "contract_ids": [1],
        "invariant_ids": [2],
        "defense_action_ids": [3]
    }
    schema = DashboardCreate(**data)
    assert schema.name == "My Dashboard"
    assert schema.contract_ids == [1]
    assert schema.invariant_ids == [2]
    assert schema.defense_action_ids == [3]

def test_dashboard_schema_defaults():
    data = {"name": "Empty Dashboard"}
    schema = DashboardCreate(**data)
    assert schema.contract_ids == []
    assert schema.invariant_ids == []
    assert schema.defense_action_ids == []
