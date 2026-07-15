from sorena.tools import web_search_tool


class FakeResponse:
    def raise_for_status(self):
        pass

    def json(self):
        return {"results": [{"title": "Example", "content": "Example content"}]}


def test_run_formats_results(monkeypatch):
    monkeypatch.setenv("TAVILY_API_KEY", "fake-key")
    monkeypatch.setattr(web_search_tool.requests, "post", lambda *a, **kw: FakeResponse())

    result = web_search_tool.run("some query")

    assert "Example" in result
    assert "Example content" in result
