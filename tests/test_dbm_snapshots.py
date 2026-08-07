"""Тесты интеграции с DBM API (snapshots): токен раз в час, «голубые» снапшоты."""

from datetime import datetime
from types import SimpleNamespace

import pytest

import services.dbm_snapshots as dbm
from services.web_publisher import PublishError


def make_snap(snap_id, db_id, name, expiration, state="READY", connection_string=""):
    return {
        "id": snap_id,
        "databaseId": db_id,
        "name": name,
        "state": state,
        "expirationDate": expiration,
        "connectionString": connection_string,
    }


def make_base(name, connect):
    return SimpleNamespace(name=name, connect=connect)


# ------------------------------------------------------------------ #
#  Парсинг дат и Ref                                                  #
# ------------------------------------------------------------------ #

def test_parse_date():
    assert dbm._parse_date("2026-08-15T12:00:00") is not None
    assert dbm._parse_date("2026-08-15") is not None
    assert dbm._parse_date(None) is None
    assert dbm._parse_date("мусор") is None


def test_ref_from_connect():
    assert dbm._ref_from_connect('Srvr="srv-1c-8325:1541";Ref="blank_database_0804_Pechericadv_3";') \
        == "blank_database_0804_Pechericadv_3"
    assert dbm._ref_from_connect("Srvr=x;Ref='zup';") == "zup"
    assert dbm._ref_from_connect("File=D:/bases/1Cv8.1CD;") == ""


# ------------------------------------------------------------------ #
#  Логика «голубой» строки (есть более новый снапшот)                 #
# ------------------------------------------------------------------ #

def test_find_updatable_snapshots():
    old = make_snap(1, 10, "snap_old", "2026-08-10T12:00:00", connection_string="conn_old")
    new = make_snap(2, 10, "snap_new", "2026-08-15T12:00:00", connection_string="conn_new")
    other = make_snap(3, 20, "snap_other", "2026-08-20T12:00:00", connection_string="conn_other")

    def get_db(db_id):
        return [old, new] if db_id == 10 else [other]

    updatable = dbm.find_updatable_snapshots([old, other], get_db)

    assert updatable == [old]  # у 10 есть более новый (2026-08-15 > 2026-08-10)
    assert other not in updatable


def test_find_updatable_no_fetch_error_handling():
    """Ошибка выборки снапшота базы не должна валить всё."""
    snap = make_snap(1, 10, "s", "2026-08-10", connection_string="c")

    def get_db(db_id):
        raise RuntimeError("boom")

    assert dbm.find_updatable_snapshots([snap], get_db) == []


# ------------------------------------------------------------------ #
#  Кандидаты на обновление (базы лаунчера)                            #
# ------------------------------------------------------------------ #

def test_build_update_candidates():
    old = make_snap(1, 10, "blank_database_0804_Pechericadv_3", "2026-08-10T12:00:00",
                    connection_string='Srvr="srv-1c-8325:1541";Ref="blank_database_0804_Pechericadv_3";')
    new = make_snap(2, 10, "blank_database_0805_Pechericadv_3", "2026-08-15T12:00:00",
                    connection_string='Srvr="srv-1c-8325:1541";Ref="blank_database_0805_Pechericadv_3";')

    zup_hran = make_base("ЗУП ХРАН", old["connectionString"])           # без даты — обновляемая
    zup_old = make_base("ЗУП ХРАН 2026-07-01", old["connectionString"])  # с датой — в списке, но не обновляемая
    other_base = make_base("Бухгалтерия", 'Srvr="s";Ref="buf";')

    rows = dbm.build_update_candidates([old, new], [zup_hran, zup_old, other_base],
                                       lambda db_id: [old, new])

    # обе «ХРАН»-базы в списке (полный список «Мои снапшоты»), Бухгалтерия — нет
    assert [r["base"].name for r in rows] == ["ЗУП ХРАН", "ЗУП ХРАН 2026-07-01"]
    fresh, dated = rows
    assert fresh["updatable"] is True
    assert fresh["blue"] is True
    assert fresh["dated"] is False
    assert fresh["new_connect"] == new["connectionString"]
    assert fresh["new_name"] == "blank_database_0805_Pechericadv_3"
    # датированная копия на голубом снапшоте тоже обновляема (кнопка есть при снятом фильтре)
    assert dated["updatable"] is True
    assert dated["blue"] is True
    assert dated["dated"] is True


def test_build_update_candidates_all_fresh():
    snap = make_snap(1, 10, "snap", "2026-08-15",
                     connection_string='Srvr="s";Ref="snap";')
    base = make_base("ЗУП ХРАН", snap["connectionString"])
    rows = dbm.build_update_candidates([snap], [base], lambda db_id: [snap])
    assert len(rows) == 1
    assert rows[0]["updatable"] is False  # самый новый — обновлять нечего


def test_multiple_bases_share_one_snapshot():
    """Несколько «ХРАН»-баз на одном старом снапшоте — обновляются обе,
    даже если новый снапшот уже занят третьей базой."""
    old = make_snap(1, 10, "old_snap", "2026-08-10T12:00:00",
                    connection_string='Srvr="s";Ref="old_snap";')
    new = make_snap(2, 10, "new_snap", "2026-08-15T12:00:00",
                    connection_string='Srvr="s";Ref="new_snap";')
    zup = make_base("ЗУП ХРАН РАСШ", old["connectionString"])
    mag = make_base("МАГ ХРАН", old["connectionString"])
    taker = make_base("СОРВ ХРАН", new["connectionString"])  # уже на новом снапшоте

    rows = dbm.build_update_candidates([old, new], [zup, mag, taker], lambda db_id: [old, new])

    by_name = {r["base"].name: r for r in rows}
    assert by_name["ЗУП ХРАН РАСШ"]["updatable"] is True
    assert by_name["МАГ ХРАН"]["updatable"] is True
    assert by_name["СОРВ ХРАН"]["updatable"] is False  # уже на новейшем
    assert by_name["ЗУП ХРАН РАСШ"]["new_connect"] == new["connectionString"]


