"""TTS phone-call notifications over SIP.

The call path is deliberately dependency-free at the SIP layer: a minimal
UDP SIP user agent (INVITE + digest auth) and an RTP stream carrying G.711
audio. TTS audio is produced by ``espeak-ng``, resampled to 8 kHz and encoded
to G.711 in-process, so the only external runtime input is the espeak-ng
binary.

We never REGISTER: the statuspage only places outbound calls, and registering
the same AOR as the home phone would fork/steal inbound calls.
"""

from __future__ import annotations

import array
import asyncio
import dataclasses
import datetime
import hashlib
import logging
import os
import random
import re
import socket
import struct
import subprocess
import sys
import tempfile
import time
import wave
from urllib.parse import urlparse

import dns.resolver
from sqlalchemy.orm import Session

from statuspage.config import global_settings as _cfg

_log = logging.getLogger(__name__)

# Set by main.py at startup — same pattern as notifier.db_engine.
_db_engine = None

_call_lock = asyncio.Lock()

_SIP_PORT = 5060
_SIP_TIMEOUT = 12.0
_RTP_PTIME = 0.020
_RTP_PAYLOAD_BYTES = 160      # 20 ms of 8 kHz G.711
_MAX_AUDIO_SECONDS = 60


@dataclasses.dataclass
class VoiceSettings:
    destination: str
    sip_number: str
    sip_auth_username: str
    sip_password: str
    sip_registrar: str
    sip_proxy: str | None
    dns_server: str | None
    tts_language: str
    message_template: str | None
    delay_seconds: int


# ── settings ──────────────────────────────────────────────────────────────────


def load_settings() -> VoiceSettings | None:
    """Return the configured voice settings, or None when calls are disabled."""
    if _db_engine is None:
        return None
    from statuspage.database.models import VoiceCallConfig

    with Session(_db_engine) as db:
        row = db.get(VoiceCallConfig, "default")
        if row is None or not row.enabled:
            return None
        if not (row.destination and row.sip_number and row.sip_password and row.sip_registrar):
            _log.warning("voice call enabled but missing destination/SIP credentials; skipping")
            return None
        return VoiceSettings(
            destination=row.destination,
            sip_number=row.sip_number,
            sip_auth_username=row.sip_auth_username or row.sip_number,
            sip_password=row.sip_password,
            sip_registrar=row.sip_registrar,
            sip_proxy=row.sip_proxy or None,
            dns_server=row.dns_server or None,
            tts_language=row.tts_language or "de",
            message_template=row.message_template or None,
            delay_seconds=int(row.delay_seconds or 300),
        )


def build_message(service_names: list[str], minutes: int, settings: VoiceSettings) -> str:
    instance = urlparse(_cfg.BASE_URL).netloc or _cfg.BASE_URL
    services = ", ".join(service_names)
    lang = (settings.tts_language or "de").split("-")[0].lower()
    if settings.message_template:
        template = settings.message_template
    elif lang == "de":
        template = (
            "Achtung. Statusseite {instance}. {services} "
            "seit {minutes} Minuten nicht erreichbar."
        )
    else:
        template = (
            "Attention. Status page {instance}. {services} "
            "has been down for {minutes} minutes."
        )
    try:
        return template.format(services=services, instance=instance, minutes=minutes)
    except (KeyError, IndexError, ValueError):
        return template


# ── public API ────────────────────────────────────────────────────────────────


def busy() -> bool:
    return _call_lock.locked()


async def place_outage_call(service_names: list[str], minutes: int) -> bool:
    """Place one call covering every service that just crossed the delay."""
    settings = load_settings()
    if settings is None:
        return False
    text = build_message(service_names, minutes, settings)
    return await _place(settings, text)


async def place_test_call() -> bool:
    settings = load_settings()
    if settings is None:
        raise RuntimeError("voice calls are not enabled or not fully configured")
    text = build_message(["Testdienst"], 1, settings)
    ok = await _place(settings, text)
    if not ok:
        raise RuntimeError("test call failed; see statuspage logs for details")
    return ok


