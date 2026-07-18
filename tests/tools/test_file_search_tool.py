from sorena.tools import file_search_tool


def test_run_finds_known_file():
    result = file_search_tool.run("**/*.py", root="src")
    assert "router.py" in result


def test_run_rejects_traversal_outside_base_dir():
    result = file_search_tool.run("*", root="../..")
    assert "Refused" in result


def test_run_rejects_absolute_root_outside_base_dir():
    result = file_search_tool.run("*", root="C:/Users")
    assert "Refused" in result