def test_create_snapshot_wrapper_delegates(monkeypatch):
    fake = SimpleNamespace(create_snapshot=lambda t, m, s, d: {"task": d})
    monkeypatch.setattr(dbm, "databases_api", fake)  # import статический — мокаем атрибут модуля
    assert dbm.create_snapshot("tok", "m1", "s1", "desc") == {"task": "desc"}


# ------------------------------------------------------------------ #
#  Токен: запрос раз в час                                             #
# ------------------------------------------------------------------ #

def test_token_cached_within_hour(monkeypatch):
    calls = []

    def fake_helper():
        calls.append(1)
        return "token-1"

    monkeypatch.setattr(dbm, "_request_token_via_helper", fake_helper)
    monkeypatch.setattr(dbm.time, "time", lambda: 1000.0)
    dbm._token_cache = {"token": None, "fetched_at": 0.0}
    assert dbm.get_valid_token() == "token-1"
    assert dbm.get_valid_token() == "token-1"  # в пределах часа — без нового запроса
    assert len(calls) == 1


def test_token_refreshed_after_hour(monkeypatch):
    calls = []

    def fake_helper():
        calls.append(1)
        return f"token-{len(calls)}"

    monkeypatch.setattr(dbm, "_request_token_via_helper", fake_helper)
    times = iter([1000.0, 1001.0, 1000.0 + 3600.0 + 1.0])
    monkeypatch.setattr(dbm.time, "time", lambda: next(times))
    dbm._token_cache = {"token": None, "fetched_at": 0.0}
    assert dbm.get_valid_token() == "token-1"
    assert dbm.get_valid_token() == "token-1"  # кэш
    assert dbm.get_valid_token() == "token-2"  # час прошёл — запрошен заново
    assert len(calls) == 2


def test_token_helper_failure_returns_none(monkeypatch):
    monkeypatch.setattr(dbm, "_request_token_via_helper", lambda: None)
    monkeypatch.setattr(dbm.time, "time", lambda: 1.0)
    dbm._token_cache = {"token": None, "fetched_at": 0.0}
    assert dbm.get_valid_token() is None


# ------------------------------------------------------------------ #
#  Операция create_copy_with_connect (без диалога)                    #
# ------------------------------------------------------------------ #

def test_create_copy_with_connect(qt_app):
    from gui.actions.database_operations import DatabaseOperations
    from models.database import Database1C

    old_connect = 'Srvr="srv-1c-8325:1541";Ref="old_snap";'
    new_connect = 'Srvr="srv-1c-8325:1541";Ref="new_snap";'
    db = Database1C(id="zup-hran", folder="/Хранилища", name="ЗУП ХРАН",
                    connect=old_connect, version="8.3.25.1394")
    win = SimpleNamespace(statusBar=SimpleNamespace(showMessage=lambda m: None))
    saved = []
    ops = DatabaseOperations.__new__(DatabaseOperations)
    ops.window = win
    ops.all_bases = [db]
    ops.save_callback = lambda: saved.append(True)
    ops.reload_callback = lambda: None

    fresh = ops.create_copy_with_connect(db, Database1C, new_connect)

    assert db.name == f"ЗУП ХРАН {datetime.now().strftime('%Y-%m-%d')}"
    assert fresh.name == "ЗУП ХРАН"
    assert fresh.connect == new_connect
    assert len(ops.all_bases) == 2
    assert saved


# ------------------------------------------------------------------ #
#  Интеграция в GUI                                                   #
# ------------------------------------------------------------------ #

def test_help_dialog_sections(qt_app):
    """Справка F1 содержит актуальные разделы и горячие клавиши."""
    from gui.dialogs.help_dialog import HelpDialog
    from PySide6.QtWidgets import QTextEdit

    dialog = HelpDialog()
    editors = dialog.findChildren(QTextEdit)
    html = editors[0].toHtml()

    assert "Публикация на Apache" in html
    assert "Снапшоты DBM API" in html
    assert "Ctrl+U" in html
    assert "Ctrl+F2" in html
    assert "F9" in html
    assert "Shift+F9" in html
    assert "Управление Apache" in html


def test_snapshots_update_mixin_registered_in_tree_window():
    from gui.tree_window import TreeWindow
    from gui.mixins import SnapshotsUpdateMixin

    assert SnapshotsUpdateMixin in TreeWindow.__mro__
    assert hasattr(TreeWindow, "open_snapshots_update")


def test_snapshots_update_dialog_imports(qt_app):
    from gui.dialogs.snapshots_update_dialog import SnapshotsUpdateDialog
    from PySide6.QtWidgets import QPushButton

    dialog = SnapshotsUpdateDialog(candidates=[], on_update_clicked=lambda b: "ok")
    texts = [b.text() for b in dialog.findChildren(QPushButton)]
    assert "Обновить все" in texts
    assert "Создать новый снапшот…" in texts


# ------------------------------------------------------------------ #
#  Кнопка «Обновить копию»: новый снапшот → connection string → F12   #
# ------------------------------------------------------------------ #

def _make_win():
    return SimpleNamespace(
        statusBar=SimpleNamespace(showMessage=lambda m: None),
        all_bases=[],
        operations=SimpleNamespace(
            create_copy_with_connect=lambda base, model, connect: None,
        ),
    )


