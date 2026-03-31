from sqlalchemy import (
    create_engine,
    Column,
    Integer,
    String,
    Boolean,
    DateTime,
    ForeignKey,
    Table,
    JSON,
)
from sqlalchemy.orm import relationship, declarative_base, sessionmaker
from datetime import datetime

Base = declarative_base()

# Association tables
dashboard_contracts = Table(
    "dashboard_contracts",
    Base.metadata,
    Column("dashboard_id", Integer, ForeignKey("dashboards.id"), primary_key=True),
    Column("contract_id", Integer, ForeignKey("contracts.id"), primary_key=True),
)

dashboard_invariants = Table(
    "dashboard_invariants",
    Base.metadata,
    Column("dashboard_id", Integer, ForeignKey("dashboards.id"), primary_key=True),
    Column("invariant_id", Integer, ForeignKey("invariants.id"), primary_key=True),
)

dashboard_defense_actions = Table(
    "dashboard_defense_actions",
    Base.metadata,
    Column("dashboard_id", Integer, ForeignKey("dashboards.id"), primary_key=True),
    Column(
        "defense_action_id", Integer, ForeignKey("defense_actions.id"), primary_key=True
    ),
)

contract_invariants = Table(
    "contract_invariants",
    Base.metadata,
    Column("contract_id", Integer, ForeignKey("contracts.id"), primary_key=True),
    Column("invariant_id", Integer, ForeignKey("invariants.id"), primary_key=True),
)

invariant_defense_actions = Table(
    "invariant_defense_actions",
    Base.metadata,
    Column("invariant_id", Integer, ForeignKey("invariants.id"), primary_key=True),
    Column(
        "defense_action_id", Integer, ForeignKey("defense_actions.id"), primary_key=True
    ),
)


class Dashboard(Base):
    __tablename__ = "dashboards"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)

    contracts = relationship(
        "Contract", secondary=dashboard_contracts, back_populates="dashboards"
    )
    invariants = relationship(
        "InvariantRecord", secondary=dashboard_invariants, back_populates="dashboards"
    )
    defense_actions = relationship(
        "DefenseAction",
        secondary=dashboard_defense_actions,
        back_populates="dashboards",
    )


class Contract(Base):
    __tablename__ = "contracts"
    id = Column(Integer, primary_key=True)
    variables = Column(JSON, nullable=True)
    address = Column(String, index=True, nullable=False)
    network = Column(String, nullable=False)

    dashboards = relationship(
        "Dashboard", secondary=dashboard_contracts, back_populates="contracts"
    )
    invariants = relationship(
        "InvariantRecord", secondary=contract_invariants, back_populates="contracts"
    )


class InvariantRecord(Base):
    __tablename__ = "invariants"
    id = Column(Integer, primary_key=True)
    contract = Column(String, index=True, nullable=False)
    type = Column(String, nullable=False)
    variable = Column(String, nullable=False)
    target = Column(String, nullable=False)
    storage = Column(String, nullable=False)
    slot_type = Column(String, nullable=False)
    network = Column(String, nullable=False, default="ethereum")
    created_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)

    dashboards = relationship(
        "Dashboard", secondary=dashboard_invariants, back_populates="invariants"
    )
    contracts = relationship(
        "Contract", secondary=contract_invariants, back_populates="invariants"
    )
    defense_actions = relationship(
        "DefenseAction",
        secondary=invariant_defense_actions,
        back_populates="invariants",
    )


class DefenseAction(Base):
    __tablename__ = "defense_actions"
    id = Column(Integer, primary_key=True)
    type = Column(String, nullable=False)
    tg_api_key = Column(String, nullable=True)
    tg_chat_id = Column(String, nullable=True)
    role_id = Column(String, nullable=True)
    function_sig = Column(String, nullable=True)
    calldata = Column(String, nullable=True)
    network = Column(String, nullable=False)

    dashboards = relationship(
        "Dashboard",
        secondary=dashboard_defense_actions,
        back_populates="defense_actions",
    )
    invariants = relationship(
        "InvariantRecord",
        secondary=invariant_defense_actions,
        back_populates="defense_actions",
    )


engine = None
SessionLocal = None


def init_db(database_url: str):
    global engine, SessionLocal
    # Check for sqlite and add check_same_thread for concurrency
    if database_url.startswith("sqlite"):
        engine = create_engine(database_url, connect_args={"check_same_thread": False})
    else:
        engine = create_engine(database_url)

    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)


def add_invariant(invariant: InvariantRecord):
    if SessionLocal is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")
    db = SessionLocal()
    try:
        db.add(invariant)
        db.commit()
    finally:
        db.close()
