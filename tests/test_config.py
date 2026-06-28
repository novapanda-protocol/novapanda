from troodon.config import NodeConfig


def test_config_from_env_defaults(monkeypatch):
    monkeypatch.delenv("TROODON_AUTH", raising=False)
    monkeypatch.delenv("TROODON_DB", raising=False)
    cfg = NodeConfig.from_env()
    assert cfg.auth is True
    assert cfg.settlement == "mock"
    assert cfg.db_path is None


def test_config_from_env_overrides(monkeypatch, tmp_path):
    db = str(tmp_path / "node.sqlite")
    monkeypatch.setenv("TROODON_AUTH", "0")
    monkeypatch.setenv("TROODON_DB", db)
    monkeypatch.setenv("TROODON_SETTLEMENT", "mock")
    cfg = NodeConfig.from_env()
    assert cfg.auth is False
    assert cfg.db_path == db
    assert cfg.make_store().__class__.__name__ == "SQLiteStore"
