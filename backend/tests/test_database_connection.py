import ssl

from app import database


def test_local_mysql_does_not_enable_tls_without_setting(settings):
    options = database.build_connect_args(settings.model_copy(update={"db_ssl": False}))
    assert "ssl" not in options
    assert options["init_command"] == "SET time_zone = '+00:00'"


def test_tidb_tls_requires_valid_certificate_and_hostname(settings):
    options = database.build_connect_args(settings.model_copy(update={"db_ssl": True}))
    context = options["ssl"]
    assert isinstance(context, ssl.SSLContext)
    assert context.verify_mode == ssl.CERT_REQUIRED
    assert context.check_hostname is True


def test_tidb_engine_uses_full_username_port_and_password_safely(settings, monkeypatch):
    from pydantic import SecretStr

    tidb_settings = settings.model_copy(update={
        "db_host": "example.tidbcloud.com", "db_port": 4000,
        "db_name": "recruitment_db", "db_user": "prefix.root",
        "db_password": SecretStr("test-only-p@ss/word:with#symbols"), "db_ssl": True,
    })
    captured = {}
    sentinel = object()

    def capture_engine(url, **options):
        captured.update(url=url, **options)
        return sentinel

    database.get_engine.cache_clear()
    monkeypatch.setattr(database, "get_settings", lambda: tidb_settings)
    monkeypatch.setattr(database, "create_engine", capture_engine)
    try:
        assert database.get_engine() is sentinel
        assert captured["url"].host == "example.tidbcloud.com"
        assert captured["url"].port == 4000
        assert captured["url"].username == "prefix.root"
        assert captured["url"].password == "test-only-p@ss/word:with#symbols"
        assert captured["connect_args"]["ssl"].check_hostname is True
    finally:
        database.get_engine.cache_clear()
