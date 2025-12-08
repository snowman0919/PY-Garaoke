from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel, Field
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime
from sqlalchemy.orm import sessionmaker, declarative_base, Session
from sqlalchemy.sql import func
from datetime import datetime
from typing import List, Optional

DATABASE_URL = "sqlite:///./karaoke_ranks.db"
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class DBScore(Base):
    __tablename__ = "scores"
    id = Column(Integer, primary_key=True, index=True)
    song_id = Column(String, index=True)
    nickname = Column(String)
    score = Column(Float)
    pitch = Column(Float)
    rhythm = Column(Float)
    vibrato = Column(Float)
    timestamp = Column(DateTime, default=func.now())
Base.metadata.create_all(bind=engine)

class ScoreBase(BaseModel):
    song_id: str
    nickname: str = Field(..., max_length=50)
    score: float = Field(..., ge=0, le=100)
    pitch: float = Field(..., ge=0, le=100)
    rhythm: float = Field(..., ge=0, le=100)
    vibrato: float = Field(..., ge=0, le=100)

class ScoreCreate(ScoreBase):
    pass

class ScoreResponse(ScoreBase):
    id: int
    timestamp: datetime

    class Config:
        from_attributes = True

app = FastAPI(
    title="PY-Garaoke Ranking API",
    description="API for submitting and retrieving karaoke scores.",
    version="1.0.0",
)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.post("/api/submit_score", response_model=ScoreResponse)

def submit_score(score_data: ScoreCreate, db: Session = Depends(get_db)):
    db_score = DBScore(**score_data.model_dump())
    db.add(db_score)
    db.commit()
    db.refresh(db_score)
    return db_score

@app.get("/api/top_scores", response_model=List[ScoreResponse])

def get_top_scores(song_id: str, limit: int = 10, db: Session = Depends(get_db)):
    scores = db.query(DBScore).filter(DBScore.song_id == song_id).order_by(DBScore.score.desc()).limit(limit).all()
    return scores

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "server:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )