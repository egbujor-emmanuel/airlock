import shutil
from pathlib import Path

from airlock.verify import load_folder, main, unreceived

EVIDENCE = Path(__file__).resolve().parents[1] / "docs" / "evidence" / "run-3"


def test_the_published_run_verifies(monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", ["airlock-verify", str(EVIDENCE)])

    assert main() == 0
    out = capsys.readouterr().out
    assert "acme" in out and "payco" in out and "INVALID" not in out
    assert "every approved crossing was countersigned" in out


def test_editing_one_character_is_caught(tmp_path, monkeypatch, capsys):
    folder = tmp_path / "run"
    shutil.copytree(EVIDENCE, folder)
    ledger = folder / "acme.jsonl"
    text = ledger.read_text(encoding="utf-8")
    ledger.write_text(text.replace("DeFi_Maroh", "DeFi_Marob", 1), encoding="utf-8")
    monkeypatch.setattr("sys.argv", ["airlock-verify", str(folder)])

    assert main() == 1
    assert "INVALID" in capsys.readouterr().out


def test_a_crossing_without_a_receipt_is_reported():
    ledgers, _ = load_folder(EVIDENCE)
    ledgers["payco"] = [e for e in ledgers["payco"] if e["type"] != "receipt"]

    assert any(m.startswith("acme ") for m in unreceived(ledgers))
