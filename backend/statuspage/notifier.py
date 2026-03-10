import asyncio
import datetime
import logging
import smtplib
from email.mime.text import MIMEText
from urllib.parse import urlparse

import httpx
from sqlalchemy.orm import Session

from statuspage.config import global_settings as _cfg

_log = logging.getLogger(__name__)

# Set by main.py at startup — same pattern as db_engine
_db_engine = None


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
        None, _email_sync, host, port, user, password, from_addr, to_addr, subject, body, use_starttls,
    )


async def _discord_send(token: str, channel_id: str, text: str) -> None:
    """Send a message to a Discord channel (works for guild channels and DM channels)."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(
            f"https://discord.com/api/v10/channels/{channel_id}/messages",
            headers={"Authorization": f"Bot {token}"},
            json={"content": text},
        )
    if not resp.is_success:
        _log.error("Discord channel send failed (%s): %s", channel_id, resp.text)


async def _discord_dm(token: str, user_id: str, text: str) -> None:
    """Open a DM channel with a user and send a message."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        dm_resp = await client.post(
            "https://discord.com/api/v10/users/@me/channels",
            headers={"Authorization": f"Bot {token}"},
            json={"recipient_id": user_id},
        )
        if not dm_resp.is_success:
            _log.error("Discord DM open failed for user %s: %s", user_id, dm_resp.text)
            return
        channel_id = dm_resp.json()["id"]
        resp = await client.post(
            f"https://discord.com/api/v10/channels/{channel_id}/messages",
            headers={"Authorization": f"Bot {token}"},
            json={"content": text},
        )
    if not resp.is_success:
        _log.error("Discord DM send failed (user %s): %s", user_id, resp.text)


# ── public API ─────────────────────────────────────────────────────────────────


async def notify(subject: str, body: str = "") -> None:
    """Send subject+body to every configured channel. Errors are logged, never raised."""
    if _db_engine is None:
        _log.warning("notify called before db_engine initialised; skipping")
        return

    from statuspage.database.models import (
        DiscordConfig, DiscordDestination, EmailSubscriber, TelegramConfig,
    )

    with Session(_db_engine) as db:
        tg = db.get(TelegramConfig, "default")
        dc = db.get(DiscordConfig, "default")
        discord_dests = db.query(DiscordDestination).all()
        email_subs = db.query(EmailSubscriber).all()
        # snapshot to avoid session issues after close
        tg_token = tg.bot_token if tg else None
        tg_chat = tg.chat_id if tg else None
        dc_token = dc.bot_token if dc else None
        dests = [(d.destination_type, d.destination_id) for d in discord_dests]
        emails = [s.email for s in email_subs]

    coros = []

    if tg_token and tg_chat:
        text = f"<b>{subject}</b>\n\n{body}".strip() if body else f"<b>{subject}</b>"
        coros.append(_telegram(tg_token, tg_chat, text))

    if dc_token and dests:
        text = f"**{subject}**\n{body}".strip() if body else f"**{subject}**"
        for dest_type, dest_id in dests:
            if dest_type == "channel":
                coros.append(_discord_send(dc_token, dest_id, text))
            else:
                coros.append(_discord_dm(dc_token, dest_id, text))

    if _cfg.SMTP_HOST and emails:
        from_addr = _cfg.SMTP_FROM or _cfg.SMTP_USER or "statuspage@localhost"
        for addr in emails:
            coros.append(
                _email(
                    _cfg.SMTP_HOST, _cfg.SMTP_PORT, _cfg.SMTP_USER,
                    _cfg.SMTP_PASSWORD, from_addr, addr, subject, body, _cfg.SMTP_USE_STARTTLS,
                )
            )

    if not coros:
        _log.debug("no notification channels configured; skipping")
        return

    results = await asyncio.gather(*coros, return_exceptions=True)
    for r in results:
        if isinstance(r, Exception):
            _log.error("notification dispatch error: %s", r)


async def notify_status_changes(
    changes: list[tuple[str, str, str, str | None, str]],
) -> None:
    """Called by the health checker with all status changes from one check cycle."""
    if not changes:
        return
    instance = urlparse(_cfg.BASE_URL).netloc or _cfg.BASE_URL
    now = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    count = len(changes)
    subject = f"[StatusPage @ {instance}] {count} service{'s' if count != 1 else ''} changed status"
    lines = []
    for svc_name, old_st, new_st, url, detail in changes:
        icon = "\u2705" if new_st == "operational" else "\U0001f534"
        line = f"{icon} {svc_name}: {old_st} -> {new_st}"
        if url:
            line += f"\n   URL: {url}"
        if detail:
            line += f"\n   Detail: {detail}"
        lines.append(line)
    body = f"Instance: {_cfg.BASE_URL}\nTime: {now}\n\n" + "\n\n".join(lines)
    await notify(subject, body)

async def notify_incident(action: str, title: str, status: str, body: str) -> None:
    """Called when an incident is created or updated."""
    instance = urlparse(_cfg.BASE_URL).netloc or _cfg.BASE_URL
    subject = f"[StatusPage @ {instance}] Incident {action}: {title} [{status}]"
    await notify(subject, body)
