import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from platform_service.database import Base, InvariantRecord, Dashboard, Contract, DefenseAction

# Use an in-memory SQLite database for testing
DATABASE_URL = "sqlite:///:memory:"

@pytest.fixture
def db_session():
    engine = create_engine(DATABASE_URL)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()
    Base.metadata.drop_all(engine)

def test_create_models(db_session):
    # Test Dashboard creation
    dashboard = Dashboard(name="Main Dashboard")
    db_session.add(dashboard)
    db_session.commit()
    assert dashboard.id is not None
    assert dashboard.name == "Main Dashboard"

    # Test Contract creation
    contract = Contract(
        variables={"owner": "0x123"},
        address="0x81d40f21f12a8f0e3252bccb954d722d4c464b64",
        network="ethereum"
    )
    db_session.add(contract)
    db_session.commit()
    assert contract.id is not None
    assert contract.network == "ethereum"

    # Test DefenseAction creation
    action = DefenseAction(
        type="telegram",
        tg_api_key="key",
        tg_chat_id="chat",
        network="ethereum"
    )
    db_session.add(action)
    db_session.commit()
    assert action.id is not None

    # Test InvariantRecord update
    invariant = InvariantRecord(
        contract="0x81d40f21f12a8f0e3252bccb954d722d4c464b64",
        type="unauthorized minting",
        target="1000",
        storage="0x0",
        slot_type="uint256",
        network="ethereum"
    )
    db_session.add(invariant)
    db_session.commit()
    assert invariant.network == "ethereum"

def test_relationships(db_session):
    # Create entities
    dash = Dashboard(name="Security Ops")
    cont = Contract(address="0x1", network="polygon")
    inv = InvariantRecord(contract="0x1", type="mint", target="0", storage="0x0", slot_type="u256", network="polygon")
    act = DefenseAction(type="pause", network="polygon")

    # Link them
    dash.contracts.append(cont)
    dash.invariants.append(inv)
    dash.defense_actions.append(act)
    cont.invariants.append(inv)
    inv.defense_actions.append(act)

    db_session.add_all([dash, cont, inv, act])
    db_session.commit()

    # Verify links
    reloaded_dash = db_session.query(Dashboard).filter_by(name="Security Ops").first()
    assert cont in reloaded_dash.contracts
    assert inv in reloaded_dash.invariants
    assert act in reloaded_dash.defense_actions
    assert inv in cont.invariants
    assert act in inv.defense_actions