def test_find_free_newer_connect(monkeypatch):
    """Есть свободный более новый снапшот — берём его connection string."""
    import gui.mixins.snapshots_update_mixin as m

    old = {"name": "snap_1", "expirationDate": "2026-08-10", "connectionString": "c1"}
    new = {"name": "snap_2", "expirationDate": "2026-08-15", "connectionString": 'Srvr="s";Ref="snap_2";'}
    taken = {"name": "snap_3", "expirationDate": "2026-08-20", "connectionString": 'Srvr="s";Ref="snap_3";'}
    monkeypatch.setattr(dbm, "get_db_snapshots", lambda t, db_id: [old, new, taken])

    mixin = m.SnapshotsUpdateMixin.__new__(m.SnapshotsUpdateMixin)
    # snap_3 занят базой — не предлагается
    result = mixin._find_free_newer_connect("tok", 39, "snap_1", {"snap_3"})
    assert result == 'Srvr="s";Ref="snap_2";'


def test_find_free_newer_connect_none(monkeypatch):
    """Нет более нового свободного снапшота — None."""
    import gui.mixins.snapshots_update_mixin as m

    old = {"name": "snap_1", "expirationDate": "2026-08-10", "connectionString": "c1"}
    monkeypatch.setattr(dbm, "get_db_snapshots", lambda t, db_id: [old])
    mixin = m.SnapshotsUpdateMixin.__new__(m.SnapshotsUpdateMixin)
    assert mixin._find_free_newer_connect("tok", 39, "snap_1", set()) is None


def test_find_newer_snapshot_connect():
    """Берёт самый новый снапшот с connection string, очищает \\", иначе ''."""
    old = {"name": "snap_1", "expirationDate": "2026-08-10", "connectionString": "c1"}
    new = {"name": "snap_2", "expirationDate": "2026-08-15",
           "connectionString": 'Srvr="s";Ref=\\"snap_2\\";'}
    assert dbm.find_newer_snapshot_connect([old, new], "snap_1") == 'Srvr="s";Ref="snap_2";'
    assert dbm.find_newer_snapshot_connect([old], "snap_1") == ""
    assert dbm.find_newer_snapshot_connect([], "snap_1") == ""


def test_task_info_from_status():
    assert dbm.task_info_from_status([{"state": "completed"}]) == {"state": "completed"}
    assert dbm.task_info_from_status({"state": "running"}) == {"state": "running"}
    assert dbm.task_info_from_status([]) == {}
    assert dbm.task_info_from_status("мусор") == {}
    assert "completed" in dbm.TASK_DONE_STATES
    assert "failed" in dbm.TASK_FAILED_STATES


def test_update_copy_flow_fast_path(monkeypatch):
    """Есть свободный более новый снапшот — применяется сразу (без мастера)."""
    import gui.mixins.snapshots_update_mixin as m
    from models.database import Database1C

    base = Database1C(id="a", folder="/", name="ЗУП ХРАН РАСШ",
                      connect='Srvr="s";Ref="snap_1";')
    win = _make_win()
    mixin = m.SnapshotsUpdateMixin.__new__(m.SnapshotsUpdateMixin)
    mixin.__dict__.update(win.__dict__)
    mixin.window = win
    mixin.all_bases = []

    monkeypatch.setattr(dbm, "get_valid_token", lambda: "tok")
    monkeypatch.setattr(mixin, "_snapshot_db_id", lambda t, ref: 39)
    monkeypatch.setattr(mixin, "_find_free_newer_connect",
                        lambda t, db_id, ref, used: 'Srvr="s";Ref="snap_2";')
    applied = []

    def fake_apply(base_, new_connect):
        applied.append(new_connect)
        return f"✅ {base_.name} → {new_connect}"

    monkeypatch.setattr(mixin, "_apply_snapshot_update", fake_apply)

    msg = mixin._update_copy_flow(base)
    assert msg.startswith("✅")
    assert applied == ['Srvr="s";Ref="snap_2";']


def test_remove_dated_from_recent(monkeypatch):
    """«Очистить Недавние»: убирает только датированные копии из «Недавних»."""
    import gui.actions.database_operations as ops_mod
    from gui.actions.database_operations import DatabaseOperations
    from models.database import Database1C

    recent_dated = Database1C(id="1", folder="/Недавние", name="ЗУП ТЕСТ 2026-07-30",
                              connect='Srvr="s";Ref="x";', is_recent=True,
                              original_folder="/Тест")
    recent_plain = Database1C(id="2", folder="/Недавние", name="ЗУП ТЕСТ",
                              connect='Srvr="s";Ref="y";', is_recent=True)
    not_recent = Database1C(id="3", folder="/Тест", name="ЗУП ТЕСТ 2026-08-05",
                            connect='Srvr="s";Ref="z";', is_recent=False)

    win = SimpleNamespace(statusBar=SimpleNamespace(showMessage=lambda m: None))
    ops = DatabaseOperations.__new__(DatabaseOperations)
    ops.window = win
    ops.all_bases = [recent_dated, recent_plain, not_recent]
    ops.save_callback = lambda: None
    ops.reload_callback = lambda: None
    monkeypatch.setattr(ops_mod.QMessageBox, "question",
                        lambda *a, **k: ops_mod.QMessageBox.Yes)

    ops.remove_dated_from_recent()

    assert recent_dated.is_recent is False
    assert recent_dated.folder == "/Тест"      # вернулась в исходную папку
    assert recent_dated.last_run_time is None
    assert recent_plain.is_recent is True      # без даты — не тронута
    assert not_recent.is_recent is False       # не из недавних — не тронута


def test_remove_dated_from_recent_empty(monkeypatch):
    """Нет датированных копий в «Недавних» — вопрос не задаётся, только статус."""
    import gui.actions.database_operations as ops_mod
    from gui.actions.database_operations import DatabaseOperations
    from models.database import Database1C

    recent_plain = Database1C(id="2", folder="/Недавние", name="ЗУП ТЕСТ",
                              connect='Srvr="s";Ref="y";', is_recent=True)
    win = SimpleNamespace(statusBar=SimpleNamespace(showMessage=lambda m: None))
    ops = DatabaseOperations.__new__(DatabaseOperations)
    ops.window = win
    ops.all_bases = [recent_plain]
    ops.save_callback = lambda: None
    ops.reload_callback = lambda: None
    asked = []
    monkeypatch.setattr(ops_mod.QMessageBox, "question",
                        lambda *a, **k: asked.append(1) or ops_mod.QMessageBox.Yes)

    ops.remove_dated_from_recent()

    assert asked == []
    assert recent_plain.is_recent is True


