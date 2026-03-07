import datetime
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from statuspage.database.connection import get_db
from statuspage.database.models import Incident, IncidentStatus, Service, ServiceStatus

router = APIRouter(tags=["api"])


# ── Services ──────────────────────────────────────────────────────────────────


class ServiceCreate(BaseModel):
    name: str
    description: str | None = None
    url: str | None = None
    status: ServiceStatus = ServiceStatus.operational


class ServiceUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    url: str | None = None
    status: ServiceStatus | None = None


class ServiceOut(BaseModel):
    id: str
    name: str
    description: str | None
    url: str | None
    status: ServiceStatus
    created_at: datetime.datetime
    updated_at: datetime.datetime

    model_config = {"from_attributes": True}


@router.get("/services", response_model=list[ServiceOut])
def list_services(db: Session = Depends(get_db)):
    return db.query(Service).order_by(Service.created_at).all()


@router.post("/services", response_model=ServiceOut, status_code=201)
def create_service(body: ServiceCreate, db: Session = Depends(get_db)):
    service = Service(
        id=str(uuid.uuid4()),
        name=body.name,
        description=body.description,
        url=body.url,
        status=body.status,
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
    service_id: str, body: ServiceUpdate, db: Session = Depends(get_db)
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
    if body.status is not None:
        service.status = body.status
    service.updated_at = datetime.datetime.utcnow()
    db.commit()
    db.refresh(service)
    return service


@router.delete("/services/{service_id}", status_code=204)
def delete_service(service_id: str, db: Session = Depends(get_db)):
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
def create_incident(body: IncidentCreate, db: Session = Depends(get_db)):
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
    return incident


@router.get("/incidents/{incident_id}", response_model=IncidentOut)
def get_incident(incident_id: str, db: Session = Depends(get_db)):
    incident = db.query(Incident).filter(Incident.id == incident_id).first()
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    return incident


@router.patch("/incidents/{incident_id}", response_model=IncidentOut)
def update_incident(
    incident_id: str, body: IncidentUpdate, db: Session = Depends(get_db)
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
    return incident


@router.delete("/incidents/{incident_id}", status_code=204)
def delete_incident(incident_id: str, db: Session = Depends(get_db)):
    incident = db.query(Incident).filter(Incident.id == incident_id).first()
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    db.delete(incident)
    db.commit()
