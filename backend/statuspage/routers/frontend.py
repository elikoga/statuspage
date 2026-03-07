import asyncio
import logging
import os
import pathlib
import re
import subprocess
import sys

import fastapi
import httpx
import psutil
import starlette.requests
from fastapi import APIRouter, Response
from fastapi.responses import StreamingResponse
from starlette.background import BackgroundTask

from statuspage.config import global_settings

logger = logging.getLogger(__name__)
logging.getLogger("httpx").setLevel(logging.WARNING)

FRONTEND_PORT = 33100 + (int(os.environ.get("UVICORN_PORT", 0)) % 10000)


def is_reload_enabled():
    return "--reload" in sys.argv


def frontend_binary_path():
    return global_settings.FRONTEND_BINARY_PATH


def detect_host_port():
    listen_to_ip_translation = {
        "0.0.0.0": "127.0.0.1",
        "::": "::1",
    }
    host_env = os.getenv("UVICORN_HOST")
    host_arg = (
        sys.argv[sys.argv.index("--host") + 1]
        if "--host" in sys.argv and len(sys.argv) > sys.argv.index("--host") + 1
        else None
    )
    port_env = os.getenv("UVICORN_PORT")
    port_arg = (
        sys.argv[sys.argv.index("--port") + 1]
        if "--port" in sys.argv and len(sys.argv) > sys.argv.index("--port") + 1
        else None
    )
    uvicorn_default_host = "127.0.0.1"
    uvicorn_default_port = 8000
    host = host_arg if host_arg else host_env if host_env else uvicorn_default_host
    port = port_arg if port_arg else port_env if port_env else uvicorn_default_port
    host = listen_to_ip_translation.get(host, host)
    port = int(port)
    return host, port


def env():
    host, port = detect_host_port()
    return {
        "PUBLIC_BASE_URL": global_settings.BASE_URL,
        "PRIVATE_BASE_URL": f"http://{host}:{port}",
    }


class Frontend:
    def __init__(self):
        self.url = f"http://127.0.0.1:{FRONTEND_PORT}"
        self.process = None
        self.started = asyncio.Event()
        self.stopped = False

    async def run(self):
        frontend_path = pathlib.Path(__file__).parent.parent.parent.parent / "frontend"
        assert (
            frontend_path.exists()
        ), f"frontend path {frontend_path} does not exist"

        if is_reload_enabled() and not frontend_binary_path():
            self.process = await asyncio.create_subprocess_exec(
                "npm",
                "run",
                "dev",
                "--",
                "--host=127.0.0.1",
                f"--port={FRONTEND_PORT}",
                "--strictPort",
                "--clearScreen",
                "false",
                cwd=frontend_path,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env={
                    "PATH": os.environ["PATH"],
                    **env(),
                },
            )
        elif not frontend_binary_path():
            self.process = await asyncio.create_subprocess_exec(
                "sh",
                "-c",
                f"npm run build && npm run preview -- --host 127.0.0.1 --port {FRONTEND_PORT}",
                cwd=frontend_path,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env={
                    "PORT": str(FRONTEND_PORT),
                    "HOST": "127.0.0.1",
                    "PATH": os.environ["PATH"],
                    **env(),
                },
            )
        else:
            self.process = await asyncio.create_subprocess_exec(
                frontend_binary_path(),
                env={
                    "PORT": str(FRONTEND_PORT),
                    "HOST": "127.0.0.1",
                    **env(),
                },
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

        asyncio.get_event_loop().create_task(self.raise_if_terminated())

        async def read_stream(stream: asyncio.StreamReader, level=logging.INFO):
            while not stream.at_eof():
                line = await stream.readline()
                if line:
                    logger.log(
                        level, "frontend: %s", line.decode("utf-8").strip()
                    )

        async def read_stream_wait_for_started(stream: asyncio.StreamReader):
            while not stream.at_eof():
                line = await stream.readline()
                if line:
                    logger.info("frontend: %s", line.decode("utf-8").strip())
                    if is_reload_enabled():
                        if re.search(r"Local: +http", line.decode("utf-8")):
                            self.started.set()
                            break
                    else:
                        if re.search(
                            r"Listening on http(s)?://\d+\.\d+\.\d+\.\d+:\d+",
                            line.decode("utf-8"),
                        ) or re.search(r"Local: +http", line.decode("utf-8")):
                            self.started.set()
                            break
                        elif re.search(
                            r"WebSocket server error: Port already in use",
                            line.decode("utf-8"),
                        ):
                            logger.error("frontend: port already in use")
                            await self.process.wait()
                            self.stopped = True
                            self.started.set()
            return await read_stream(stream)

        asyncio.create_task(read_stream_wait_for_started(self.process.stdout))
        asyncio.create_task(read_stream(self.process.stderr, level=logging.ERROR))

        await self.started.wait()

        if self.stopped:
            raise RuntimeError("frontend process stopped unexpectedly")

    async def raise_if_terminated(self):
        return_code = await self.process.wait()
        self.stopped = True
        self.started.set()
        logger.error("frontend process terminated with code %s", return_code)
        await asyncio.sleep(0.1)

    async def stop(self):
        if self.stopped:
            return
        self.stopped = True
        process_pid = self.process.pid
        parent = psutil.Process(process_pid)
        for child in parent.children(recursive=True):
            try:
                child.terminate()
            except psutil.NoSuchProcess:
                pass
            await asyncio.sleep(0.1)
            if child.is_running():
                child.kill()
        try:
            parent.terminate()
        except psutil.NoSuchProcess:
            pass
        await asyncio.sleep(0.1)
        if parent.is_running():
            parent.kill()
        await self.process.wait()


frontend = Frontend()

client = httpx.AsyncClient(base_url=frontend.url)

router = APIRouter()


async def _reverse_proxy(request: fastapi.Request):
    url = httpx.URL(path=request.url.path, query=request.url.query.encode("utf-8"))
    rp_req = client.build_request(
        request.method,
        url,
        headers=request.headers.raw,
        content=request.stream(),
        timeout=None,
    )
    try:
        rp_resp = await client.send(rp_req, stream=True)
        return StreamingResponse(
            rp_resp.aiter_raw(),
            status_code=rp_resp.status_code,
            headers=rp_resp.headers,
            background=BackgroundTask(rp_resp.aclose),
        )
    except starlette.requests.ClientDisconnect as e:
        logger.debug("client disconnected: %s", e)
    except httpx.RemoteProtocolError as e:
        logger.error("frontend request failed: %s", e)
    except httpx.ConnectError as e:
        logger.error("failed to connect to frontend: %s", e)
    except Exception as e:
        logger.error("proxy error: %s", e)
        raise e
    return Response(status_code=500)


router.add_route(
    "/{path:path}",
    _reverse_proxy,
    methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"],
)
