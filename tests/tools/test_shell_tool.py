import pytest

from sorena.tools import shell_tool


def test_run_allows_whitelisted_command():
    result = shell_tool.run("whoami")
    assert result.strip() != ""


def test_run_rejects_command_not_on_allowlist():
    with pytest.raises(shell_tool.DisallowedCommandError):
        shell_tool.run("rm -rf /")