async def _place(settings: VoiceSettings, text: str) -> bool:
    if _call_lock.locked():
        _log.warning("voice call already in progress; skipping")
        return False
    async with _call_lock:
        try:
            pcm = await asyncio.to_thread(_synthesize, text, settings.tts_language)
        except Exception as exc:  # noqa: BLE001
            _log.error("voice call TTS failed: %s", exc)
            return False
        pcm = pcm[: 8000 * 2 * _MAX_AUDIO_SECONDS]
        for attempt in (1, 2):
            try:
                await asyncio.to_thread(_call_blocking, settings, pcm)
                _log.info("voice call to %s completed", settings.destination)
                return True
            except Exception as exc:  # noqa: BLE001
                _log.error("voice call attempt %d failed: %s", attempt, exc)
                if attempt == 1:
                    await asyncio.sleep(5)
        return False


# ── TTS / audio ───────────────────────────────────────────────────────────────


def _synthesize(text: str, language: str) -> bytes:
    """Return 8 kHz mono 16-bit PCM for ``text``."""
    with tempfile.NamedTemporaryFile(suffix=".wav") as tmp:
        lang = (language or "de").split("-")[0].split("_")[0]
        try:
            proc = subprocess.run(
                ["espeak-ng", "-v", lang, "-s", "150", "-w", tmp.name, text],
                capture_output=True,
                timeout=60,
            )
        except FileNotFoundError as exc:
            raise RuntimeError("espeak-ng is not installed or not on PATH") from exc
        if proc.returncode != 0:
            raise RuntimeError(
                "espeak-ng failed: " + proc.stderr.decode("utf-8", "replace").strip()
            )
        with wave.open(tmp.name, "rb") as wav:
            sr = wav.getframerate()
            channels = wav.getnchannels()
            width = wav.getsampwidth()
            frames = wav.readframes(wav.getnframes())

    if width != 2:
        raise RuntimeError(f"unsupported TTS sample width: {width}")
    samples = array.array("h")
    samples.frombytes(frames)
    if sys.byteorder == "big":
        samples.byteswap()
    if channels > 1:
        mono = array.array("h", samples[::channels])
        samples = mono
    return _resample(samples, sr, 8000).tobytes()


def _resample(samples: array.array, sr_in: int, sr_out: int) -> array.array:
    if sr_in == sr_out or not samples:
        return samples
    n_out = max(1, int(len(samples) * sr_out / sr_in))
    step = sr_in / sr_out
    out = array.array("h")
    for i in range(n_out):
        pos = i * step
        j = int(pos)
        frac = pos - j
        a = samples[j]
        b = samples[j + 1] if j + 1 < len(samples) else a
        out.append(int(a + (b - a) * frac))
    return out


def _linear_to_ulaw(sample: int) -> int:
    clip = 32635
    bias = 0x84
    sign = 0x80 if sample < 0 else 0
    if sample < 0:
        sample = -sample
    if sample > clip:
        sample = clip
    sample += bias
    exponent = 7
    mask = 0x4000
    while exponent > 0 and not (sample & mask):
        exponent -= 1
        mask >>= 1
    mantissa = (sample >> (exponent + 3)) & 0x0F
    return ~(sign | (exponent << 4) | mantissa) & 0xFF


def _linear_to_alaw(sample: int) -> int:
    if sample >= 0:
        mask = 0xD5
    else:
        mask = 0x55
        sample = -sample - 1
    if sample > 32767:
        sample = 32767
    if sample >= 256:
        exponent = sample.bit_length() - 8
        mantissa = (sample >> (exponent + 3)) & 0x0F
        return ((exponent << 4) | mantissa) ^ mask
    return (sample >> 4) ^ mask


def _encode_g711(pcm: bytes, codec: str) -> bytes:
    samples = array.array("h")
    samples.frombytes(pcm)
    if sys.byteorder == "big":
        samples.byteswap()
    encode = _linear_to_ulaw if codec == "PCMU" else _linear_to_alaw
    return bytes(encode(s) for s in samples)


