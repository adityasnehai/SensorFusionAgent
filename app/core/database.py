from sqlalchemy import create_engine, Column, String, Float, Integer, DateTime, Text, text
from sqlalchemy.orm import declarative_base, sessionmaker
from datetime import datetime

DATABASE_URL = "sqlite:///./sensorfusion.db"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine)

Base = declarative_base()


class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    hashed_password = Column(String)


class Job(Base):
    __tablename__ = "jobs"

    id = Column(String, primary_key=True, index=True)
    user_id = Column(String, index=True, nullable=True)
    status = Column(String, index=True, nullable=False, default="processing")
    progress = Column(Integer, nullable=False, default=0)
    research_suggestion_json = Column(Text, nullable=True)
    result_json = Column(Text, nullable=True)
    learning_metadata_json = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)
    alignment_mode = Column(String, nullable=True)
    output_path = Column(String, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)


class Experiment(Base):
    __tablename__ = "experiments"

    id = Column(String, primary_key=True, index=True)
    job_id = Column(String, index=True)
    final_score = Column(Float)
    sampling_rate = Column(Float)
    offset_ms = Column(Integer)
    unit_corrected = Column(String)


def init_db():
    Base.metadata.create_all(bind=engine)
    _ensure_jobs_table_compat()


def _ensure_jobs_table_compat():
    # Lightweight migration for existing local SQLite DBs.
    with engine.begin() as conn:
        cols = {
            row[1]
            for row in conn.execute(text("PRAGMA table_info(jobs)")).fetchall()
        }
        if not cols:
            return

        if "user_id" not in cols:
            conn.execute(text("ALTER TABLE jobs ADD COLUMN user_id VARCHAR"))
        if "progress" not in cols:
            conn.execute(text("ALTER TABLE jobs ADD COLUMN progress INTEGER DEFAULT 0"))
        if "result_json" not in cols:
            conn.execute(text("ALTER TABLE jobs ADD COLUMN result_json TEXT"))
        if "learning_metadata_json" not in cols:
            conn.execute(text("ALTER TABLE jobs ADD COLUMN learning_metadata_json TEXT"))
        if "research_suggestion_json" not in cols:
            conn.execute(text("ALTER TABLE jobs ADD COLUMN research_suggestion_json TEXT"))
        if "error_message" not in cols:
            conn.execute(text("ALTER TABLE jobs ADD COLUMN error_message TEXT"))
        if "alignment_mode" not in cols:
            conn.execute(text("ALTER TABLE jobs ADD COLUMN alignment_mode VARCHAR"))
        if "output_path" not in cols:
            conn.execute(text("ALTER TABLE jobs ADD COLUMN output_path VARCHAR"))
        if "created_at" not in cols:
            conn.execute(text("ALTER TABLE jobs ADD COLUMN created_at DATETIME"))
        if "completed_at" not in cols:
            conn.execute(text("ALTER TABLE jobs ADD COLUMN completed_at DATETIME"))

        conn.execute(
            text(
                "UPDATE jobs SET progress = COALESCE(progress, 0), "
                "created_at = COALESCE(created_at, CURRENT_TIMESTAMP)"
            )
        )
