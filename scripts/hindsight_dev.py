from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from pathlib import Path


def _env(name: str, default: str | None = None) -> str:
    value = os.environ.get(name, default)
    if value is None or value == "":
        raise RuntimeError(f"Missing required env var: {name}")
    return value


def _build_hindsight_env(database_url: str) -> dict[str, str]:
    env = os.environ.copy()
    env["HINDSIGHT_API_HOST"] = _env("HINDSIGHT_BIND_HOST", "127.0.0.1")
    env["HINDSIGHT_API_PORT"] = _env("HINDSIGHT_BIND_PORT", "8888")
    env["HINDSIGHT_API_LLM_PROVIDER"] = _env("HINDSIGHT_LLM_PROVIDER", "openai")
    env["HINDSIGHT_API_LLM_MODEL"] = _env("HINDSIGHT_LLM_MODEL")
    env["HINDSIGHT_API_LLM_API_KEY"] = _env("HINDSIGHT_LLM_API_KEY", "dummy")
    env["HINDSIGHT_API_LLM_BASE_URL"] = _env("HINDSIGHT_LLM_BASE_URL")
    env["HINDSIGHT_API_DATABASE_URL"] = database_url
    env["HINDSIGHT_API_MIGRATION_DATABASE_URL"] = database_url
    return env


def _start_pg0(data_dir: Path):
    try:
        from pg0 import Pg0  # type: ignore
    except Exception as exc:  # pragma: no cover
        raise RuntimeError("pg0 package is required for explicit hindsight data_dir persistence") from exc

    data_dir.mkdir(parents=True, exist_ok=True)
    instance_name = "agentmux-hindsight"
    pg = Pg0(
        name=instance_name,
        username="hindsight",
        password="hindsight",
        database="hindsight",
        data_dir=str(data_dir),
    )
    info = pg.start()
    return pg, info.uri


def main() -> int:
    data_dir = Path(_env("HINDSIGHT_DATA_DIR", "~/data/hindsight")).expanduser()
    pg, database_url = _start_pg0(data_dir)

    env = _build_hindsight_env(database_url)
    host = env["HINDSIGHT_API_HOST"]
    port = env["HINDSIGHT_API_PORT"]

    print(f"hindsight persistence data_dir={data_dir}", flush=True)
    print(f"hindsight database_url={database_url}", flush=True)
    print(f"hindsight listening on http://{host}:{port}", flush=True)

    process = subprocess.Popen(
        ["uv", "run", "hindsight-api", "--host", host, "--port", port, "--no-access-log"],
        env=env,
        start_new_session=True,
    )

    def _shutdown(*_args):
        try:
            os.killpg(os.getpgid(process.pid), signal.SIGTERM)
        except ProcessLookupError:
            pass
        try:
            pg.stop()
        except Exception:
            pass

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)

    try:
        return process.wait()
    finally:
        _shutdown()
        time.sleep(0.1)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"hindsight_dev error: {exc}", file=sys.stderr)
        raise
