import asyncio
import datetime
import logging

import httpx
from sqlalchemy import or_, and_
from sqlalchemy.orm import Session

from statuspage.database.models import CheckType, Service, ServiceStatus, ServiceStatusHistory

_log = logging.getLogger(__name__)

_COMMAND_TIMEOUT = 45.0   # seconds; relay SSH needs auth + relay setup time
_WARMUP_TIMEOUT  = 300.0  # seconds; one-time init (nix store population, etc.)
_failure_counts: dict = {}    # service_id -> consecutive outage count (in-memory, reset on restart)


async def _check_http(client: httpx.AsyncClient, name: str, url: str) -> tuple[str, str]:
    """HTTP GET — operational if status < 500, outage otherwise."""
    try:
        resp = await client.get(url)
        if resp.status_code >= 500:
            return ServiceStatus.outage, f"HTTP {resp.status_code}"
        return ServiceStatus.operational, f"HTTP {resp.status_code}"
    except (httpx.ConnectError, httpx.TimeoutException, httpx.TransportError) as exc:
        _log.warning("check %s failed: %s: %s", name, type(exc).__name__, exc)
        return ServiceStatus.outage, f"{type(exc).__name__}: {exc}"
    except Exception as exc:  # noqa: BLE001
        _log.warning("unexpected error checking %s: %s", name, exc)
        return ServiceStatus.outage, f"{type(exc).__name__}: {exc}"


async def _check_command(name: str, command: str) -> tuple[str, str]:
    """Shell command — operational if exit 0, outage otherwise."""
    try:
        proc = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            _, stderr = await asyncio.wait_for(proc.communicate(), timeout=_COMMAND_TIMEOUT)
        except asyncio.TimeoutError:
            proc.kill()
            await proc.communicate()
            _log.warning("check %s: command timed out after %.0fs", name, _COMMAND_TIMEOUT)
            return ServiceStatus.outage, f"timed out after {_COMMAND_TIMEOUT:.0f}s"

        if proc.returncode == 0:
            return ServiceStatus.operational, "exit 0"
        stderr_text = (stderr or b"").decode(errors="replace").strip()
        _log.warning("check %s: command exited %d: %s", name, proc.returncode, stderr_text)
        return ServiceStatus.outage, f"exit {proc.returncode}: {stderr_text}"
    except Exception as exc:  # noqa: BLE001
        _log.warning("check %s: command error: %s", name, exc)
        return ServiceStatus.outage, f"{type(exc).__name__}: {exc}"


async def _warmup_single(name: str, command: str) -> None:
    """Run command once with a long timeout; result is discarded."""
    try:
        proc = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        try:
            await asyncio.wait_for(proc.wait(), timeout=_WARMUP_TIMEOUT)
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            _log.warning("warmup %s: timed out after %.0fs", name, _WARMUP_TIMEOUT)
    except Exception as exc:  # noqa: BLE001
        _log.warning("warmup %s: error: %s", name, exc)


async def warmup_command_checks(db_engine) -> None:
    """Run all command-type checks once at startup to warm caches.

    Results are discarded; the sole purpose is side-effects such as populating
    the nix store so subsequent timed checks don't incur download latency.
    """
    with Session(db_engine) as session:
        rows = (
            session.query(Service.name, Service.check_command)
            .filter(
                Service.check_enabled.is_(True),
                Service.check_type == CheckType.command,
                Service.check_command.isnot(None),
            )
            .all()
        )
    if not rows:
        return

    _log.info("warming up %d command check(s)", len(rows))
    await asyncio.gather(*[_warmup_single(row.name, row.check_command) for row in rows])
    _log.info("command check warmup complete")


async def run_checks(db_engine) -> None:
    """Run one round of health checks; updates DB in-place."""
    # Phase 1: read service list, then release the connection immediately.
    with Session(db_engine) as session:
        rows = (
            session.query(
                Service.id,
                Service.name,
                Service.url,
                Service.status,
                Service.on_demand,
                Service.check_type,
                Service.check_command,
            )
            .filter(
                Service.check_enabled.is_(True),
                or_(
                    and_(Service.check_type == CheckType.http, Service.url.isnot(None)),
                    and_(Service.check_type == CheckType.command, Service.check_command.isnot(None)),
                ),
            )
            .all()
        )
    if not rows:
        return

    targets = [
        (row.id, row.name, row.url, row.status, row.on_demand, row.check_type, row.check_command)
        for row in rows
    ]

    # Phase 2: run all checks with no DB connection held.
    async with httpx.AsyncClient(
    timeout=httpx.Timeout(5.0),
        follow_redirects=True,
    ) as client:
        async def _dispatch(name: str, url: str | None, check_type: str, cmd: str | None) -> tuple[str, str]:
            if check_type == CheckType.command:
                return await _check_command(name, cmd)
            return await _check_http(client, name, url)

        results = await asyncio.gather(
            *[_dispatch(name, url, ct, cmd) for _, name, url, _, _, ct, cmd in targets],
            return_exceptions=True,
        )

    # Phase 3: write results; acquire connection only now.
    now = datetime.datetime.utcnow()
    status_changes: list[tuple[str, str, str, str | None, str]] = []
    with Session(db_engine) as session:
        for (svc_id, svc_name, svc_url, prior_status, on_demand, _ct, _cmd), result in zip(targets, results):
            svc = session.get(Service, svc_id)
            if svc is None:
                continue
            if isinstance(result, Exception):
                _log.error("check task for %s raised: %s", svc_name, result)
                new_status = ServiceStatus.outage
                detail = f"check task raised: {result}"
            else:
                new_status, detail = result
            # Consecutive-failure guard: suppress outage/offline transitions until
            # consecutive failures == svc.failure_threshold before status transitions.  Single-cycle
            # network blips therefore produce no alert.  Recoveries are immediate.
            if new_status == ServiceStatus.outage:
                _failure_counts[svc_id] = _failure_counts.get(svc_id, 0) + 1
                if _failure_counts[svc_id] < svc.failure_threshold:
                    _log.debug(
                        "check %s: failure %d/%d — holding at %s",
                        svc_name, _failure_counts[svc_id], svc.failure_threshold, prior_status.value,
                    )
                    new_status = prior_status
            else:
                _failure_counts.pop(svc_id, None)
            # on_demand services never show outage — downtime is expected.
            # Non-on_demand services also keep offline if already set manually.
            if new_status == ServiceStatus.outage and (on_demand or prior_status == ServiceStatus.offline):
                new_status = ServiceStatus.offline
            if new_status != prior_status:
                _log.info("status change: %s %s -> %s", svc_name, prior_status.value, new_status.value)
                status_changes.append((svc_name, prior_status.value, new_status.value, svc_url, detail))
                session.add(ServiceStatusHistory(
                    service_id=svc_id,
                    status=new_status,
                    started_at=now,
                ))
            svc.status = new_status
            svc.last_checked_at = now
        session.commit()
    _log.info("checked %d services", len(targets))

    # Fire notifications after the commit so DB is consistent if they fail.
    if status_changes:
        from statuspage import notifier as _notifier
        asyncio.create_task(_notifier.notify_status_changes(status_changes))


async def health_check_loop(db_engine, interval_seconds: int) -> None:
    """Continuous background loop. Run forever; errors are logged, not raised."""
    _log.info("health-check loop starting, interval=%ds", interval_seconds)
    while True:
        try:
            await run_checks(db_engine)
        except Exception as exc:  # noqa: BLE001
            _log.error("health-check round failed: %s", exc)
        await asyncio.sleep(interval_seconds)
