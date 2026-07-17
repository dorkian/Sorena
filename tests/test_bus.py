from sorena.agents import bus


def test_log_event_then_recent_events_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(bus, "DB_PATH", tmp_path / "test_events.db")

    bus.log_event(agent="dayplanner", event_type="scheduled_event", payload="Dentist at 3pm")
    bus.log_event(agent="scribe", event_type="note_written", payload="Daily summary")

    events = bus.recent_events(limit=10)

    assert len(events) == 2
    # most recent first
    assert events[0]["agent"] == "scribe"
    assert events[0]["event_type"] == "note_written"
    assert events[1]["agent"] == "dayplanner"


def test_recent_events_respects_limit(tmp_path, monkeypatch):
    monkeypatch.setattr(bus, "DB_PATH", tmp_path / "test_events.db")

    for i in range(5):
        bus.log_event(agent="dayplanner", event_type="test", payload=str(i))

    events = bus.recent_events(limit=2)

    assert len(events) == 2
    assert events[0]["payload"] == "4"
    assert events[1]["payload"] == "3"


def test_recent_events_empty_db_returns_empty_list(tmp_path, monkeypatch):
    monkeypatch.setattr(bus, "DB_PATH", tmp_path / "test_events.db")

    assert bus.recent_events() == []
