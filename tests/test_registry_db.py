import json
from pathlib import Path

import pytest

from novapanda.node import create_app
from novapanda.registry import load_default_registries
from novapanda.store import SQLiteStore

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "ed25519_signing_vector.json"


def test_sqlite_registry_save_and_load(tmp_path):
    store = SQLiteStore(str(tmp_path / "reg.sqlite"))
    onto, rules = load_default_registries()
    store.registry_save(onto, rules)

    onto2, rules2 = store.registry_load()
    assert rules2.get("R-energy-dc-meter-v1") is not None
    assert onto2.get("energy.electric.dc")["reserved"] is True


def test_create_app_seeds_registry_into_sqlite(tmp_path):
    path = str(tmp_path / "node.sqlite")
    create_app(seed=True, auth=False, store=SQLiteStore(path))
    store2 = SQLiteStore(path)
    loaded = store2.registry_load()
    assert loaded is not None
    _, rules = loaded
    assert rules.get("R-extract-invoice-v1") is not None


def test_second_startup_loads_registry_from_db_not_duplicate(tmp_path):
    path = str(tmp_path / "node.sqlite")
    app1 = create_app(seed=True, auth=False, store=SQLiteStore(path))
    n1 = len(app1.state.rules.list())

    app2 = create_app(seed=True, auth=False, store=SQLiteStore(path))
    assert len(app2.state.rules.list()) == n1
    assert app2.state.rules.get("R-energy-dc-meter-v1") is not None


def test_signing_vector_fixture_matches_python():
    from novapanda.auth import sign_request
    from novapanda.identity import Identity

    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    identity = Identity.from_private_bytes(bytes.fromhex(data["private_key_hex"]))
    assert identity.agent_id == data["agent_id"]
    body = data["body"].encode("utf-8")
    sig = sign_request(
        identity, data["method"], data["path"], data["nonce"], body,
    )
    assert sig == data["signature"]
