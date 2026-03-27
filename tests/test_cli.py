import sys

from veridoc.cli import main


def test_main_runs(capsys, monkeypatch):
    monkeypatch.setattr(sys, "argv", ["veridoc"])
    main()
    out = capsys.readouterr().out
    assert "veridoc" in out
