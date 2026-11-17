"""whistlecode.py: the P0 commands frame and roundtrip."""
import importlib.util
from pathlib import Path

import pytest

WC = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def cli():
    spec = importlib.util.spec_from_file_location("whistlecode_cli", WC / "whistlecode.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_frame(cli, capsys):
    assert cli.main(["frame", "HI", "--key", "reef42", "--nonce", "7"]) == 0
    out = capsys.readouterr().out
    assert "3 preamble + 12 header + 24 payload = 39" in out
    assert "header symbols  : e b 0 b 3 d 1 2 5 a 9 5" in out


def test_roundtrip_repairs(cli, capsys):
    assert cli.main(["roundtrip", "MEET AT DAWN", "--key", "k", "--nonce", "1", "--wrong", "2", "--erased", "4"]) == 0
    assert "result   : OK -> 'MEET AT DAWN'" in capsys.readouterr().out


def test_roundtrip_fails_cleanly(cli, capsys):
    assert cli.main(["roundtrip", "MEET AT DAWN", "--key", "k", "--nonce", "1", "--erased", "40"]) == 1
    assert "result   : FAILED" in capsys.readouterr().out


def test_bad_message(cli, capsys):
    assert cli.main(["frame", "x" * 141, "--key", "k"]) == 2
    assert "error:" in capsys.readouterr().err
