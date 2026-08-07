"""Тесты аварийного сброса ожидания закрытия процесса (глобальная клавиша Alt+D).

Проверяют, что ProcessManager.close_process:
- прерывается (WaitAborted), если во время ожидания установлен abort_event;
- прокручивает очередь событий (pump_events) во время ожидания, чтобы глобальная
  клавиша могла быть доставлена в Qt-цикл;
- WaitAborted не проглатывается общим except Exception.
"""

import threading

import pytest

pytest.importorskip("win32gui")

from services.process_manager import Process1C, ProcessManager, WaitAborted  # noqa: E402


class _FakeProc:
    """Фейковый psutil.Process: PID в тестах не существует в системе."""

    def kill(self):
        pass

    def terminate(self):
        pass


def _patch_process_api(monkeypatch):
    import services.process_manager as pm

    monkeypatch.setattr(pm.psutil, "Process", lambda pid: _FakeProc())
    monkeypatch.setattr(pm.psutil, "pid_exists", lambda pid: True)


def _window_never_closes(monkeypatch):
    """Окно «не закрывается», процесс «жив» — ожидание может затянуться бесконечно."""
    import services.process_manager as pm

    _patch_process_api(monkeypatch)
    monkeypatch.setattr(pm.win32gui, "IsWindow", lambda hwnd: True)
    monkeypatch.setattr(pm.win32gui, "PostMessage", lambda *args: True)


def test_close_process_abort_raises_wait_aborted(monkeypatch):
    """Установка abort_event во время ожидания прерывает его исключением WaitAborted."""
    _window_never_closes(monkeypatch)

    abort = threading.Event()
    pump_calls = []

    def pump():
        pump_calls.append(1)
        abort.set()  # имитация Alt+D, доставленной через QApplication.processEvents

    proc = Process1C(pid=12345, name="Тест", hwnd=999)

    with pytest.raises(WaitAborted):
        ProcessManager.close_process(proc, force=False, abort_event=abort, pump_events=pump)

    assert pump_calls  # очередь событий прокручивалась во время ожидания


def test_close_process_abort_without_event_pump(monkeypatch):
    """abort_event работает и без pump_events (проверка на входе в цикл)."""
    _window_never_closes(monkeypatch)

    abort = threading.Event()
    abort.set()  # «передумал закрывать» ещё до начала ожидания

    proc = Process1C(pid=12345, name="Тест", hwnd=999)

    with pytest.raises(WaitAborted):
        ProcessManager.close_process(proc, force=False, abort_event=abort)


def test_close_process_returns_true_when_window_closes(monkeypatch):
    """Без прерывания: после закрытия окна ожидание завершается успешно (True)."""
    import services.process_manager as pm

    # Первый вызов IsWindow (проверка перед WM_CLOSE) → True, дальше → False
    calls = {"n": 0}

    def is_window(hwnd):
        calls["n"] += 1
        return calls["n"] == 1

    _patch_process_api(monkeypatch)
    monkeypatch.setattr(pm.win32gui, "IsWindow", is_window)
    monkeypatch.setattr(pm.win32gui, "PostMessage", lambda *args: True)

    proc = Process1C(pid=12345, name="Тест", hwnd=999)

    assert ProcessManager.close_process(proc, force=False) is True
    assert calls["n"] == 2


def test_close_process_abort_not_swallowed_by_generic_except(monkeypatch):
    """WaitAborted пробрасывается наверх, а не превращается в return False."""
    _window_never_closes(monkeypatch)

    abort = threading.Event()
    abort.set()
    proc = Process1C(pid=12345, name="Тест", hwnd=999)

    with pytest.raises(WaitAborted):
        ProcessManager.close_process(proc, force=False, abort_event=abort)
