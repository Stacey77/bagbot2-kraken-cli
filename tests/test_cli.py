import os

from typer.testing import CliRunner

from bagbot.cli import app

runner = CliRunner()


def _clean_env(monkeypatch):
    for var in ("KRAKEN_API_KEY", "KRAKEN_API_SECRET", "BAGBOT_DRY_RUN"):
        monkeypatch.delenv(var, raising=False)


def test_buy_defaults_to_dry_run_without_credentials(monkeypatch):
    _clean_env(monkeypatch)
    result = runner.invoke(app, ["--env-file", "nonexistent.env", "buy", "XBTUSD", "0.01"])
    assert result.exit_code == 0
    assert "[dry-run]" in result.output
    assert "DRYRUN-" in result.output


def test_live_flag_stays_dry_run_when_env_still_true(monkeypatch):
    _clean_env(monkeypatch)
    monkeypatch.setenv("BAGBOT_DRY_RUN", "true")
    result = runner.invoke(app, ["--env-file", "nonexistent.env", "--live", "buy", "XBTUSD", "0.01"])
    assert result.exit_code == 0
    assert "staying in dry-run" in result.output
    assert "DRYRUN-" in result.output


def test_balance_requires_credentials(monkeypatch):
    _clean_env(monkeypatch)
    result = runner.invoke(app, ["--env-file", "nonexistent.env", "balance"])
    assert result.exit_code == 2
    assert "KRAKEN_API_KEY" in result.output


def test_invalid_volume_rejected(monkeypatch):
    _clean_env(monkeypatch)
    result = runner.invoke(app, ["--env-file", "nonexistent.env", "buy", "XBTUSD", "0"])
    assert result.exit_code == 1
    assert "volume must be positive" in result.output
