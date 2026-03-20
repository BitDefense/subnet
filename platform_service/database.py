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
    storage_slot_type = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)


engine = create_engine("sqlite:///./platform.db")
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db():
    Base.metadata.create_all(bind=engine)
