from sorena import main


def test_main_runs(capsys):
    main()
    assert "sorena" in capsys.readouterr().out.lower()