# ── DNS / network helpers ─────────────────────────────────────────────────────


def _resolver(dns_server: str | None) -> dns.resolver.Resolver:
    if dns_server:
        res = dns.resolver.Resolver(configure=False)
        res.nameservers = [dns_server]
    else:
        res = dns.resolver.Resolver()
    res.lifetime = 5.0
    res.timeout = 3.0
    return res


def _a_record(res: dns.resolver.Resolver, host: str) -> str:
    try:
        socket.inet_aton(host)
        return host
    except OSError:
        pass
    for rtype in ("A", "AAAA"):
        try:
            answer = res.resolve(host, rtype)
        except (dns.resolver.NoAnswer, dns.resolver.NXDOMAIN):
            continue
        for rr in answer:
            if rtype == "A":
                return rr.address
            # We only open AF_INET sockets; an IPv6-only SBC is not usable here.
    raise RuntimeError(f"no A record for {host}")


def _srv_targets(res: dns.resolver.Resolver, host: str) -> list[str]:
    try:
        answer = res.resolve(f"_sip._udp.{host}", "SRV")
    except (dns.resolver.NoAnswer, dns.resolver.NXDOMAIN, dns.resolver.NoNameservers):
        return []
    records = sorted(answer, key=lambda r: (r.priority, -r.weight))
    return [str(r.target).rstrip(".") for r in records if str(r.target).rstrip(".")]


def _resolve_sip_target(settings: VoiceSettings) -> tuple[str, int]:
    res = _resolver(settings.dns_server)
    names = [n for n in (settings.sip_proxy, settings.sip_registrar) if n]
    errors: list[str] = []
    for name in names:
        for target in _srv_targets(res, name):
            try:
                return _a_record(res, target), _SIP_PORT
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{target}: {exc}")
        try:
            return _a_record(res, name), _SIP_PORT
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{name}: {exc}")
    raise RuntimeError("could not resolve SIP proxy/registrar: " + "; ".join(errors))


def _local_ip(target_ip: str) -> str:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect((target_ip, _SIP_PORT))
        return sock.getsockname()[0]
    finally:
        sock.close()


# ── SIP protocol ──────────────────────────────────────────────────────────────


def _parse_response(data: bytes) -> tuple[int, dict[str, list[str]], bytes]:
    text = data.decode("utf-8", "replace")
    head, _, body = text.partition("\r\n\r\n")
    lines = head.split("\r\n")
    match = re.match(r"SIP/2\.0\s+(\d{3})", lines[0])
    if not match:
        raise ValueError(f"not a SIP response: {lines[0]!r}")
    headers: dict[str, list[str]] = {}
    last_key = None
    for line in lines[1:]:
        if not line:
            continue
        if line[0] in " \t" and last_key:
            headers[last_key][-1] += " " + line.strip()
            continue
        if ":" in line:
            key, value = line.split(":", 1)
            key = key.strip().lower()
            headers.setdefault(key, []).append(value.strip())
            last_key = key
    return int(match.group(1)), headers, body.encode("utf-8")


def _parse_auth_params(header: str) -> dict[str, str]:
    params: dict[str, str] = {}
    for key, quoted, bare in re.findall(r'(\w+)\s*=\s*(?:"([^"]*)"|([^\s,]+))', header):
        params[key.lower()] = quoted if quoted else bare.rstrip(",")
    return params


