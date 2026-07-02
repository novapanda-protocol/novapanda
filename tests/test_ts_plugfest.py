import shutil
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest
import uvicorn

from novapanda.node import create_app

ROOT = Path(__file__).resolve().parents[1]
TS_ROOT = ROOT / "sdk" / "typescript"
SCRIPT = TS_ROOT / "test" / "plugfest_lifecycle.mjs"


def _free_port() -> int:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
@pytest.mark.skipif(not SCRIPT.is_file(), reason="plugfest_lifecycle.mjs missing")
def test_ts_sdk_auth_lifecycle_against_uvicorn():
    assert (TS_ROOT / "dist" / "index.js").is_file(), "run npm run build in sdk/typescript first"

    port = _free_port()
    app = create_app(seed=True, auth=True)
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    time.sleep(0.5)

    r = subprocess.run(
        ["node", str(SCRIPT), f"http://127.0.0.1:{port}"],
        cwd=str(TS_ROOT),
        capture_output=True,
        text=True,
    )
    assert r.returncode == 0, r.stderr or r.stdout
    assert '"ok":true' in r.stdout.replace(" ", "")
