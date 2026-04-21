"""SettingsStoreResource 단위 테스트."""

from pathlib import Path

import pytest

from dagster_project.resources.settings_store import SettingsStoreResource


@pytest.fixture
def store(tmp_path: Path) -> SettingsStoreResource:
    s = SettingsStoreResource(db_path=str(tmp_path / "test_settings.duckdb"))
    s.ensure_table()
    return s


def test_ensure_table_creates_default_settings(store: SettingsStoreResource) -> None:
    settings = store.all_settings()
    keys = [s["key"] for s in settings]
    assert "anomaly.zscore.warning" in keys
    assert "budget.alert_threshold_pct" in keys


def test_get_float_existing_key(store: SettingsStoreResource) -> None:
    val = store.get_float("anomaly.zscore.warning", 99.0)
    assert val == pytest.approx(2.0)


def test_get_float_missing_key_returns_default(store: SettingsStoreResource) -> None:
    val = store.get_float("nonexistent.key", 42.5)
    assert val == pytest.approx(42.5)


def test_get_int_existing_key(store: SettingsStoreResource) -> None:
    val = store.get_int("reporting.lookback_days", 0)
    assert val == 30


def test_get_int_missing_key_returns_default(store: SettingsStoreResource) -> None:
    val = store.get_int("nonexistent.key", 99)
    assert val == 99


def test_get_str_existing_key(store: SettingsStoreResource) -> None:
    val = store.get_str("anomaly.active_detectors", "none")
    assert "zscore" in val


def test_get_str_missing_key_returns_default(store: SettingsStoreResource) -> None:
    val = store.get_str("nonexistent.key", "fallback_value")
    assert val == "fallback_value"


def test_set_value_insert(store: SettingsStoreResource) -> None:
    store.set_value("custom.new_key", "hello")
    val = store.get_str("custom.new_key", "default")
    assert val == "hello"


def test_set_value_update(store: SettingsStoreResource) -> None:
    store.set_value("anomaly.zscore.warning", "5.0")
    val = store.get_float("anomaly.zscore.warning", 0.0)
    assert val == pytest.approx(5.0)


def test_get_float_bad_db_returns_default() -> None:
    """DB 접근 불가 시 default를 반환한다."""
    store = SettingsStoreResource(db_path="/nonexistent/path/db.duckdb")
    val = store.get_float("some.key", 3.14)
    assert val == pytest.approx(3.14)


def test_get_int_bad_db_returns_default() -> None:
    store = SettingsStoreResource(db_path="/nonexistent/path/db.duckdb")
    val = store.get_int("some.key", 7)
    assert val == 7


def test_get_str_bad_db_returns_default() -> None:
    store = SettingsStoreResource(db_path="/nonexistent/path/db.duckdb")
    val = store.get_str("some.key", "fallback")
    assert val == "fallback"
