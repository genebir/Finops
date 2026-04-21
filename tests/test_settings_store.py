"""SettingsStoreResource 단위 테스트."""

import pytest

from dagster_project.resources.settings_store import SettingsStoreResource


@pytest.fixture
def store() -> SettingsStoreResource:
    s = SettingsStoreResource()
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
    # cleanup
    try:
        conn = store._connect()
        cur = conn.cursor()
        cur.execute("DELETE FROM platform_settings WHERE key = %s", ["custom.new_key"])
        cur.close()
        conn.close()
    except Exception:
        pass


def test_set_value_update(store: SettingsStoreResource) -> None:
    original = store.get_float("anomaly.zscore.warning", 0.0)
    store.set_value("anomaly.zscore.warning", "5.0")
    val = store.get_float("anomaly.zscore.warning", 0.0)
    assert val == pytest.approx(5.0)
    # restore
    store.set_value("anomaly.zscore.warning", str(original))


def test_ensure_table_idempotent(store: SettingsStoreResource) -> None:
    """ensure_table 중복 호출해도 에러 없음."""
    store.ensure_table()
    store.ensure_table()
    settings = store.all_settings()
    assert isinstance(settings, list)