def test_remove_dated_from_recent_cancelled(monkeypatch):
    """Отмена — ничего не меняется."""
    import gui.actions.database_operations as ops_mod
    from gui.actions.database_operations import DatabaseOperations
    from models.database import Database1C

    recent_dated = Database1C(id="1", folder="/Недавние", name="ЗУП ТЕСТ 2026-07-30",
                              connect='Srvr="s";Ref="x";', is_recent=True,
                              original_folder="/Тест")
    win = SimpleNamespace(statusBar=SimpleNamespace(showMessage=lambda m: None))
    ops = DatabaseOperations.__new__(DatabaseOperations)
    ops.window = win
    ops.all_bases = [recent_dated]
    ops.save_callback = lambda: None
    ops.reload_callback = lambda: None
    monkeypatch.setattr(ops_mod.QMessageBox, "question",
                        lambda *a, **k: ops_mod.QMessageBox.No)

    ops.remove_dated_from_recent()

    assert recent_dated.is_recent is True


def test_downgrade_to_snapshot(monkeypatch):
    """Downgrade: строка подключения каскадной копии переносится в «<имя> <дата1>», копия удаляется."""
    import gui.actions.database_operations as ops_mod
    from gui.actions.database_operations import DatabaseOperations
    from models.database import Database1C

    fresh = Database1C(id="1", folder="/Недавние", name="ЗУП ХРАН РАСШ 2026-08-05 2026-08-05",
                       connect='Srvr="srv-1c-8325:1541";Ref="blank_database_0604_Pechericadv_6";')
    older = Database1C(id="2", folder="/Тест", name="ЗУП ХРАН РАСШ 2026-08-05",
                       connect='Srvr="srv-1c-8325:1541";Ref="old_snap";')
    other = Database1C(id="3", folder="/Тест", name="СОРВ ХРАН", connect='Srvr="s";Ref="x";')

    win = SimpleNamespace(statusBar=SimpleNamespace(showMessage=lambda m: None))
    ops = DatabaseOperations.__new__(DatabaseOperations)
    ops.window = win
    ops.all_bases = [fresh, older, other]
    ops.save_callback = lambda: None
    ops.reload_callback = lambda: None
    monkeypatch.setattr(ops_mod.QMessageBox, "question",
                        lambda *a, **k: ops_mod.QMessageBox.Yes)

    ops.downgrade_to_snapshot(fresh)

    assert older.connect == 'Srvr="srv-1c-8325:1541";Ref="blank_database_0604_Pechericadv_6";'
    assert fresh not in ops.all_bases
    assert other.connect == 'Srvr="s";Ref="x";'  # не тронута


def test_downgrade_to_snapshot_target_not_found(monkeypatch):
    """База «<имя> <дата1>» не найдена — ничего не делаем, только сообщение."""
    import gui.actions.database_operations as ops_mod
    from gui.actions.database_operations import DatabaseOperations
    from models.database import Database1C

    fresh = Database1C(id="1", folder="/Недавние", name="ЗУП ХРАН РАСШ 2026-08-05 2026-08-05",
                       connect='Srvr="s";Ref="new";')
    messages = []
    win = SimpleNamespace(statusBar=SimpleNamespace(showMessage=lambda m: messages.append(m)))
    ops = DatabaseOperations.__new__(DatabaseOperations)
    ops.window = win
    ops.all_bases = [fresh]
    ops.save_callback = lambda: None
    ops.reload_callback = lambda: None
    asked = []
    monkeypatch.setattr(ops_mod.QMessageBox, "question",
                        lambda *a, **k: asked.append(1) or ops_mod.QMessageBox.Yes)

    ops.downgrade_to_snapshot(fresh)

    assert asked == []  # подтверждение не запрашивалось
    assert fresh in ops.all_bases
    assert any("не найдена" in m for m in messages)


def test_downgrade_to_snapshot_no_date(monkeypatch):
    """В имени нет даты — откат невозможен, ничего не делаем."""
    import gui.actions.database_operations as ops_mod
    from gui.actions.database_operations import DatabaseOperations
    from models.database import Database1C

    base = Database1C(id="1", folder="/Тест", name="ЗУП ХРАН РАСШ",
                      connect='Srvr="s";Ref="x";')
    messages = []
    win = SimpleNamespace(statusBar=SimpleNamespace(showMessage=lambda m: messages.append(m)))
    ops = DatabaseOperations.__new__(DatabaseOperations)
    ops.window = win
    ops.all_bases = [base]
    ops.save_callback = lambda: None
    ops.reload_callback = lambda: None
    asked = []
    monkeypatch.setattr(ops_mod.QMessageBox, "question",
                        lambda *a, **k: asked.append(1) or ops_mod.QMessageBox.Yes)

    ops.downgrade_to_snapshot(base)

    assert asked == []
    assert base in ops.all_bases
    assert any("нет даты" in m for m in messages)


