"""Тесты внешнего конфига launcher.toml — динамическая загрузка настроек.

config.py читает launcher.toml (рядом с exe/модулем) поверх встроенных значений;
повреждённый или отсутствующий файл не должен ронять приложение.
"""

import sys
from pathlib import Path

import config


def test_defaults_when_config_missing(tmp_path):
    settings = config.load_settings(tmp_path / "no_such.toml")
    assert settings["hotkey"] == {"modifiers": 0x0001, "vk": 0x44}
    assert settings["encoding"] == "utf-8-sig"
    assert settings["tracked_applications"]  # дефолтный список непустой


def test_toml_overrides_paths_and_hotkey(tmp_path):
    cfg = tmp_path / "launcher.toml"
    cfg.write_text(
        "[base]\n"
        "ir_tools_path = 'C:\\tmp\\ir.epf'\n"
        "[hotkey]\n"
        "modifiers = 'Alt+Ctrl+Shift'\n"
        "vk = '0x31'\n",
        encoding="utf-8",
    )
    settings = config.load_settings(cfg)
    assert settings["ir_tools_path"] == "C:\\tmp\\ir.epf"
    assert settings["hotkey"]["modifiers"] == 0x0001 | 0x0002 | 0x0004  # 7
    assert settings["hotkey"]["vk"] == 0x31
    # ключи, не заданные в toml, остаются дефолтными
    assert str(settings["cf_dump_path"]).startswith("D:")


def test_toml_overrides_tracked_apps(tmp_path):
    cfg = tmp_path / "launcher.toml"
    cfg.write_text(
        "[[tracked_applications]]\n"
        "process_name = 'myapp.exe'\n"
        "display_name = 'MyApp'\n"
        "icon = 'X'\n"
        "launch_path = 'C:\\apps\\myapp.exe'\n",
        encoding="utf-8",
    )
    settings = config.load_settings(cfg)
    assert len(settings["tracked_applications"]) == 1
    assert settings["tracked_applications"][0]["process_name"] == "myapp.exe"


def test_invalid_toml_falls_back_to_defaults(tmp_path, capsys):
    cfg = tmp_path / "launcher.toml"
    cfg.write_text("this is not [valid toml", encoding="utf-8")
    settings = config.load_settings(cfg)
    # повреждённый файл не роняет загрузку — используются дефолты
    assert settings["hotkey"]["vk"] == 0x44
    assert "Ошибка чтения настроек" in capsys.readouterr().out


def test_hotkey_int_modifiers_accepted(tmp_path):
    cfg = tmp_path / "launcher.toml"
    cfg.write_text("[hotkey]\nmodifiers = 7\nvk = 0x44\n", encoding="utf-8")
    settings = config.load_settings(cfg)
    assert settings["hotkey"]["modifiers"] == 7


def test_config_module_loaded_from_real_toml():
    # В исходниках рядом с config.py лежит src/launcher.toml — модуль обязан
    # подхватить его. Проверяем самосогласованность (устойчиво к изменению
    # конфига оператором: значения модуля == значения из найденного файла).
    cfg_path = config.find_config_file()
    assert cfg_path is not None and cfg_path.name == "launcher.toml"
    settings = config.load_settings(cfg_path)
    assert config.GLOBAL_HOTKEY_MODIFIERS == settings["hotkey"]["modifiers"]
    assert config.GLOBAL_HOTKEY_VK == settings["hotkey"]["vk"]


def test_frozen_prefers_config_next_to_exe(monkeypatch, tmp_path):
    """В сборке конфиг ищется в первую очередь РЯДОМ С exe (dist\\launcher.toml)."""
    exe_dir = tmp_path / "dist"
    exe_dir.mkdir()
    (exe_dir / "launcher.toml").write_text(
        "[hotkey]\nmodifiers = 'Ctrl+Shift'\nvk = '0x31'\n", encoding="utf-8"
    )
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(exe_dir / "app.exe"))

    found = config.find_config_file()
    assert found == exe_dir / "launcher.toml"


def test_frozen_loads_config_next_to_exe(monkeypatch, tmp_path):
    """Динамическая загрузка: изменение launcher.toml рядом с exe меняет настройки
    без пересборки (Ctrl+Shift+1 вместо Alt+D)."""
    exe_dir = tmp_path / "dist"
    exe_dir.mkdir()
    (exe_dir / "launcher.toml").write_text(
        "[hotkey]\nmodifiers = 'Ctrl+Shift'\nvk = '0x31'\n", encoding="utf-8"
    )
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(exe_dir / "app.exe"))

    settings = config.load_settings()  # без явного пути — поиск рядом с exe
    assert settings["hotkey"]["modifiers"] == 0x0002 | 0x0004  # Ctrl+Shift
    assert settings["hotkey"]["vk"] == 0x31

def test_highlighting_bsl_keywords_string_and_array(tmp_path):
    """[highlighting] bsl_keywords: строка или TOML-массив строк — оба варианта."""
    cfg = tmp_path / "launcher.toml"
    cfg.write_text("[highlighting]\nbsl_keywords = 'Тогда ИначеЕсли'\n", encoding="utf-8")
    settings = config.load_settings(cfg)
    assert settings["highlighting"]["bsl_keywords"].split() == ["Тогда", "ИначеЕсли"]

    cfg.write_text("[highlighting]\nbsl_keywords = ['Процедура', 'Функция']\n", encoding="utf-8")
    settings = config.load_settings(cfg)
    assert settings["highlighting"]["bsl_keywords"].split() == ["Процедура", "Функция"]

    cfg.write_text("[highlighting]\nbsl_keywords = ''\n", encoding="utf-8")
    settings = config.load_settings(cfg)
    assert "Тогда" in settings["highlighting"]["bsl_keywords"]  # пусто → дефолт