def _digest_authorization(
    challenge: str, method: str, uri: str, username: str, password: str
) -> str:
    params = _parse_auth_params(challenge)
    realm = params.get("realm", "")
    nonce = params.get("nonce", "")
    algorithm = params.get("algorithm", "MD5")
    if algorithm.upper() not in ("MD5", "MD5-SESS"):
        raise RuntimeError(f"unsupported SIP digest algorithm: {algorithm}")
    qop_options = [q.strip() for q in params.get("qop", "").split(",") if q.strip()]
    cnonce = os.urandom(8).hex()
    nc = "00000001"

    ha1 = hashlib.md5(f"{username}:{realm}:{password}".encode()).hexdigest()
    if algorithm.upper() == "MD5-SESS":
        ha1 = hashlib.md5(f"{ha1}:{nonce}:{cnonce}".encode()).hexdigest()
    ha2 = hashlib.md5(f"{method}:{uri}".encode()).hexdigest()

    parts = [
        f'username="{username}"',
        f'realm="{realm}"',
        f'nonce="{nonce}"',
        f'uri="{uri}"',
        f"algorithm={algorithm}",
    ]
    if "auth" in qop_options:
        response = hashlib.md5(
            f"{ha1}:{nonce}:{nc}:{cnonce}:auth:{ha2}".encode()
        ).hexdigest()
        parts += [f'response="{response}"', "qop=auth", f"nc={nc}", f'cnonce="{cnonce}"']
    else:
        response = hashlib.md5(f"{ha1}:{nonce}:{ha2}".encode()).hexdigest()
        parts.append(f'response="{response}"')
    if params.get("opaque"):
        parts.append(f'opaque="{params["opaque"]}"')
    return "Digest " + ", ".join(parts)


def _recv_sip(sock: socket.socket, deadline: float) -> tuple[int, dict[str, list[str]], bytes]:
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("timed out waiting for SIP response")
        sock.settimeout(min(remaining, 1.0))
        try:
            data, _addr = sock.recvfrom(65535)
        except socket.timeout:
            continue
        if not data.startswith(b"SIP/2.0"):
            continue
        return _parse_response(data)


def _transaction(
    sock: socket.socket,
    dest: tuple[str, int],
    message: str,
    method: str,
    timeout: float = _SIP_TIMEOUT,
) -> tuple[int, dict[str, list[str]], bytes]:
    deadline = time.monotonic() + timeout
    last_send = 0.0
    while time.monotonic() < deadline:
        now = time.monotonic()
        if now - last_send >= 1.0:
            sock.sendto(message.encode(), dest)
            last_send = now
        try:
            code, headers, body = _recv_sip(sock, min(deadline, last_send + 1.0))
        except TimeoutError:
            continue
        cseq = " ".join(headers.get("cseq", [""]))
        if method not in cseq:
            continue
        # Any response proves the request arrived; stop retransmitting while
        # waiting for the final answer (a ringing INVITE can take a while).
        last_send = time.monotonic() + timeout
        if 100 <= code < 200:
            continue  # provisional; keep waiting for the final response
        return code, headers, body
    raise TimeoutError(f"no final response to {method}")


def _contact_uri(headers: dict[str, list[str]]) -> str | None:
    for value in headers.get("contact", []):
        match = re.search(r"<([^>]+)>", value)
        if match:
            return match.group(1)
        if value.startswith("sip:"):
            return value.split(";")[0]
    return None


def _build_sdp(local_ip: str, rtp_port: int) -> str:
    session_id = random.randint(1, 2**31 - 1)
    return "\r\n".join(
        [
            "v=0",
            f"o=- {session_id} {session_id} IN IP4 {local_ip}",
            "s=statuspage",
            f"c=IN IP4 {local_ip}",
            "t=0 0",
            f"m=audio {rtp_port} RTP/AVP 0 8 101",
            "a=rtpmap:0 PCMU/8000",
            "a=rtpmap:8 PCMA/8000",
            "a=rtpmap:101 telephone-event/8000",
            "a=fmtp:101 0-16",
            "a=ptime:20",
            "a=sendrecv",
            "",
        ]
    )


def _parse_sdp(body: bytes) -> tuple[str, int, list[int]]:
    text = body.decode("utf-8", "replace").replace("\r\n", "\n")
    session_ip = None
    media_ip = None
    media_port = None
    payloads: list[int] = []
    for line in text.split("\n"):
        line = line.strip()
        if line.startswith("c=IN IP4 "):
            ip = line.split(" ", 2)[2].strip()
            if media_port is None:
                session_ip = session_ip or ip
            else:
                media_ip = ip
        elif line.startswith("m=audio ") and media_port is None:
            fields = line.split()
            media_port = int(fields[1])
            payloads = [int(p) for p in fields[3:]]
    if media_port is None:
        raise RuntimeError("SDP answer has no audio stream")
    ip = media_ip or session_ip
    if not ip or ip in ("0.0.0.0", "::"):
        raise RuntimeError("SDP answer has no usable connection address")
    return ip, media_port, payloads


