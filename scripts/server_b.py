"""Run a second, independent Switch server for Acme (two-server mode).

    uv run python scripts/server_b.py start     # create its database (once) and start it
    uv run python scripts/server_b.py status

Server A (the one Switch Console runs) holds the shared room and PayCo's room.
Server B is Acme's own deployment: its own database, its own secrets, its own admin
account and its own Telegram bot. Acme's private room, Acme's agent and the inside
half of Acme's envoy live only here, so nothing of Acme's is stored on server A
unless Acme's envoy carried it across, redacted, approved and signed.

It reuses Switch Console's bundled Python, switch-core and PostgreSQL, so there is
nothing extra to install. Settings and secrets are generated once into
.airlock/server-b/switch-core.env.
"""

from __future__ import annotations

import os
import secrets
import subprocess
import sys
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
NATIVE = Path(os.environ["APPDATA"]) / "switchdash" / "local-switch-server" / "native"
CORE_A_ENV = NATIVE / "run" / "switch-core.env"
STATE = ROOT / ".airlock" / "server-b"
ENV_FILE = STATE / "switch-core.env"
PORT = 62013
CALLBACK_PORT = 62012
DB_NAME = "switch_acme"


def read_env(path: Path) -> dict[str, str]:
    out = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            k, v = line.split("=", 1)
            out[k.strip()] = v.strip()
    return out


def python_exe() -> Path:
    return next(p for p in (NATIVE / "switch-core").rglob("python.exe") if "venv" in p.parts and "Scripts" in p.parts)



def ensure_env() -> dict[str, str]:
    """Server B's settings: server A's database host and roles, everything else its own."""
    if ENV_FILE.exists():
        return read_env(ENV_FILE)
    a = read_env(CORE_A_ENV)
    b = {
        "SERVER_HOST": "127.0.0.1",
        "SERVER_PORT": str(PORT),
        "COLLABORATION_CALLBACK_HOST": "127.0.0.1",
        "COLLABORATION_CALLBACK_PORT": str(CALLBACK_PORT),
        "DB_HOST": a["DB_HOST"],
        "DB_PORT": a["DB_PORT"],
        "DB_USER": a["DB_USER"],
        "DB_PASSWORD": a["DB_PASSWORD"],
        "DB_OWNER_USER": a["DB_OWNER_USER"],
        "DB_OWNER_PASSWORD": a["DB_OWNER_PASSWORD"],
        "DB_NAME": DB_NAME,
        "ID_SERVER_NAME": "acme.local",
        "AGENT_REGISTRATION_TOKEN": secrets.token_urlsafe(32),
        "JWT_SECRET_KEY": secrets.token_urlsafe(48),
        "SECRET_KEYS": f"acme:{secrets.token_urlsafe(32)}",
        "CONTROLLER_TOKEN_SECRET": secrets.token_urlsafe(32),
        "FEATURE_FLAGS_ENABLED": a.get("FEATURE_FLAGS_ENABLED", ""),
        "GATEWAY_ADMIN_EMAIL": "admin@acme.local",
        "GATEWAY_ADMIN_PASSWORD": secrets.token_urlsafe(18),
        "FRONTEND_BASE_URL": f"http://localhost:{PORT}",
        "GATEWAY_COOKIE_SECURE": "false",
        "GATEWAY_PUBLIC_URL": f"http://localhost:{PORT}",
        "OUTBOUND_ALLOWED_PRIVATE_HOSTS": "localhost,127.0.0.1",
        "TELEMETRY_ENABLED": "false",
    }
    STATE.mkdir(parents=True, exist_ok=True)
    ENV_FILE.write_text("".join(f"{k}={v}\n" for k, v in b.items()), encoding="utf-8")
    return b


CREATE_DB = """
import asyncio, os, asyncpg
async def main():
    conn = await asyncpg.connect(host=os.environ["DB_HOST"], port=int(os.environ["DB_PORT"]),
                                 user=os.environ["DB_OWNER_USER"], password=os.environ["DB_OWNER_PASSWORD"],
                                 database="postgres")
    name = os.environ["DB_NAME"]
    if not await conn.fetchval("SELECT 1 FROM pg_database WHERE datname=$1", name):
        await conn.execute(f'CREATE DATABASE "{name}"')
        print("created database", name)
    await conn.close()
asyncio.run(main())
"""


def ensure_database(env: dict[str, str]) -> None:
    """The bundled PostgreSQL has no psql, so use switch-core's own driver (asyncpg)."""
    child_env = {k: v for k, v in os.environ.items() if k != "ELECTRON_RUN_AS_NODE"}
    child_env.update(env)
    subprocess.run([str(python_exe()), "-c", CREATE_DB], env=child_env, check=True)


def healthy() -> bool:
    try:
        return httpx.get(f"http://127.0.0.1:{PORT}/health", timeout=3).status_code == 200
    except httpx.HTTPError:
        return False


def start() -> int:
    if healthy():
        print(f"server B already running on http://127.0.0.1:{PORT}")
        return 0
    env = ensure_env()
    ensure_database(env)
    python = python_exe()
    log = (STATE / "switch-core.log").open("ab")
    child_env = {k: v for k, v in os.environ.items() if k != "ELECTRON_RUN_AS_NODE"}
    child_env.update(env)
    flags = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS if sys.platform == "win32" else 0
    proc = subprocess.Popen([str(python), "-m", "switch_core.main"], cwd=python.parents[2], env=child_env,
                            stdout=log, stderr=log, stdin=subprocess.DEVNULL, creationflags=flags)
    (STATE / "pid").write_text(str(proc.pid), encoding="utf-8")
    for _ in range(60):
        if healthy():
            print(f"server B running on http://127.0.0.1:{PORT} (pid {proc.pid})")
            print(f"admin: {env['GATEWAY_ADMIN_EMAIL']} (password in {ENV_FILE.relative_to(ROOT)})")
            return 0
        if proc.poll() is not None:
            break
        time.sleep(2)
    print(f"server B didn't come up; see {(STATE / 'switch-core.log').relative_to(ROOT)}")
    return 1


def main() -> int:
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    if cmd == "start":
        return start()
    print(f"server B {'running' if healthy() else 'not running'} on http://127.0.0.1:{PORT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
