from bagbot.config import DEFAULT_KRAKEN_BASE_URL, load_settings, parse_bool


def test_dry_run_defaults_to_true():
    settings = load_settings(env_file=None, environ={})
    assert settings.dry_run is True


def test_credentials_loaded_from_env():
    env = {"KRAKEN_API_KEY": "key", "KRAKEN_API_SECRET": "secret"}  # envshield:allow - fake test data
    settings = load_settings(env_file=None, environ=env)
    assert settings.has_credentials
    assert settings.api_key == "key"
    assert settings.api_secret == "secret"


def test_missing_credentials_flagged():
    settings = load_settings(env_file=None, environ={})
    assert not settings.has_credentials


def test_dry_run_can_be_disabled_explicitly():
    settings = load_settings(env_file=None, environ={"BAGBOT_DRY_RUN": "false"})
    assert settings.dry_run is False


def test_base_url_default_and_override():
    assert load_settings(env_file=None, environ={}).base_url == DEFAULT_KRAKEN_BASE_URL
    custom = load_settings(env_file=None, environ={"KRAKEN_BASE_URL": "https://example.test/"})
    assert custom.base_url == "https://example.test"


def test_parse_bool_variants():
    for truthy in ("1", "true", "TRUE", "yes", "on"):
        assert parse_bool(truthy, False) is True
    for falsy in ("0", "false", "no", "off", ""):
        assert parse_bool(falsy, True) is False
    assert parse_bool(None, True) is True
    assert parse_bool(None, False) is False