def _send_request(
    sock: socket.socket,
    dest: tuple[str, int],
    method: str,
    request_uri: str,
    *,
    local_ip: str,
    local_port: int,
    call_id: str,
    from_uri: str,
    to_uri: str,
    from_tag: str,
    to_tag: str | None,
    cseq: int,
    extra_headers: dict[str, str] | None = None,
    body: str = "",
    auth_challenge: tuple[str, str] | None = None,
    auth_user: str = "",
    auth_password: str = "",
) -> tuple[int, dict[str, list[str]], bytes, int]:
    branch = f"z9hG4bK{os.urandom(6).hex()}"
    headers = [
        f"{method} {request_uri} SIP/2.0",
        f"Via: SIP/2.0/UDP {local_ip}:{local_port};branch={branch};rport",
        "Max-Forwards: 70",
        f"From: <{from_uri}>;tag={from_tag}",
        f"To: <{to_uri}>" + (f";tag={to_tag}" if to_tag else ""),
        f"Call-ID: {call_id}",
        f"CSeq: {cseq} {method}",
        f"Contact: <sip:{from_uri[len('sip:'):].split('@')[0]}@{local_ip}:{local_port}>",
        "User-Agent: statuspage-voice",
    ]
    for key, value in (extra_headers or {}).items():
        headers.append(f"{key}: {value}")
    if auth_challenge:
        header_name, challenge = auth_challenge
        headers.append(
            f"{header_name}: "
            + _digest_authorization(
                challenge, method, request_uri, auth_user, auth_password
            )
        )
    headers.append(f"Content-Length: {len(body.encode())}")
    message = "\r\n".join(headers) + "\r\n\r\n" + body

    code, resp_headers, resp_body = _transaction(sock, dest, message, method)
    if code in (401, 407):
        name = "Proxy-Authorization" if code == 407 else "Authorization"
        source = "proxy-authenticate" if code == 407 else "www-authenticate"
        challenge = ""
        for value in resp_headers.get(source, []):
            if value.lower().startswith("digest "):
                challenge = value
                break
        if not challenge:
            return code, resp_headers, resp_body, cseq
        return _send_request(
            sock,
            dest,
            method,
            request_uri,
            local_ip=local_ip,
            local_port=local_port,
            call_id=call_id,
            from_uri=from_uri,
            to_uri=to_uri,
            from_tag=from_tag,
            to_tag=to_tag,
            cseq=cseq + 1,
            extra_headers=extra_headers,
            body=body,
            auth_challenge=(name, challenge),
            auth_user=auth_user,
            auth_password=auth_password,
        )
    return code, resp_headers, resp_body, cseq


def _send_rtp(
    sock: socket.socket,
    dest: tuple[str, int],
    payload: bytes,
    codec: str,
    ptime: float = _RTP_PTIME,
) -> None:
    payload_type = 0 if codec == "PCMU" else 8
    seq = random.randint(0, 0xFFFF)
    timestamp = random.randint(0, 0xFFFFFFFF)
    ssrc = random.randint(0, 0xFFFFFFFF)
    next_send = time.monotonic()
    for offset in range(0, len(payload), _RTP_PAYLOAD_BYTES):
        chunk = payload[offset : offset + _RTP_PAYLOAD_BYTES]
        marker = 0x80 if offset == 0 else 0
        header = struct.pack(
            "!BBHII", 0x80, marker | payload_type, seq & 0xFFFF, timestamp, ssrc
        )
        sock.sendto(header + chunk, dest)
        seq = (seq + 1) & 0xFFFF
        timestamp = (timestamp + len(chunk)) & 0xFFFFFFFF
        next_send += ptime
        delay = next_send - time.monotonic()
        if delay > 0:
            time.sleep(delay)