def test_downgrade_to_snapshot_cancelled(monkeypatch):
    """Отмена — ничего не меняется."""
    import gui.actions.database_operations as ops_mod
    from gui.actions.database_operations import DatabaseOperations
    from models.database import Database1C

    fresh = Database1C(id="1", folder="/Недавние", name="ЗУП ХРАН РАСШ 2026-08-05 2026-08-05",
                       connect='Srvr="s";Ref="new";')
    older = Database1C(id="2", folder="/Тест", name="ЗУП ХРАН РАСШ 2026-08-05",
                       connect='Srvr="s";Ref="old";')
    win = SimpleNamespace(statusBar=SimpleNamespace(showMessage=lambda m: None))
    ops = DatabaseOperations.__new__(DatabaseOperations)
    ops.window = win
    ops.all_bases = [fresh, older]
    ops.save_callback = lambda: None
    ops.reload_callback = lambda: None
    monkeypatch.setattr(ops_mod.QMessageBox, "question",
                        lambda *a, **k: ops_mod.QMessageBox.No)

    ops.downgrade_to_snapshot(fresh)

    assert older.connect == 'Srvr="s";Ref="old";'
    assert fresh in ops.all_bases


def test_apply_snapshot_update_dated_cascades_copy(monkeypatch):
    """Датированная копия тоже обновляется каскадно: к имени дописывается дата,
    состояние на старом снапшоте сохраняется (как F12)."""
    import gui.mixins.snapshots_update_mixin as m
    from models.database import Database1C

    base = Database1C(id="a", folder="/", name="ЗУП ТЕСТ 2026-07-30",
                      connect='Srvr="s";Ref="old";')
    created = []
    refreshed = []
    ops = SimpleNamespace(
        create_copy_with_connect=lambda db, model, c: (created.append((db.name, c)),
                                                       SimpleNamespace(name=db.name))[1],
        refresh_copy_connect=lambda db, c: refreshed.append(c),
    )
    mixin = m.SnapshotsUpdateMixin.__new__(m.SnapshotsUpdateMixin)
    mixin.operations = ops

    msg = mixin._apply_snapshot_update(base, 'Srvr="s";Ref="new";')

    # исходное имя (с датой) сохраняется на старой копии, новая создаётся под ним
    assert created == [("ЗУП ТЕСТ 2026-07-30", 'Srvr="s";Ref="new";')]
    assert refreshed == []
    assert "Создана копия" in msg


def test_apply_snapshot_update_fresh_creates_copy(monkeypatch):
    """База без даты — как F12: создаётся копия с датой, свежая получает connect."""
    import gui.mixins.snapshots_update_mixin as m
    from models.database import Database1C

    base = Database1C(id="a", folder="/", name="ЗУП ХРАН РАСШ",
                      connect='Srvr="s";Ref="old";')
    refreshed = []
    created = []
    ops = SimpleNamespace(
        refresh_copy_connect=lambda db, c: refreshed.append(c),
        create_copy_with_connect=lambda db, model, c: (created.append(c), SimpleNamespace(name="ЗУП ХРАН РАСШ"))[1],
    )
    mixin = m.SnapshotsUpdateMixin.__new__(m.SnapshotsUpdateMixin)
    mixin.operations = ops

    msg = mixin._apply_snapshot_update(base, 'Srvr="s";Ref="new";')

    assert created == ['Srvr="s";Ref="new";']
    assert refreshed == []
    assert "Создана копия" in msg


def test_update_copy_flow_creates_via_dbm_api(monkeypatch):
    """Свободного нет — мастер DBM API, затем ожидание задачи и применение (F12)."""
    import gui.mixins.snapshots_update_mixin as m
    from models.database import Database1C

    base = Database1C(id="a", folder="/", name="ЗУП ХРАН РАСШ",
                      connect='Srvr="srv-1c-8327:1541";Ref="snap_1";')
    win = _make_win()
    mixin = m.SnapshotsUpdateMixin.__new__(m.SnapshotsUpdateMixin)
    mixin.__dict__.update(win.__dict__)
    mixin.window = win
    mixin.all_bases = []

    monkeypatch.setattr(dbm, "get_valid_token", lambda: "tok")
    monkeypatch.setattr(mixin, "_snapshot_db_id", lambda t, ref: 39)
    monkeypatch.setattr(mixin, "_find_free_newer_connect", lambda t, db_id, ref, used: None)

    seen_kw = {}

    class FakeCreateDialog:
        def __init__(self, *a, **kw):
            seen_kw.update(kw)

        def exec(self):
            return 1  # QDialog.Accepted

        def task_result(self):
            return {"taskId": "task-42", "snapshot": None}

        def last_description(self):
            return "Создание копии snap_1 на srv"

    monkeypatch.setattr(m, "CreateSnapshotDialog", FakeCreateDialog)

    class FakeWaitDialog:
        def __init__(self, *a, **kw):
            seen_wait_kw.update(kw)

        def exec(self):
            return 1  # Accepted

        def connection_string(self):
            return 'Srvr="s";Ref="snap_2";'

    seen_wait_kw = {}
    monkeypatch.setattr(m, "SnapshotTaskWaitDialog", FakeWaitDialog)

    applied = []

    def fake_apply(base_, new_connect):
        applied.append(new_connect)
        return f"✅ {base_.name} → {new_connect}"

    monkeypatch.setattr(mixin, "_apply_snapshot_update", fake_apply)

    msg = mixin._update_copy_flow(base)
    assert msg.startswith("✅")
    assert applied == ['Srvr="s";Ref="snap_2";']
    # в мастер передаётся подсказка сервера из строки соединения базы
    assert seen_kw.get("prefill_server_hint") == "srv-1c-8327"
    # окно ожидания получает задачу и БД
    assert seen_wait_kw.get("task_id") == "task-42"
    assert seen_wait_kw.get("db_id") == 39


