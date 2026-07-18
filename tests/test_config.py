import os
import subprocess
import sys


def test_config_loads_env_vars_even_when_imported_before_litellm(tmp_path):
    """Regression test for a real bug: litellm's own import has a side effect
    of calling load_dotenv(), which is what let router.py (which imports
    litellm before sorena.config) see .env values -- but any caller that
    reaches sorena.config first (e.g. face.py's on-connect config message)
    got stuck with the hardcoded defaults, silently ignoring .env. Must run
    in a real subprocess: within this test process, sorena.config (and
    litellm) are already imported and cached in sys.modules, so re-importing
    here wouldn't re-execute the module-level code being tested."""
    env_file = tmp_path / ".env"
    env_file.write_text("SORENA_PROVIDER_CHAIN=some/model-a,some/model-b\n")

    # load_dotenv() defaults to override=False -- inheriting this test process's
    # os.environ verbatim would carry over whatever the REAL project .env already
    # loaded into it (another test importing litellm earlier in this run), which
    # would silently shadow the tmp .env this test actually means to exercise.
    clean_env = {k: v for k, v in os.environ.items() if k != "SORENA_PROVIDER_CHAIN"}

    result = subprocess.run(
        [sys.executable, "-c", "from sorena import config; print(config.PROVIDER_CHAIN)"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=30,
        env=clean_env,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "['some/model-a', 'some/model-b']"
