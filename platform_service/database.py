from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime

Base = declarative_base()


class InvariantRecord(Base):
    __tablename__ = "invariants"
    id = Column(Integer, primary_key=True)
    contract = Column(String, index=True, nullable=False)
    type = Column(String, nullable=False)
    target = Column(String, nullable=False)
    storage = Column(String, nullable=False)
    slot_type = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)


engine = create_engine("sqlite:///./platform.db")
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db():
    Base.metadata.create_all(bind=engine)
    mock_invariant = InvariantRecord(
        contract="0x81d40f21f12a8f0e3252bccb954d722d4c464b64",
        type="unauthorized minting",
        target="10000000000",
        storage="0x325f5c7d0dbc1b2b9548e916a6eec23104865d21322b600caedb790388daaa4e",
        slot_type="uint256",
    )
    add_invariant(mock_invariant)


def add_invariant(invariant: InvariantRecord):
    db = SessionLocal()
    try:
        db.add(invariant)
        db.commit()
    finally:
        db.close()
