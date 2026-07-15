from sorena.tools import file_search_tool


def test_run_finds_known_file():
    result = file_search_tool.run("**/*.py", root="src")
    assert "router.py" in result
