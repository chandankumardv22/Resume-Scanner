# ==============================================================================
# TECH STACK: [SQLAlchemy 2.0 ORM] - Relational Data Models for PostgreSQL & SQLite
# Defines schemas for Users, Sessions, Analysis Records, and Platform Stats
# ==============================================================================
from __future__ import annotations

import json
import time
from typing import Any

from sqlalchemy import BigInteger, Column, Float, Integer, String, Text
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class User(Base):
    """Stores registered candidate accounts with PBKDF2 hashed credentials."""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    name = Column(String(255), nullable=False)
    phone = Column(String(50), default="")
    salt = Column(String(64), nullable=False)
    password_hash = Column(String(128), nullable=False)
    created_at = Column(BigInteger, default=lambda: int(time.time()), nullable=False)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "email": self.email,
            "phone": self.phone or "",
            "created_at": self.created_at,
        }


class UserSession(Base):
    """Persistent session store for authenticated tokens."""
    __tablename__ = "user_sessions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    token = Column(String(64), unique=True, index=True, nullable=False)
    email = Column(String(255), index=True, nullable=False)
    expires_at = Column(Float, nullable=False)
    created_at = Column(Float, default=lambda: time.time(), nullable=False)


class AnalysisRecord(Base):
    """Tracks resume analysis history and ATS scoring breakdown."""
    __tablename__ = "analysis_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_email = Column(String(255), index=True, nullable=True)
    candidate_name = Column(String(255), default="Unknown")
    detected_domain = Column(String(100), default="General")
    predicted_role = Column(String(150), default="Software Professional")
    ats_score = Column(Integer, default=50)
    matched_skills = Column(Text, default="[]")
    missing_skills = Column(Text, default="[]")
    analysis_source = Column(String(50), default="heuristic")
    created_at = Column(BigInteger, default=lambda: int(time.time()), nullable=False)

    def get_matched_skills(self) -> list[str]:
        try:
            return json.loads(self.matched_skills or "[]")
        except Exception:
            return []

    def get_missing_skills(self) -> list[str]:
        try:
            return json.loads(self.missing_skills or "[]")
        except Exception:
            return []


class PlatformMetric(Base):
    """Platform-wide operational counters and telemetry."""
    __tablename__ = "platform_metrics"

    id = Column(Integer, primary_key=True, autoincrement=True)
    metric_key = Column(String(100), unique=True, index=True, nullable=False)
    metric_value = Column(BigInteger, default=0, nullable=False)
