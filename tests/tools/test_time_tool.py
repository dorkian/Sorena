from sorena.tools import time_tool


def test_run_returns_iso_utc_string():
    result = time_tool.run()
    assert "T" in result
    assert result.endswith("+00:00")
