import base64
import datetime
import uuid
from collections import defaultdict

from fastapi import APIRouter, BackgroundTasks, Cookie, Depends, HTTPException, Query
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session

from statuspage.database.connection import get_db
from statuspage.database.models import CheckType, Incident, IncidentStatus, Service, ServiceStatus, ServiceStatusHistory, EmailSubscriber, TelegramConfig, DiscordConfig, DiscordDestination
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


def _now() -> datetime.datetime:
    return datetime.datetime.utcnow()


def _get_or_404(db, model, id: str, detail: str = "Not found"):
    obj = db.query(model).filter(model.id == id).first()
    if obj is None:
        raise HTTPException(status_code=404, detail=detail)
    return obj


class _UTCModel(BaseModel):
    model_config = {"from_attributes": True}

    @field_validator("*", mode="before")
    @classmethod
    def _utc(cls, v):
        if isinstance(v, datetime.datetime) and v.tzinfo is None:
            return v.replace(tzinfo=datetime.timezone.utc)
        return v


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
    muted: bool = False
    check_type: CheckType = CheckType.http
    check_command: str | None = None
    failure_threshold: int = 2


class ServiceUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    url: str | None = None
    site_url: str | None = None
    status: ServiceStatus | None = None
    group: str | None = None
    check_enabled: bool | None = None
    is_public: bool | None = None
    muted: bool | None = None
    check_type: CheckType | None = None
    check_command: str | None = None
    failure_threshold: int | None = None


class ServiceOut(_UTCModel):
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
    muted: bool
    last_checked_at: datetime.datetime | None
    check_type: CheckType
    check_command: str | None
    failure_threshold: int



class ServicePublicOut(_UTCModel):
    id: str
    name: str
    description: str | None
    site_url: str | None
    status: ServiceStatus
    created_at: datetime.datetime
    updated_at: datetime.datetime
    group: str | None
    last_checked_at: datetime.datetime | None

@router.get("/services")
def list_services(
    db: Session = Depends(get_db),
    session_token: str | None = Cookie(default=None, alias="session-token"),
    include_private: bool = Query(default=False),
):
    if include_private:
        if not session_token or not _auth.get_session(session_token):
            raise HTTPException(status_code=401, detail="Not authenticated")
        return [
            ServiceOut.model_validate(s)
            for s in db.query(Service).order_by(Service.created_at).all()
        ]
    return [
        ServicePublicOut.model_validate(s)
        for s in db.query(Service).filter(Service.is_public.is_(True)).order_by(Service.created_at).all()
    ]


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
        muted=body.muted,
        check_type=body.check_type,
        check_command=body.check_command,
        failure_threshold=body.failure_threshold,
        created_at=_now(),
        updated_at=_now(),
    )
    db.add(service)
    now = _now()
    db.add(ServiceStatusHistory(service_id=service.id, status=service.status, started_at=now))
    db.commit()
    db.refresh(service)
    return service


@router.get("/services/{service_id}", response_model=ServiceOut)
def get_service(service_id: str, db: Session = Depends(get_db), _user: str = Depends(require_auth)):
    return _get_or_404(db, Service, service_id, "Service not found")


@router.patch("/services/{service_id}", response_model=ServiceOut)
def update_service(
    service_id: str, body: ServiceUpdate, db: Session = Depends(get_db), _user: str = Depends(require_auth)
):
    service = _get_or_404(db, Service, service_id, "Service not found")
    _non_nullable = {'name', 'status', 'check_enabled', 'is_public', 'muted', 'check_type', 'failure_threshold'}
    for field in body.model_fields_set:
        value = getattr(body, field)
        if value is None and field in _non_nullable:
            continue
        setattr(service, field, value)
    service.updated_at = _now()
    db.commit()
    db.refresh(service)
    return service


@router.delete("/services/{service_id}", status_code=204)
def delete_service(service_id: str, db: Session = Depends(get_db), _user: str = Depends(require_auth)):
    service = _get_or_404(db, Service, service_id, "Service not found")
    db.delete(service)
    db.commit()


# ── History ──────────────────────────────────────────────────────────────────


