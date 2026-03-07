import datetime
import enum
import uuid

from sqlalchemy import Boolean, Column, DateTime, Enum, Index, String, Text
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


class ServiceStatus(str, enum.Enum):
    operational = "operational"
    degraded = "degraded"
    outage = "outage"
    offline = "offline"


class CheckType(str, enum.Enum):
    http = "http"
    command = "command"

class IncidentStatus(str, enum.Enum):
    investigating = "investigating"
    identified = "identified"
    monitoring = "monitoring"
    resolved = "resolved"


class Service(Base):
    __tablename__ = "services"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    url = Column(String, nullable=True)
    site_url = Column(String, nullable=True)
    status = Column(
        Enum(ServiceStatus), default=ServiceStatus.operational, nullable=False
    )
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime,
        default=datetime.datetime.utcnow,
        onupdate=datetime.datetime.utcnow,
        nullable=False,
    )
    group = Column(String, nullable=True)
    check_enabled = Column(Boolean, default=True, nullable=False)
    last_checked_at = Column(DateTime, nullable=True)
    is_public = Column(Boolean, default=True, nullable=False)
    on_demand = Column(Boolean, default=False, nullable=False)
    check_type = Column(
        Enum(CheckType), default=CheckType.http, nullable=False
    )
    check_command = Column(Text, nullable=True)


class Incident(Base):
    __tablename__ = "incidents"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    title = Column(String, nullable=False)
    body = Column(Text, nullable=False, default="")
    status = Column(
        Enum(IncidentStatus),
        default=IncidentStatus.investigating,
        nullable=False,
    )
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime,
        default=datetime.datetime.utcnow,
        onupdate=datetime.datetime.utcnow,
        nullable=False,
    )



class SessionStore(Base):
    __tablename__ = "session_store"

    token = Column(String, primary_key=True)
    username = Column(String, nullable=False)
    expires_at = Column(DateTime, nullable=False)


class ServiceStatusHistory(Base):
    __tablename__ = "service_status_history"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    service_id = Column(String, nullable=False)
    status = Column(Enum(ServiceStatus), nullable=False)
    started_at = Column(DateTime, nullable=False)

    __table_args__ = (
        Index("ix_ssh_service_started", "service_id", "started_at"),
    )