def _call_blocking(settings: VoiceSettings, pcm: bytes) -> None:
    target_ip, target_port = _resolve_sip_target(settings)
    dest = (target_ip, target_port)
    local_ip = _local_ip(target_ip)

    sip_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    rtp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sip_sock.bind((local_ip, 0))
        sip_sock.settimeout(_SIP_TIMEOUT)
        local_port = sip_sock.getsockname()[1]
        rtp_sock.bind((local_ip, 0))
        rtp_port = rtp_sock.getsockname()[1]

        registrar = settings.sip_registrar
        caller = settings.sip_number
        from_uri = f"sip:{caller}@{registrar}"
        if settings.destination.lower().startswith("sip:"):
            to_uri = settings.destination
        else:
            to_uri = f"sip:{settings.destination}@{registrar}"
        # Request-URI for the outbound call is the destination user at the registrar.
        request_uri = to_uri
        call_id = f"{os.urandom(8).hex()}@{local_ip}"
        from_tag = os.urandom(6).hex()

        sdp = _build_sdp(local_ip, rtp_port)
        code, headers, body, invite_cseq = _send_request(
            sip_sock,
            dest,
            "INVITE",
            request_uri,
            local_ip=local_ip,
            local_port=local_port,
            call_id=call_id,
            from_uri=from_uri,
            to_uri=to_uri,
            from_tag=from_tag,
            to_tag=None,
            cseq=1,
            extra_headers={
                "Allow": "INVITE, ACK, BYE, CANCEL, OPTIONS",
                "P-Preferred-Identity": f"<{from_uri}>",
            },
            body=sdp,
            auth_user=settings.sip_auth_username,
            auth_password=settings.sip_password,
        )
        if code != 200:
            raise RuntimeError(f"INVITE rejected: {code}")

        remote_ip, remote_port, payloads = _parse_sdp(body)
        if 0 in payloads:
            codec = "PCMU"
        elif 8 in payloads:
            codec = "PCMA"
        else:
            raise RuntimeError(f"no supported codec in SDP answer: {payloads}")

        to_header = headers.get("to", [""])[0]
        tag_match = re.search(r";tag=([^;>\s]+)", to_header)
        to_tag = tag_match.group(1) if tag_match else ""
        remote_target = _contact_uri(headers) or request_uri
        # ACK for a 2xx reuses the INVITE's CSeq number and is its own transaction.
        branch = f"z9hG4bK{os.urandom(6).hex()}"
        ack = "\r\n".join(
            [
                f"ACK {remote_target} SIP/2.0",
                f"Via: SIP/2.0/UDP {local_ip}:{local_port};branch={branch};rport",
                "Max-Forwards: 70",
                f"From: <{from_uri}>;tag={from_tag}",
                f"To: <{to_uri}>" + (f";tag={to_tag}" if to_tag else ""),
                f"Call-ID: {call_id}",
                f"CSeq: {invite_cseq} ACK",
                f"Contact: <sip:{caller}@{local_ip}:{local_port}>",
                "Content-Length: 0",
                "",
                "",
            ]
        )
        sip_sock.sendto(ack.encode(), dest)

        encoded = _encode_g711(pcm, codec)
        _send_rtp(rtp_sock, (remote_ip, remote_port), encoded, codec)

        # Let the last packets drain, then end the call.
        time.sleep(0.8)
        bye_code, _, _, _ = _send_request(
            sip_sock,
            dest,
            "BYE",
            remote_target,
            local_ip=local_ip,
            local_port=local_port,
            call_id=call_id,
            from_uri=from_uri,
            to_uri=to_uri,
            from_tag=from_tag,
            to_tag=to_tag,
            cseq=invite_cseq + 1,
            auth_user=settings.sip_auth_username,
            auth_password=settings.sip_password,
        )
        if bye_code >= 300:
            _log.warning("BYE returned %s", bye_code)
    finally:
        sip_sock.close()
        rtp_sock.close()
