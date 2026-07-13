from pathlib import Path

from tallymind import config


def test_parse_tally_ini_preserves_keys_with_spaces(tmp_path: Path) -> None:
    ini = tmp_path / "tally.ini"
    ini.write_text(
        ";; comment\n[TALLY]\nServerPort=9000\nClient Server=Both\nExport Path=C:\\Exports\n",
        encoding="utf-8",
    )
    settings = config.parse_tally_ini(ini)
    assert settings["ServerPort"] == "9000"
    assert settings["Client Server"] == "Both"
    assert settings["Export Path"] == "C:\\Exports"


def test_parse_tally_ini_missing_file_returns_empty(tmp_path: Path) -> None:
    assert config.parse_tally_ini(tmp_path / "missing.ini") == {}


def test_server_port_validates_range() -> None:
    assert config.server_port({"ServerPort": "1234"}) == 1234
    assert config.server_port({"ServerPort": "abc"}) == config.DEFAULT_PORT
    assert config.server_port({"ServerPort": "70000"}) == config.DEFAULT_PORT
    assert config.server_port(None) == config.DEFAULT_PORT


def test_normalize_install_dir_prefers_explicit_path(tmp_path: Path) -> None:
    assert config.normalize_install_dir(str(tmp_path)) == tmp_path


def test_normalize_install_dir_falls_back_to_default(monkeypatch) -> None:
    monkeypatch.delenv("TALLYPRIME_HOME", raising=False)
    monkeypatch.delenv("TALLY_HOME", raising=False)
    monkeypatch.setattr("shutil.which", lambda _name: None)
    assert config.normalize_install_dir() == config.DEFAULT_INSTALL_DIR