def test_update_copy_flow_connect_in_task_result(monkeypatch):
    """connection string уже в ответе создания — окно ожидания всё равно открывается,
    строка передаётся как запасная (initial_connect)."""
    import gui.mixins.snapshots_update_mixin as m
    from models.database import Database1C

    base = Database1C(id="a", folder="/", name="ЗУП ХРАН РАСШ",
                      connect='Srvr="s";Ref="snap_1";')
    win = _make_win()
    mixin = m.SnapshotsUpdateMixin.__new__(m.SnapshotsUpdateMixin)
    mixin.__dict__.update(win.__dict__)
    mixin.window = win
    mixin.all_bases = []

    monkeypatch.setattr(dbm, "get_valid_token", lambda: "tok")
    monkeypatch.setattr(mixin, "_snapshot_db_id", lambda t, ref: 39)
    monkeypatch.setattr(mixin, "_find_free_newer_connect", lambda t, db_id, ref, used: None)

    class FakeCreateDialog:
        def __init__(self, *a, **kw):
            pass

        def exec(self):
            return 1

        def task_result(self):
            return {"taskId": "task-1",
                    "snapshot": {"connectionString": 'Srvr="s";Ref=\\"snap_2\\";'}}

        def last_description(self):
            return "Создание копии snap_1 на srv"

    monkeypatch.setattr(m, "CreateSnapshotDialog", FakeCreateDialog)
    seen_kw = {}

    class FakeWaitDialog:
        def __init__(self, *a, **kw):
            seen_kw.update(kw)

        def exec(self):
            return 1

        def connection_string(self):
            return 'Srvr="s";Ref="snap_2";'

    monkeypatch.setattr(m, "SnapshotTaskWaitDialog", FakeWaitDialog)

    applied = []

    def fake_apply(base_, new_connect):
        applied.append(new_connect)
        return "✅ ok"

    monkeypatch.setattr(mixin, "_apply_snapshot_update", fake_apply)

    assert mixin._update_copy_flow(base) == "✅ ok"
    assert applied == ['Srvr="s";Ref="snap_2";']  # \\" очищены
    # окно ожидания открылось, запасная строка передана
    assert seen_kw.get("initial_connect") == 'Srvr="s";Ref="snap_2";'


def test_server_host_from_connect():
    """Парсинг хоста Srvr= из строки соединения."""
    from gui.mixins.snapshots_update_mixin import _server_host_from_connect

    assert _server_host_from_connect('Srvr="srv-1c-8327:1541";Ref="x";') == "srv-1c-8327"
    assert _server_host_from_connect('Srvr="10.128.64.252";Ref="x";') == "10.128.64.252"
    assert _server_host_from_connect("File=D:/1Cv8.1CD;") == ""


def test_create_dialog_prefill_server(qt_app, monkeypatch):
    """Мастер предвыбирает сервер, ближайший к строке соединения."""
    from gui.dialogs.create_snapshot_dialog import CreateSnapshotDialog

    servers = [
        {"id": 1, "name": "srv-1c-8323", "description": "сервер 8323"},
        {"id": 2, "name": "srv-1c-8327", "description": "сервер 8327"},
    ]
    dialog = CreateSnapshotDialog(
        token="tok",
        databases_loader=lambda: [{"id": 39, "name": "blank_database", "description": ""}],
        snapshots_loader=lambda db_id: [{"id": 1, "name": "snap_1", "expirationDate": "2026-08-10"}],
        servers_loader=lambda: servers,
        creator=lambda m, s, d: {"task": d},
        prefill_db_id=39, prefill_ref="snap_1",
        prefill_server_hint="srv-1c-8327",
    )
    selected = dialog.server_combo.currentData()
    assert selected and selected.get("id") == 2


def test_create_dialog_enter_creates_if_valid(qt_app, monkeypatch):
    """Enter в описании: создаёт, если мастер и сервер выбраны; иначе — ничего."""
    from gui.dialogs.create_snapshot_dialog import CreateSnapshotDialog

    dialog = CreateSnapshotDialog(
        token="tok",
        databases_loader=lambda: [{"id": 39, "name": "d", "description": ""}],
        snapshots_loader=lambda db_id: [{"id": 1, "name": "snap_1", "expirationDate": "2026-08-10"}],
        servers_loader=lambda: [{"id": 2, "name": "srv-1c-8327", "description": ""}],
        creator=lambda m, s, d: {"task": d},
    )
    calls = []
    monkeypatch.setattr(dialog, "_create", lambda: calls.append(1))

    dialog._create_from_enter()  # всё выбрано → создаёт
    assert calls == [1]

    dialog.snap_combo.setCurrentIndex(-1)  # мастер не выбран
    dialog._create_from_enter()  # ничего не происходит
    assert calls == [1]


def test_snapshots_update_dialog_enter_on_row(qt_app, monkeypatch):
    """Enter на обновляемой строке запускает обновление; на необновляемой — ничего."""
    from gui.dialogs.snapshots_update_dialog import SnapshotsUpdateDialog
    from PySide6.QtGui import QKeyEvent
    from PySide6.QtCore import QEvent, Qt
    from models.database import Database1C

    rows = [
        {"base": Database1C(id="a", folder="/", name="ЗУП ХРАН РАСШ",
                            connect='Srvr="s";Ref="old";'),
         "snapshot_name": "old", "snapshot_exp": None,
         "blue": True, "updatable": True, "dated": False,
         "new_name": "new", "new_connect": 'Srvr="s";Ref="new";', "new_expiration": None},
        {"base": Database1C(id="b", folder="/", name="СОРВ ХРАН",
                            connect='Srvr="s";Ref="new";'),
         "snapshot_name": "new", "snapshot_exp": None,
         "blue": False, "updatable": False, "dated": False,
         "new_name": None, "new_connect": None, "new_expiration": None},
    ]
    dialog = SnapshotsUpdateDialog(candidates=rows, on_update_clicked=lambda b: "ok")
    updates = []
    monkeypatch.setattr(dialog, "_update_row", lambda row: updates.append(row))

    dialog.table.setCurrentCell(0, 0)  # обновляемая строка
    dialog.keyPressEvent(QKeyEvent(QEvent.Type.KeyPress, Qt.Key_Return, Qt.KeyboardModifier.NoModifier))
    assert updates == [0]

    dialog.table.setCurrentCell(1, 0)  # необновляемая — ничего
    dialog.keyPressEvent(QKeyEvent(QEvent.Type.KeyPress, Qt.Key_Return, Qt.KeyboardModifier.NoModifier))
    assert updates == [0]


