import datetime
import uuid

from fastapi import APIRouter, BackgroundTasks, Cookie, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from statuspage.database.connection import get_db
from statuspage.database.models import Incident, IncidentStatus, Service, ServiceStatus
from statuspage import auth as _auth

router = APIRouter(tags=["api"])


def require_auth(
    session_token: str | None = Cookie(default=None, alias="session-token"),
) -> str:
    if not session_token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    entry = _auth.get_session(session_token)
    if not entry:
        raise HTTPException(status_code=401, detail="Session expired or invalid")
    return entry["username"]


# ── Services ──────────────────────────────────────────────────────────────────


class ServiceCreate(BaseModel):
    name: str
    description: str | None = None
    url: str | None = None
    site_url: str | None = None
    status: ServiceStatus = ServiceStatus.operational
    group: str | None = None
    check_enabled: bool = True
    is_public: bool = True
    on_demand: bool = False


class ServiceUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    url: str | None = None
    site_url: str | None = None
    status: ServiceStatus | None = None
    group: str | None = None
    check_enabled: bool | None = None
    is_public: bool | None = None
    on_demand: bool | None = None


class ServiceOut(BaseModel):
    id: str
    name: str
    description: str | None
    url: str | None
    site_url: str | None
    status: ServiceStatus
    created_at: datetime.datetime
    updated_at: datetime.datetime
    group: str | None
    check_enabled: bool
    is_public: bool
    on_demand: bool
    last_checked_at: datetime.datetime | None

    model_config = {"from_attributes": True}


@router.get("/services", response_model=list[ServiceOut])
def list_services(
    db: Session = Depends(get_db),
    session_token: str | None = Cookie(default=None, alias="session-token"),
    include_private: bool = Query(default=False),
):
    if include_private:
        if not session_token or not _auth.get_session(session_token):
            raise HTTPException(status_code=401, detail="Not authenticated")
        return db.query(Service).order_by(Service.created_at).all()
    return db.query(Service).filter(Service.is_public.is_(True)).order_by(Service.created_at).all()


@router.post("/services", response_model=ServiceOut, status_code=201)
def create_service(body: ServiceCreate, db: Session = Depends(get_db), _user: str = Depends(require_auth)):
    service = Service(
        id=str(uuid.uuid4()),
        name=body.name,
        description=body.description,
        url=body.url,
        site_url=body.site_url,
        status=body.status,
        group=body.group,
        check_enabled=body.check_enabled,
        is_public=body.is_public,
        on_demand=body.on_demand,
        created_at=datetime.datetime.utcnow(),
        updated_at=datetime.datetime.utcnow(),
    )
    db.add(service)
    db.commit()
    db.refresh(service)
    return service


@router.get("/services/{service_id}", response_model=ServiceOut)
def get_service(service_id: str, db: Session = Depends(get_db)):
    service = db.query(Service).filter(Service.id == service_id).first()
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")
    return service


@router.patch("/services/{service_id}", response_model=ServiceOut)
def update_service(
    service_id: str, body: ServiceUpdate, db: Session = Depends(get_db), _user: str = Depends(require_auth)
):
    service = db.query(Service).filter(Service.id == service_id).first()
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")
    if body.name is not None:
        service.name = body.name
    if body.description is not None:
        service.description = body.description
    if body.url is not None:
        service.url = body.url
    if "site_url" in body.model_fields_set:
        service.site_url = body.site_url
    if body.status is not None:
        service.status = body.status
    if "group" in body.model_fields_set:
        service.group = body.group
    if body.check_enabled is not None:
        service.check_enabled = body.check_enabled
    if body.is_public is not None:
        service.is_public = body.is_public
    if body.on_demand is not None:
        service.on_demand = body.on_demand
    service.updated_at = datetime.datetime.utcnow()
    db.commit()
    db.refresh(service)
    return service


@router.delete("/services/{service_id}", status_code=204)
def delete_service(service_id: str, db: Session = Depends(get_db), _user: str = Depends(require_auth)):
    service = db.query(Service).filter(Service.id == service_id).first()
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")
    db.delete(service)
    db.commit()


# ── Incidents ─────────────────────────────────────────────────────────────────


class IncidentCreate(BaseModel):
    title: str
    body: str = ""
    status: IncidentStatus = IncidentStatus.investigating


class IncidentUpdate(BaseModel):
    title: str | None = None
    body: str | None = None
    status: IncidentStatus | None = None


class IncidentOut(BaseModel):
    id: str
    title: str
    body: str
    status: IncidentStatus
    created_at: datetime.datetime
    updated_at: datetime.datetime

    model_config = {"from_attributes": True}


@router.get("/incidents", response_model=list[IncidentOut])
def list_incidents(db: Session = Depends(get_db)):
    return db.query(Incident).order_by(Incident.created_at.desc()).all()


@router.post("/incidents", response_model=IncidentOut, status_code=201)
def create_incident(
    body: IncidentCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    _user: str = Depends(require_auth),
):
    incident = Incident(
        id=str(uuid.uuid4()),
        title=body.title,
        body=body.body,
        status=body.status,
        created_at=datetime.datetime.utcnow(),
        updated_at=datetime.datetime.utcnow(),
    )
    db.add(incident)
    db.commit()
    db.refresh(incident)
    from statuspage import notifier as _notifier
    background_tasks.add_task(
        _notifier.notify_incident, "created", incident.title, incident.status.value, incident.body
    )
    return incident


@router.get("/incidents/{incident_id}", response_model=IncidentOut)
def get_incident(incident_id: str, db: Session = Depends(get_db)):
    incident = db.query(Incident).filter(Incident.id == incident_id).first()
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    return incident


@router.patch("/incidents/{incident_id}", response_model=IncidentOut)
def update_incident(
    incident_id: str,
    body: IncidentUpdate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    _user: str = Depends(require_auth),
):
    incident = db.query(Incident).filter(Incident.id == incident_id).first()
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    if body.title is not None:
        incident.title = body.title
    if body.body is not None:
        incident.body = body.body
    if body.status is not None:
        incident.status = body.status
    incident.updated_at = datetime.datetime.utcnow()
    db.commit()
    db.refresh(incident)
    from statuspage import notifier as _notifier
    background_tasks.add_task(
        _notifier.notify_incident,
        "updated",
        incident.title,
        incident.status.value,
        incident.body,
    )
    return incident


@router.delete("/incidents/{incident_id}", status_code=204)
def delete_incident(incident_id: str, db: Session = Depends(get_db), _user: str = Depends(require_auth)):
    incident = db.query(Incident).filter(Incident.id == incident_id).first()
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    db.delete(incident)
    db.commit()
