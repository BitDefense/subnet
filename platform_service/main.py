from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from platform_service.database import InvariantRecord, SessionLocal, init_db
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

# Initialize database
init_db()

app = FastAPI()

# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

class InvariantSchema(BaseModel):
    contract: str
    type: str
    target: str
    storage: str
    storage_slot_type: str

class InvariantResponse(InvariantSchema):
    id: int
    created_at: datetime
    is_active: bool

    class Config:
        from_attributes = True

@app.post("/invariants", response_model=InvariantResponse)
async def create_invariant(inv: InvariantSchema, db: Session = Depends(get_db)):
    db_inv = InvariantRecord(**inv.dict())
    db.add(db_inv)
    db.commit()
    db.refresh(db_inv)
    return db_inv

@app.get("/invariants", response_model=List[InvariantResponse])
async def get_invariants(db: Session = Depends(get_db)):
    invs = db.query(InvariantRecord).filter(InvariantRecord.is_active == True).all()
    return invs

@app.get("/")
async def root():
    return {"message": "BitDefense Platform API"}