def test_snapshots_update_dialog_statusbar_object(qt_app, monkeypatch):
    """Регрессия: parent.statusBar — объект QStatusBar (не метод), showMessage работает."""
    import gui.dialogs.snapshots_update_dialog as dlg
    from gui.dialogs.snapshots_update_dialog import SnapshotsUpdateDialog
    from PySide6.QtWidgets import QWidget
    from models.database import Database1C

    parent = QWidget()
    messages = []
    parent.statusBar = SimpleNamespace(showMessage=lambda m: messages.append(m))
    infos = []
    monkeypatch.setattr(dlg.QMessageBox, "information",
                        lambda *a, **k: infos.append(a[2]))
    rows = [
        {"base": Database1C(id="a", folder="/", name="ЗУП ХРАН РАСШ",
                            connect='Srvr="s";Ref="old";'),
         "snapshot_name": "old", "snapshot_exp": None,
         "blue": True, "updatable": True, "dated": False,
         "new_name": "new", "new_connect": 'Srvr="s";Ref="new";', "new_expiration": None},
    ]
    dialog = SnapshotsUpdateDialog(parent=parent, candidates=rows,
                                   on_update_clicked=lambda b: "✅ готово")

    assert dialog._update_row(0) is True
    assert messages == ["✅ готово"]
    # после успеха показывается info-окно с результатом
    assert infos == ["✅ готово"]


# ------------------------------------------------------------------ #
#  Окно ожидания задачи создания снапшота (как DBM API)               #
# ------------------------------------------------------------------ #

def test_task_wait_dialog_completed_fetches_connect(qt_app, monkeypatch):
    """Статус completed → progress 100%, «Готово!», запрашивается connection string."""
    from gui.dialogs.snapshot_task_wait_dialog import SnapshotTaskWaitDialog

    dialog = SnapshotTaskWaitDialog(
        token="tok", task_id="t1", db_id=39, base_ref="snap_1",
        description="Создание копии snap_1 на srv",
        task_status_fetcher=lambda t, tid: {"state": "running"},
        snapshots_fetcher=lambda t, db: [],
        poll_interval_ms=10**9,  # таймер не мешает тесту
    )
    fetched = []
    monkeypatch.setattr(dialog, "_fetch_connection_string",
                        lambda: fetched.append(1))

    dialog._on_status(("ok", {"state": "completed"}))

    assert fetched == [1]
    assert dialog.progress.value() == 100
    assert "Готово!" in dialog.status_label.text()
    assert "snap_1" in dialog.info_label.text()  # описание показано


def test_task_wait_dialog_live_log(qt_app):
    """Лог задачи выводится в log_view (живой лог, как DBM API)."""
    from gui.dialogs.snapshot_task_wait_dialog import SnapshotTaskWaitDialog

    dialog = SnapshotTaskWaitDialog(
        token="tok", task_id="t1", db_id=39, base_ref="snap_1",
        task_status_fetcher=lambda t, tid: {"state": "running"},
        snapshots_fetcher=lambda t, db: [],
        poll_interval_ms=10**9,
    )

    dialog._on_status(("ok", {"state": "running", "log": ["шаг 1", "шаг 2"]}))

    text = dialog.log_view.toPlainText()
    assert "шаг 1" in text and "шаг 2" in text


def test_task_wait_dialog_params_table(qt_app):
    """Task ID виден в таблице параметров."""
    from gui.dialogs.snapshot_task_wait_dialog import SnapshotTaskWaitDialog

    dialog = SnapshotTaskWaitDialog(
        token="tok", task_id="task-777", db_id=39, base_ref="snap_1",
        task_status_fetcher=lambda t, tid: {"state": "running"},
        snapshots_fetcher=lambda t, db: [],
        poll_interval_ms=10**9,
    )
    assert dialog.params_table.item(0, 0).text() == "Task ID"
    assert dialog.params_table.item(0, 1).text() == "task-777"


def test_task_wait_dialog_failed_state(qt_app, monkeypatch):
    """Статус failed → сообщение об ошибке и закрытие с Rejected."""
    import gui.dialogs.snapshot_task_wait_dialog as w
    from gui.dialogs.snapshot_task_wait_dialog import SnapshotTaskWaitDialog

    dialog = SnapshotTaskWaitDialog(
        token="tok", task_id="t1", db_id=39, base_ref="snap_1",
        task_status_fetcher=lambda t, tid: {"state": "running"},
        snapshots_fetcher=lambda t, db: [],
        poll_interval_ms=10**9,
    )
    monkeypatch.setattr(w.QMessageBox, "critical", lambda *a, **k: None)
    rejected = []
    monkeypatch.setattr(dialog, "reject", lambda: rejected.append(1))

    dialog._on_status(("ok", {"state": "failed", "message": "boom"}))

    assert dialog._state == "failed"
    assert rejected == [1]


def test_task_wait_dialog_snapshots_connect(qt_app, monkeypatch):
    """После завершения задачи находится connection string нового снапшота."""
    import gui.dialogs.snapshot_task_wait_dialog as w
    from gui.dialogs.snapshot_task_wait_dialog import SnapshotTaskWaitDialog

    old = {"name": "snap_1", "expirationDate": "2026-08-10", "connectionString": "c1"}
    new = {"name": "snap_2", "expirationDate": "2026-08-15",
           "connectionString": 'Srvr="s";Ref="snap_2";'}
    dialog = SnapshotTaskWaitDialog(
        token="tok", task_id="t1", db_id=39, base_ref="snap_1",
        task_status_fetcher=lambda t, tid: {"state": "running"},
        snapshots_fetcher=lambda t, db: [old, new],
        poll_interval_ms=10**9,
    )
    accepted = []
    monkeypatch.setattr(dialog, "accept", lambda: accepted.append(1))

    dialog._on_snapshots(("ok", [old, new]))

    assert accepted == [1]
    assert dialog.connection_string() == 'Srvr="s";Ref="snap_2";'


