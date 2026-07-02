from novapanda.config import NodeConfig


def test_config_from_env_defaults(monkeypatch):
    monkeypatch.delenv("NOVAPANDA_AUTH", raising=False)
    monkeypatch.delenv("NOVAPANDA_DB", raising=False)
    cfg = NodeConfig.from_env()
    assert cfg.auth is True
    assert cfg.settlement == "mock"
    assert cfg.db_path is None


def test_config_from_env_overrides(monkeypatch, tmp_path):
    db = str(tmp_path / "node.sqlite")
    monkeypatch.setenv("NOVAPANDA_AUTH", "0")
    monkeypatch.setenv("NOVAPANDA_DB", db)
    monkeypatch.setenv("NOVAPANDA_SETTLEMENT", "mock")
    cfg = NodeConfig.from_env()
    assert cfg.auth is False
    assert cfg.db_path == db
    assert cfg.make_store().__class__.__name__ == "SQLiteStore"