def _compute_daily_history(
    rows: list, days: int, now: datetime.datetime
) -> list[dict]:
    """Return one {date, status} entry per day for the last `days` days.

    For each day: worst status of all events that started that day, carry-forward
    the last known status when no event occurred, 'no_data' if no history at all.
    Outage events that lasted ≤60 s and are not currently ongoing are suppressed
    to avoid red dots from transient blips.
    """
    _PRIORITY = {"outage": 3, "degraded": 2, "operational": 1, "offline": 0}
    _OUTAGE_MIN_SECONDS = 60
    today = now.date()
    rows_sorted = sorted(rows, key=lambda r: r.started_at)

    # Precompute effective status for each row: short non-ongoing outage rows
    # are replaced with whatever non-outage status preceded them.
    effective: list[str] = []
    for i, row in enumerate(rows_sorted):
        raw = row.status.value
        if raw != "outage":
            effective.append(raw)
            continue
        if i == len(rows_sorted) - 1:
            effective.append("outage")  # ongoing — always visible
            continue
        duration_s = (rows_sorted[i + 1].started_at - row.started_at).total_seconds()
        if duration_s > _OUTAGE_MIN_SECONDS:
            effective.append("outage")
        else:
            # Short blip: fall back to the last non-outage effective status.
            prior = next(
                (effective[j] for j in range(i - 1, -1, -1) if effective[j] != "outage"),
                "operational",
            )
            effective.append(prior)

    result = []
    for i in range(days - 1, -1, -1):
        day = today - datetime.timedelta(days=i)
        day_start = datetime.datetime(day.year, day.month, day.day)
        day_end = day_start + datetime.timedelta(days=1)
        in_day = [j for j, r in enumerate(rows_sorted) if day_start <= r.started_at < day_end]
        before_day = [j for j, r in enumerate(rows_sorted) if r.started_at < day_start]
        if not in_day and not before_day:
            status = "no_data"
        elif not in_day:
            status = effective[before_day[-1]]
        else:
            candidates = in_day + (before_day[-1:] if before_day else [])
            best_j = max(candidates, key=lambda j: _PRIORITY.get(effective[j], -1))
            status = effective[best_j]
        result.append({"date": day.isoformat(), "status": status})
    return result


@router.get("/history")
def get_history(
    days: int = Query(default=90, ge=1, le=365),
    db: Session = Depends(get_db),
    session_token: str | None = Cookie(default=None, alias="session-token"),
    include_private: bool = Query(default=False),
) -> dict[str, list[dict]]:
    if include_private:
        if not session_token or not _auth.get_session(session_token):
            raise HTTPException(status_code=401, detail="Not authenticated")
        service_ids = [r[0] for r in db.query(Service.id).all()]
    else:
        service_ids = [r[0] for r in db.query(Service.id).filter(Service.is_public.is_(True)).all()]

    if not service_ids:
        return {}

    now = _now()
    window_start = now - datetime.timedelta(days=days + 1)  # +1 for carry-over
    rows = (
        db.query(ServiceStatusHistory)
        .filter(
            ServiceStatusHistory.service_id.in_(service_ids),
            ServiceStatusHistory.started_at >= window_start,
        )
        .order_by(ServiceStatusHistory.service_id, ServiceStatusHistory.started_at)
        .all()
    )

    rows_by_service: dict[str, list] = defaultdict(list)
    for row in rows:
        rows_by_service[row.service_id].append(row)

    return {svc_id: _compute_daily_history(rows_by_service[svc_id], days, now) for svc_id in service_ids}


# ── Incidents ─────────────────────────────────────────────────────────────────


class IncidentCreate(BaseModel):
    title: str
    body: str = ""
    status: IncidentStatus = IncidentStatus.investigating


class IncidentUpdate(BaseModel):
    title: str | None = None
    body: str | None = None
    status: IncidentStatus | None = None


class IncidentOut(_UTCModel):
    id: str
    title: str
    body: str
    status: IncidentStatus
    created_at: datetime.datetime
    updated_at: datetime.datetime


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
        created_at=_now(),
        updated_at=_now(),
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
    return _get_or_404(db, Incident, incident_id, "Incident not found")


@router.patch("/incidents/{incident_id}", response_model=IncidentOut)
def update_incident(
    incident_id: str,
    body: IncidentUpdate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    _user: str = Depends(require_auth),
):
    incident = _get_or_404(db, Incident, incident_id, "Incident not found")
    if body.title is not None:
        incident.title = body.title
    if body.body is not None:
        incident.body = body.body
    if body.status is not None:
        incident.status = body.status
    incident.updated_at = _now()
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
    incident = _get_or_404(db, Incident, incident_id, "Incident not found")
    db.delete(incident)
    db.commit()



# ── Notifications ──────────────────────────────────────────────────────────────────────────────────