def test_task_wait_dialog_initial_connect_fallback(qt_app, monkeypatch):
    """Новый снапшот ещё не виден в списке — используется строка из ответа создания."""
    import gui.dialogs.snapshot_task_wait_dialog as w
    from gui.dialogs.snapshot_task_wait_dialog import SnapshotTaskWaitDialog

    old = {"name": "snap_1", "expirationDate": "2026-08-10", "connectionString": "c1"}
    dialog = SnapshotTaskWaitDialog(
        token="tok", task_id="t1", db_id=39, base_ref="snap_1",
        initial_connect='Srvr="s";Ref="snap_2";',
        task_status_fetcher=lambda t, tid: {"state": "running"},
        snapshots_fetcher=lambda t, db: [old],
        poll_interval_ms=10**9,
    )
    accepted = []
    monkeypatch.setattr(dialog, "accept", lambda: accepted.append(1))

    dialog._on_snapshots(("ok", [old]))  # нового снапшота в списке ещё нет

    assert accepted == [1]
    assert dialog.connection_string() == 'Srvr="s";Ref="snap_2";'


def test_snapshots_update_dialog_row_button(qt_app):
    """Кнопка «Обновить копию» — только у обновляемой строки, у остальных пусто."""
    from gui.dialogs.snapshots_update_dialog import SnapshotsUpdateDialog
    from models.database import Database1C

    old_connect = 'Srvr="s";Ref="old_snap";'
    rows = [
        {"base": Database1C(id="a", folder="/", name="ЗУП ХРАН РАСШ", connect=old_connect),
         "snapshot_name": "old_snap", "snapshot_exp": None,
         "blue": True, "updatable": True, "dated": False,
         "new_name": "new_snap", "new_connect": 'Srvr="s";Ref="new_snap";',
         "new_expiration": None},
        {"base": Database1C(id="b", folder="/", name="СОРВ ХРАН", connect='Srvr="s";Ref="new_snap";'),
         "snapshot_name": "new_snap", "snapshot_exp": None,
         "blue": False, "updatable": False, "dated": False,
         "new_name": "new_snap", "new_connect": None, "new_expiration": None},
    ]
    dialog = SnapshotsUpdateDialog(candidates=rows, on_update_clicked=lambda b: "ok")

    button_upd = dialog.table.cellWidget(0, 5)
    assert button_upd is not None and button_upd.text() == "Обновить копию"
    assert button_upd.isEnabled()
    assert dialog.table.cellWidget(1, 5) is None  # необновляемая — без кнопки
    # колонка «Строка соединения» показывает текущий connect базы
    assert dialog.table.item(0, 2).text() == old_connect


def test_snapshots_update_dialog_hide_dated_checkbox(qt_app):
    """Чекбокс «Скрыть копии с датой» по умолчанию включён и фильтрует строки."""
    from gui.dialogs.snapshots_update_dialog import SnapshotsUpdateDialog
    from models.database import Database1C

    def row(name, blue, dated):
        return {"base": Database1C(id=name, folder="/", name=name, connect='Srvr="s";Ref="x";'),
                "snapshot_name": "x", "snapshot_exp": None,
                "blue": blue, "updatable": blue and not dated, "dated": dated,
                "new_name": "new" if blue else None,
                "new_connect": 'Srvr="s";Ref="new";' if blue else None, "new_expiration": None}

    rows = [row("ЗУП ХРАН РАСШ", True, False),
            row("ЗУП ХРАН 2026-08-05", True, True),
            row("СОРВ ХРАН", False, False)]
    dialog = SnapshotsUpdateDialog(candidates=rows, on_update_clicked=lambda b: "ok")

    names = [dialog.table.item(r, 0).text() for r in range(dialog.table.rowCount())]
    assert names == ["ЗУП ХРАН РАСШ", "СОРВ ХРАН"]  # датированная скрыта по умолчанию

    dialog.hide_dated_check.setChecked(False)
    names = [dialog.table.item(r, 0).text() for r in range(dialog.table.rowCount())]
    assert names == ["ЗУП ХРАН РАСШ", "ЗУП ХРАН 2026-08-05", "СОРВ ХРАН"]


def test_snapshots_update_dialog_dated_has_button(qt_app):
    """Датированная копия на голубом снапшоте — при снятом фильтре видна и с кнопкой."""
    from gui.dialogs.snapshots_update_dialog import SnapshotsUpdateDialog
    from models.database import Database1C

    rows = [
        {"base": Database1C(id="a", folder="/", name="ЗУП ТЕСТ 2026-07-30",
                            connect='Srvr="s";Ref="old";'),
         "snapshot_name": "old", "snapshot_exp": None,
         "blue": True, "updatable": True, "dated": True,  # голубой и датирован — тоже обновляема
         "new_name": "new_snap", "new_connect": 'Srvr="s";Ref="new";', "new_expiration": None},
    ]
    dialog = SnapshotsUpdateDialog(candidates=rows, on_update_clicked=lambda b: "ok")

    assert dialog.table.rowCount() == 0  # по умолчанию датированные скрыты

    dialog.hide_dated_check.setChecked(False)  # показать датированную копию
    assert dialog.table.rowCount() == 1
    button = dialog.table.cellWidget(0, 5)
    assert button is not None and button.text() == "Обновить копию"
    assert button.isEnabled()
