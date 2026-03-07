import asyncio
import datetime
import logging

import httpx

_log = logging.getLogger(__name__)


async def _check_one(client: httpx.AsyncClient, name: str, url: str) -> str:
    """Returns the new ServiceStatus string for one service."""
    from statuspage.database.models import ServiceStatus

    try:
        resp = await client.get(url)
        if resp.status_code >= 500:
            return ServiceStatus.outage
        return ServiceStatus.operational
    except (httpx.ConnectError, httpx.TimeoutException, httpx.TransportError) as exc:
        _log.debug("check %s -> %s: %s", name, type(exc).__name__, exc)
        return ServiceStatus.outage
    except Exception as exc:  # noqa: BLE001
        _log.warning("unexpected error checking %s: %s", name, exc)
        return ServiceStatus.outage


async def run_checks(db_engine) -> None:
    """Run one round of health checks; updates DB in-place."""
    from sqlalchemy.orm import Session
    from statuspage.database.models import Service, ServiceStatus

    # Phase 1: read service list, then release the connection immediately.
    with Session(db_engine) as session:
        rows = (
            session.query(Service.id, Service.name, Service.url, Service.status, Service.on_demand)
            .filter(
                Service.url.isnot(None),
                Service.check_enabled.is_(True),
            )
            .all()
        )
    if not rows:
        return

    # Phase 2: run all HTTP checks with no DB connection held.
    targets = [(row.id, row.name, row.url, row.status, row.on_demand) for row in rows]
    async with httpx.AsyncClient(
        timeout=httpx.Timeout(10.0),
        follow_redirects=True,
    ) as client:
        results = await asyncio.gather(
            *[_check_one(client, name, url) for _, name, url, _, _ in targets],
            return_exceptions=True,
        )

    # Phase 3: write results; acquire connection only now.
    now = datetime.datetime.utcnow()
    with Session(db_engine) as session:
        for (svc_id, svc_name, _, prior_status, on_demand), result in zip(targets, results):
            svc = session.get(Service, svc_id)
            if svc is None:
                continue
            if isinstance(result, Exception):
                _log.error("check task for %s raised: %s", svc_name, result)
                new_status = ServiceStatus.outage
            else:
                new_status = result
            # on_demand services never show outage — downtime is expected.
            # Non-on_demand services also keep offline if already set manually.
            if new_status == ServiceStatus.outage and (on_demand or prior_status == ServiceStatus.offline):
                new_status = ServiceStatus.offline
            svc.status = new_status
            svc.last_checked_at = now
        session.commit()
    _log.info("checked %d services", len(targets))


async def health_check_loop(db_engine, interval_seconds: int) -> None:
    """Continuous background loop. Run forever; errors are logged, not raised."""
    _log.info("health-check loop starting, interval=%ds", interval_seconds)
    while True:
        try:
            await run_checks(db_engine)
        except Exception as exc:  # noqa: BLE001
            _log.error("health-check round failed: %s", exc)
        await asyncio.sleep(interval_seconds)
