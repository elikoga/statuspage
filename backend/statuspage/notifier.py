import asyncio
import logging
import smtplib
from email.mime.text import MIMEText

import httpx

_log = logging.getLogger(__name__)


# ── low-level transports ───────────────────────────────────────────────────────


async def _telegram(token: str, chat_id: str, text: str) -> None:
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"},
        )
    data = resp.json()
    if not data.get("ok"):
        _log.error("Telegram notification failed: %s", data.get("description", resp.text))


def _email_sync(
    host: str,
    port: int,
    user: str | None,
    password: str | None,
    from_addr: str,
    to_addr: str,
    subject: str,
    body: str,
    use_starttls: bool,
) -> None:
    msg = MIMEText(body, "plain")
    msg["Subject"] = subject
    msg["From"] = from_addr
    msg["To"] = to_addr
    if port == 465:
        smtp: smtplib.SMTP = smtplib.SMTP_SSL(host, port)
    else:
        smtp = smtplib.SMTP(host, port)
        if use_starttls:
            smtp.starttls()
    try:
        if user and password:
            smtp.login(user, password)
        smtp.sendmail(from_addr, [to_addr], msg.as_string())
    finally:
        smtp.quit()


async def _email(
    host: str,
    port: int,
    user: str | None,
    password: str | None,
    from_addr: str,
    to_addr: str,
    subject: str,
    body: str,
    use_starttls: bool,
) -> None:
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(
        None,
        _email_sync,
        host,
        port,
        user,
        password,
        from_addr,
        to_addr,
        subject,
        body,
        use_starttls,
    )


# ── public API ─────────────────────────────────────────────────────────────────


async def notify(subject: str, body: str = "") -> None:
    """Send subject+body to every configured channel. Errors are logged, never raised."""
    from statuspage.config import global_settings as cfg

    coros = []

    if cfg.TELEGRAM_BOT_TOKEN and cfg.TELEGRAM_CHAT_ID:
        text = f"<b>{subject}</b>\n\n{body}".strip() if body else f"<b>{subject}</b>"
        coros.append(_telegram(cfg.TELEGRAM_BOT_TOKEN, cfg.TELEGRAM_CHAT_ID, text))

    if cfg.SMTP_HOST and cfg.SMTP_TO:
        from_addr = cfg.SMTP_FROM or cfg.SMTP_USER or "statuspage@localhost"
        coros.append(
            _email(
                cfg.SMTP_HOST,
                cfg.SMTP_PORT,
                cfg.SMTP_USER,
                cfg.SMTP_PASSWORD,
                from_addr,
                cfg.SMTP_TO,
                subject,
                body,
                cfg.SMTP_USE_STARTTLS,
            )
        )

    if not coros:
        _log.debug("no notification channels configured; skipping")
        return

    results = await asyncio.gather(*coros, return_exceptions=True)
    for r in results:
        if isinstance(r, Exception):
            _log.error("notification dispatch error: %s", r)


async def notify_status_change(service_name: str, old_status: str, new_status: str) -> None:
    """Called by the health checker when a service's status changes."""
    if old_status == new_status:
        return
    if new_status == "operational":
        subject = f"[StatusPage] {service_name} recovered ({old_status} -> operational)"
    else:
        subject = f"[StatusPage] {service_name}: {old_status} -> {new_status}"
    await notify(subject)


async def notify_incident(action: str, title: str, status: str, body: str) -> None:
    """Called when an incident is created or updated."""
    subject = f"[StatusPage] Incident {action}: {title} [{status}]"
    await notify(subject, body)
