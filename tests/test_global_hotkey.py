"""Тесты менеджера глобальных горячих клавиш (Windows API)."""

import pytest


def test_module_imports():
    """Модуль импортируется без ошибок на любой платформе."""
    import gui.hotkeys.global_hotkey_manager as g

    assert hasattr(g, "GlobalHotkeyManager")


def test_vendored_dbm_client_imports():
    """Vendored клиент DBM API (src/databases_api.py) импортируется статически —
    без рантайм-манипуляций sys.path (как в PyInstaller-сборке)."""
    import databases_api

    assert hasattr(databases_api, "get_user_snapshots")
    assert hasattr(databases_api, "get_databases")
    assert hasattr(databases_api, "create_snapshot")
    assert hasattr(databases_api, "get_task_status")
    assert hasattr(databases_api, "get_erp_servers")


def test_hotkey_reads_config_dynamically():
    """Комбинация читается из launcher.toml (config.py загружает его динамически),
    а не захардкожена в менеджере."""
    import config
    from gui.hotkeys.global_hotkey_manager import GlobalHotkeyManager

    class _Stub:
        pass

    mgr = GlobalHotkeyManager(_Stub())
    assert mgr.HOTKEY_MODIFIERS == config.GLOBAL_HOTKEY_MODIFIERS
    assert mgr.HOTKEY_VK == config.GLOBAL_HOTKEY_VK
    # Для дефолта Alt+D имя читаемое, без fallback VK_0x...
    name = mgr.get_hotkey_name()
    assert name == "Alt+D"


def test_hotkey_name_covers_common_keys():
    """Читаемое имя строится для любых VK из config (буквы, цифры, F1–F12)."""
    from gui.hotkeys.global_hotkey_manager import GlobalHotkeyManager

    class _Stub:
        pass

    for vk, expected in [(0x41, "A"), (0x31, "1"), (0x70, "F1"), (0x7B, "F12")]:
        mgr = GlobalHotkeyManager(_Stub())
        mgr.HOTKEY_VK = vk
        assert mgr.get_hotkey_name() == f"Alt+{expected}"


def test_hwnd_argtypes_configured_on_windows():
    """Регрессия: RegisterHotKey принимает большой 64-битный hwnd без OverflowError."""
    import ctypes
    from ctypes import wintypes

    import gui.hotkeys.global_hotkey_manager as g

    if not g.WINDOWS_HOTKEY_AVAILABLE:
        pytest.skip("Windows API недоступен (не Windows)")

    user32 = ctypes.windll.user32
    # сигнатуры заданы — ctypes не пытается сжать HWND до c_int
    assert user32.RegisterHotKey.argtypes is not None
    assert user32.UnregisterHotKey.argtypes is not None

    # большой HWND (как winId() окна) конвертируется в pointer-size без OverflowError
    big = wintypes.HWND(2**60)
    assert big.value == 2**60
