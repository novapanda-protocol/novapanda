"""OpenClaw 结对 CLI：同机 run → SETTLED + reverify。"""

from __future__ import annotations

import json
import socket
import threading
import time
from pathlib import Path

import pytest
import uvicorn

from novapanda.node import create_app

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "demo" / "openclaw_pair" / "pair_cli.py"


def _free_port() -> int:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


def _load_cli():
    import importlib.util

    spec = importlib.util.spec_from_file_location("openclaw_pair_cli", CLI)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.mark.skipif(not CLI.is_file(), reason="pair_cli missing")
def test_openclaw_pair_run_settled(tmp_path: Path):
    port = _free_port()
    app = create_app(seed=True, auth=False)
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    time.sleep(0.5)

    pair_cli = _load_cli()
    root = tmp_path / "pair"
    base = f"http://127.0.0.1:{port}"
    assert pair_cli.main(["--root", str(root), "--base-url", base, "init"]) == 0
    assert pair_cli.main(["--root", str(root), "--base-url", base, "run"]) == 0
    last = json.loads((root / "last_run.json").read_text(encoding="utf-8"))
    assert last["ok"] is True
    assert last["state"] == "SETTLED"
    assert last["settlement"] == "mock"

    skill_rc = pair_cli.main([
        "--root", str(root), "--base-url", base,
        "skill", "--role", "claw", "--name", "adopter_vault_stats",
    ])
    assert skill_rc == 0