class TelegramConfigIn(BaseModel):
    bot_token: str | None = None
    chat_id: str | None = None


class DiscordConfigIn(BaseModel):
    bot_token: str | None = None


class EmailSubscriberCreate(BaseModel):
    email: str


class EmailSubscriberOut(_UTCModel):
    id: str
    email: str
    created_at: datetime.datetime


class DiscordDestinationCreate(BaseModel):
    destination_type: str  # "channel" or "user"
    destination_id: str
    label: str | None = None


class DiscordDestinationOut(_UTCModel):
    id: str
    destination_type: str
    destination_id: str
    label: str | None
    created_at: datetime.datetime


@router.get("/notifications/settings")
def get_notification_settings(db: Session = Depends(get_db), _user: str = Depends(require_auth)):
    tg = db.get(TelegramConfig, "default")
    dc = db.get(DiscordConfig, "default")
    return {
        "telegram": {
            "bot_token_set": bool(tg and tg.bot_token),
            "chat_id": tg.chat_id if tg else None,
        },
        "discord": {
            "bot_token_set": bool(dc and dc.bot_token),
            "app_id": base64.b64decode(dc.bot_token.split('.')[0] + '==').decode() if (dc and dc.bot_token) else None,
        },
    }


@router.put("/notifications/telegram", status_code=204)
def upsert_telegram(body: TelegramConfigIn, db: Session = Depends(get_db), _user: str = Depends(require_auth)):
    tg = db.get(TelegramConfig, "default")
    if tg is None:
        tg = TelegramConfig(singleton_id="default")
        db.add(tg)
    tg.bot_token = body.bot_token
    tg.chat_id = body.chat_id
    db.commit()


@router.put("/notifications/discord", status_code=204)
def upsert_discord(body: DiscordConfigIn, db: Session = Depends(get_db), _user: str = Depends(require_auth)):
    dc = db.get(DiscordConfig, "default")
    if dc is None:
        dc = DiscordConfig(singleton_id="default")
        db.add(dc)
    dc.bot_token = body.bot_token
    db.commit()


@router.get("/notifications/email-subscribers", response_model=list[EmailSubscriberOut])
def list_email_subscribers(db: Session = Depends(get_db), _user: str = Depends(require_auth)):
    return db.query(EmailSubscriber).order_by(EmailSubscriber.created_at).all()


@router.post("/notifications/email-subscribers", response_model=EmailSubscriberOut, status_code=201)
def add_email_subscriber(body: EmailSubscriberCreate, db: Session = Depends(get_db), _user: str = Depends(require_auth)):
    existing = db.query(EmailSubscriber).filter(EmailSubscriber.email == body.email).first()
    if existing:
        raise HTTPException(status_code=409, detail="Email already subscribed")
    sub = EmailSubscriber(id=str(uuid.uuid4()), email=body.email, created_at=_now())
    db.add(sub)
    db.commit()
    db.refresh(sub)
    return sub


@router.delete("/notifications/email-subscribers/{sub_id}", status_code=204)
def delete_email_subscriber(sub_id: str, db: Session = Depends(get_db), _user: str = Depends(require_auth)):
    sub = _get_or_404(db, EmailSubscriber, sub_id, "Subscriber not found")
    db.delete(sub)
    db.commit()


@router.get("/notifications/discord/destinations", response_model=list[DiscordDestinationOut])
def list_discord_destinations(db: Session = Depends(get_db), _user: str = Depends(require_auth)):
    return db.query(DiscordDestination).order_by(DiscordDestination.created_at).all()


@router.post("/notifications/discord/destinations", response_model=DiscordDestinationOut, status_code=201)
def add_discord_destination(
    body: DiscordDestinationCreate,
    db: Session = Depends(get_db),
    _user: str = Depends(require_auth),
):
    if body.destination_type not in ("channel", "user"):
        raise HTTPException(status_code=422, detail="destination_type must be 'channel' or 'user'")
    dest = DiscordDestination(
        id=str(uuid.uuid4()),
        destination_type=body.destination_type,
        destination_id=body.destination_id,
        label=body.label,
        created_at=_now(),
    )
    db.add(dest)
    db.commit()
    db.refresh(dest)
    return dest


@router.delete("/notifications/discord/destinations/{dest_id}", status_code=204)
def delete_discord_destination(dest_id: str, db: Session = Depends(get_db), _user: str = Depends(require_auth)):
    dest = _get_or_404(db, DiscordDestination, dest_id, "Destination not found")
    db.delete(dest)
    db.commit()