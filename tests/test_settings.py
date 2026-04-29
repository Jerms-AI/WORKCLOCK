from workclock import settings as settings_mod


def test_read_settings_returns_defaults_when_missing(tmp_appdata):
    s = settings_mod.read_settings()
    assert s == {
        "always_on_top": True,
        "idle_threshold_minutes": 15,
        "remember_window_position": True,
        "window_position": None,
    }


def test_write_then_read_round_trips(tmp_appdata):
    settings_mod.write_settings({
        "always_on_top": False,
        "idle_threshold_minutes": 30,
        "remember_window_position": True,
        "window_position": [100, 200],
    })
    s = settings_mod.read_settings()
    assert s["always_on_top"] is False
    assert s["idle_threshold_minutes"] == 30
    assert s["window_position"] == [100, 200]


def test_partial_settings_merged_with_defaults(tmp_appdata):
    import json
    from workclock.settings import _settings_file
    _settings_file().parent.mkdir(parents=True, exist_ok=True)
    _settings_file().write_text(json.dumps({"idle_threshold_minutes": 5}))
    s = settings_mod.read_settings()
    assert s["idle_threshold_minutes"] == 5
    assert s["always_on_top"] is True
