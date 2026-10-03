import asyncio
import datetime
import logging
import socket

import httpx
from sqlalchemy import or_, and_
from sqlalchemy.orm import Session

from statuspage.database.models import CheckType, Service, ServiceStatus, ServiceStatusHistory

_log = logging.getLogger(__name__)

_COMMAND_TIMEOUT = 45.0   # seconds; relay SSH needs auth + relay setup time
_WARMUP_TIMEOUT  = 300.0  # seconds; one-time init (nix store population, etc.)
_failure_counts: dict = {}    # service_id -> consecutive outage count (in-memory, reset on restart)

# Connect timeout must exceed glibc's resolver timeout (5s by default). Name
# resolution happens inside the connect timeout, and a lookup whose first UDP
# query is lost only returns once glibc's retry completes (~5.0s). With a 5s
# budget every check in the round failed with ConnectTimeout at exactly t+5s.
_CONNECT_TIMEOUT = 10.0
_READ_TIMEOUT = 10.0
_POOL_TIMEOUT = 5.0
_RETRY_DELAY = 1.0        # seconds between the two attempts of an HTTP check

# Canary for the monitoring host's own network path. Kept independent of the
# monitored services so that a DNS/egress stall here cannot be reported as an
# outage of every monitored service at once.
_CANARY_DNS_HOST = "example.com"
_CANARY_TCP_ADDR = ("1.1.1.1", 443)
_CANARY_TIMEOUT = 5.0


async def _check_http(client: httpx.AsyncClient, name: str, url: str) -> tuple[str, str]:
    """HTTP GET — operational if status < 500, outage otherwise.

    Transport failures are retried once. Name resolution runs on the event
    loop's default thread pool (6 workers on a 2-vCPU host), so a few stalled
    lookups hold the pool and can push unrelated in-flight checks past the
    connect deadline. Retrying turns a transient stall into a success.
    """
    last_detail = "no attempt made"
    for attempt in range(2):
        try:
            resp = await client.get(url)
        except httpx.TransportError as exc:
            last_detail = f"{type(exc).__name__}: {exc}"
            _log.warning(
                "check %s failed (%d/2): %s: %s", name, attempt + 1, type(exc).__name__, exc
            )
            if attempt == 0:
                await asyncio.sleep(_RETRY_DELAY)
            continue
        except Exception as exc:  # noqa: BLE001
            _log.warning("unexpected error checking %s: %s", name, exc)
            return ServiceStatus.outage, f"{type(exc).__name__}: {exc}"
        if resp.status_code >= 500:
            return ServiceStatus.outage, f"HTTP {resp.status_code}"
        # Caddy answers an empty-bodied 200 when no reverse-proxy route matches
        # the host (e.g. runtime routes wiped by a config reload/restart). That
        # is a silent outage: a healthy monitored service returns a body. Flag
        # it so the status page catches it instead of reporting operational.
        if resp.status_code == 200 and not resp.content:
            return ServiceStatus.outage, "HTTP 200 (empty body - no route?)"
        return ServiceStatus.operational, f"HTTP {resp.status_code}"
    return ServiceStatus.outage, last_detail


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
        # Tracebacks can be hundreds of lines; keep the tail where the exception lives.
        if len(stderr_text) > 500:
            stderr_text = "..." + stderr_text[-497:]
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


async def _self_test() -> str | None:
    """Check that this host can still resolve names and open outbound TCP.

    Returns None when the monitor's own network path is healthy, otherwise a
    description of the failure. Without this, a DNS or egress stall on the
    monitoring host makes every in-flight check fail at once, and the round is
    recorded as an outage of every service on the page.
    """
    loop = asyncio.get_running_loop()
    try:
        await asyncio.wait_for(
            loop.getaddrinfo(_CANARY_DNS_HOST, 443, type=socket.SOCK_STREAM),
            timeout=_CANARY_TIMEOUT,
        )
    except Exception as exc:  # noqa: BLE001
        return f"dns lookup {_CANARY_DNS_HOST} failed: {type(exc).__name__}: {exc}"
    try:
        _, writer = await asyncio.wait_for(
            asyncio.open_connection(*_CANARY_TCP_ADDR), timeout=_CANARY_TIMEOUT
        )
        writer.close()
        await writer.wait_closed()
    except Exception as exc:  # noqa: BLE001
        return f"tcp connect {_CANARY_TCP_ADDR[0]}:{_CANARY_TCP_ADDR[1]} failed: {type(exc).__name__}: {exc}"
    return None


async def run_checks(db_engine) -> None:
    """Run one round of health checks; updates DB in-place."""
    self_test_failure = await _self_test()
    if self_test_failure is not None:
        _log.warning(
            "skipping check round: monitor host network unhealthy (%s)", self_test_failure
        )
        return

    # Phase 1: read service list, then release the connection immediately.
    with Session(db_engine) as session:
        rows = (
            session.query(
                Service.id,
                Service.name,
                Service.url,
                Service.status,
                Service.muted,
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
        (row.id, row.name, row.url, row.status, row.muted, row.check_type, row.check_command)
        for row in rows
    ]

    # Phase 2: run all checks with no DB connection held.
    async with httpx.AsyncClient(
        timeout=httpx.Timeout(_CONNECT_TIMEOUT, read=_READ_TIMEOUT, pool=_POOL_TIMEOUT),
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
        for (svc_id, svc_name, svc_url, prior_status, muted, _ct, _cmd), result in zip(targets, results):
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
            # muted services never show outage — downtime is expected.
            # Non-muted services also keep offline if already set manually.
            # muted status changes update the DB for the timeline display
            # but never trigger notifications.
            if new_status == ServiceStatus.outage and (muted or prior_status == ServiceStatus.offline):
                new_status = ServiceStatus.offline
            if new_status != prior_status:
                _log.info("status change: %s %s -> %s", svc_name, prior_status.value, new_status.value)
                session.add(ServiceStatusHistory(
                    service_id=svc_id,
                    status=new_status,
                    started_at=now,
                ))
                if not muted:
                    status_changes.append((svc_name, prior_status.value, new_status.value, svc_url, detail))
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
