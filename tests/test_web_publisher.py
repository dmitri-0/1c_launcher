"""Тесты модуля публикации базы на Apache (services.web_publisher).

Не использует сеть и не запускает реальный webinst.exe — subprocess и
urllib замоканы; файловая система — через tmp_path.
"""

import json
import os
import re
import urllib.error
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

import services.web_publisher as wp
from services.web_publisher import WebPublisher, PublishError


# ------------------------------------------------------------------ #
#  Вспомогательное                                                    #
# ------------------------------------------------------------------ #

def make_db(**overrides):
    """Фейковая база (duck typing: connect, name, version, app_arch)."""
    data = dict(
        name="ЗУП",
        connect='Srvr="srv-1c-8325:1541";Ref="ZUP_0730_Pechericadv_3";',
        version="8.3.25.1394",
        app_arch="x86_64",
        publish_name=None,
        publish_dir=None,
    )
    data.update(overrides)
    return SimpleNamespace(**data)


def make_publisher(tmp_path, instances=None):
    """Публикатор с JSON-конфигом во временной папке (детерминированно).

    Инстансы по умолчанию лежат под tmp_path, чтобы build_command не создавал
    каталоги в реальном C:\\Apache24 во время тестов.
    """
    cfg = tmp_path / "web_publish.json"
    if instances is None:
        instances = [
            {"name": "apache-80", "apache_root": str(tmp_path / "Apache24"), "port": 80, "versions": ["8.3.25.1394"]},
            {"name": "apache24-8327", "apache_root": str(tmp_path / "Apache24-8327"), "port": 81, "versions": ["8.3.27.1688"]},
        ]
    cfg.write_text(json.dumps({"apache_instances": instances}), encoding="utf-8")
    return WebPublisher(config_path=cfg)


def fake_pe(path, bits):
    """Минимальный валидный PE-заголовок указанной разрядности."""
    e_lfanew = 0x80
    machine = 0x8664 if bits == 64 else 0x14C
    buf = bytearray(e_lfanew + 24)
    buf[0:2] = b"MZ"
    buf[0x3C:0x40] = e_lfanew.to_bytes(4, "little")
    buf[e_lfanew:e_lfanew + 4] = b"PE\x00\x00"
    buf[e_lfanew + 4:e_lfanew + 6] = machine.to_bytes(2, "little")
    path.write_bytes(bytes(buf))


def fake_platform_install(tmp_path, version="8.3.25.1394", arch="x86_64"):
    """Создаёт временный каталог установки платформы (webinst + wsap24)."""
    if arch == "x86_64":
        root = tmp_path / "PF64"
        bits = 64
    else:
        root = tmp_path / "PF32"
        bits = 32
    bin_dir = root / version / "bin"
    bin_dir.mkdir(parents=True)
    exe = bin_dir / "webinst.exe"
    exe.write_bytes(b"fake")
    fake_pe(bin_dir / "wsap24.dll", bits)
    wp.PROGRAM_FILES_64 = tmp_path / "PF64"
    wp.PROGRAM_FILES_32 = tmp_path / "PF32"
    return exe


def fake_run(monkeypatch, returncode=0, stdout=b"", stderr=b""):
    monkeypatch.setattr(
        wp.subprocess,
        "run",
        lambda *a, **k: SimpleNamespace(returncode=returncode, stdout=stdout, stderr=stderr),
    )


# ------------------------------------------------------------------ #
#  Выбор экземпляра Apache по версии платформы (регресс ошибки 409)  #
# ------------------------------------------------------------------ #

def test_instances_split_by_platform_version(tmp_path):
    """Две базы разных версий должны уходить в РАЗНЫЕ экземпляры Apache."""
    publisher = make_publisher(tmp_path)

    inst_zup = publisher.select_instance("8.3.25.1394")
    inst_astor = publisher.select_instance("8.3.27.1688")

    assert inst_zup.name == "apache-80"
    assert inst_astor.name == "apache24-8327"
    assert inst_zup.port != inst_astor.port
    # ключевое: разные конфиги httpd.conf, значит и разные wsap24.dll
    assert inst_zup.conf_path != inst_astor.conf_path


def test_config_missing_uses_defaults(tmp_path):
    """Без конфига — один универсальный инстанс (C:\\Apache24, любой версии)."""
    publisher = WebPublisher(config_path=tmp_path / "missing.json")
    assert [i.name for i in publisher.apache_instances] == ["apache"]
    assert publisher.select_instance("8.3.27.1688").name == "apache"


def test_user_config_overrides_defaults(tmp_path):
    """Машинная конфигурация (несколько версий) живёт в JSON, а не в коде."""
    cfg = tmp_path / "web_publish.json"
    cfg.write_text(json.dumps({"apache_instances": [
        {"name": "apache-80", "apache_root": "C:/Apache24", "port": 80, "versions": ["8.3.25.1394"]},
        {"name": "apache24-8327", "apache_root": "C:/Apache24-8327", "port": 81, "versions": ["8.3.27.1688"]},
    ]}), encoding="utf-8")
    publisher = WebPublisher(config_path=cfg)
    assert publisher.select_instance("8.3.27.1688").name == "apache24-8327"
    assert publisher.select_instance("8.3.25.1394").name == "apache-80"


def test_select_instance_prefix_match(tmp_path):
    publisher = make_publisher(tmp_path, instances=[
        {"name": "a", "apache_root": "C:/A", "port": 80, "versions": ["8.3.25"]},
    ])
    assert publisher.select_instance("8.3.25.1394").name == "a"


def test_select_instance_unknown_version_raises(tmp_path):
    publisher = make_publisher(tmp_path)
    with pytest.raises(PublishError, match="не найден экземпляр Apache"):
        publisher.select_instance("8.3.30.1234")


def test_select_instance_without_version_raises(tmp_path):
    publisher = make_publisher(tmp_path)
    with pytest.raises(PublishError, match="не указана версия"):
        publisher.select_instance(None)


# ------------------------------------------------------------------ #
#  Поиск webinst.exe                                                  #
# ------------------------------------------------------------------ #

def test_find_webinst_x64_first(tmp_path):
    exe64 = fake_platform_install(tmp_path, arch="x86_64")
    result = WebPublisher(config_path=tmp_path / "none.json").find_webinst("8.3.25.1394", "x86_64")
    assert result == str(exe64)


def test_find_webinst_x86_first(tmp_path):
    exe32 = fake_platform_install(tmp_path, version="8.3.27.1688", arch="x86")
    result = WebPublisher(config_path=tmp_path / "none.json").find_webinst("8.3.27.1688", "x86")
    assert result == str(exe32)


def test_find_webinst_missing_returns_none(tmp_path):
    fake_platform_install(tmp_path)
    result = WebPublisher(config_path=tmp_path / "none.json").find_webinst("8.3.99.9999", "x86_64")
    assert result is None


# ------------------------------------------------------------------ #
#  Разрядность Apache и платформы (PE-заголовки)                      #
# ------------------------------------------------------------------ #

def test_detect_pe_bits(tmp_path):
    f64 = tmp_path / "x64.bin"
    fake_pe(f64, 64)
    f32 = tmp_path / "x86.bin"
    fake_pe(f32, 32)
    junk = tmp_path / "junk.bin"
    junk.write_bytes(b"not a pe")
    assert wp.detect_pe_bits(f64) == 64
    assert wp.detect_pe_bits(f32) == 32
    assert wp.detect_pe_bits(junk) is None
    assert wp.detect_pe_bits(tmp_path / "missing.bin") is None


def test_get_apache_bits_from_httpd(tmp_path):
    root = tmp_path / "Apache24"
    (root / "bin").mkdir(parents=True)
    fake_pe(root / "bin" / "httpd.exe", 64)
    publisher = WebPublisher(config_path=tmp_path / "none.json")
    assert publisher.get_apache_bits(wp.ApacheInstance(name="t", apache_root=root)) == 64


def test_get_apache_bits_fallback_to_config(tmp_path):
    publisher = WebPublisher(config_path=tmp_path / "none.json")
    instance = wp.ApacheInstance(name="t", apache_root=tmp_path / "no", apache_bits=32)
    assert publisher.get_apache_bits(instance) == 32


def test_select_webinst_prefers_apache_bits_over_base_arch(tmp_path):
    """База настроена как x86, но Apache 64-битный — берём 64-битную установку."""
    install = tmp_path / "PF"
    for root_name, bits in (("PF64", 64), ("PF32", 32)):
        bin_dir = install / root_name / "8.3.27.1688" / "bin"
        bin_dir.mkdir(parents=True)
        (bin_dir / "webinst.exe").write_bytes(b"fake")
        fake_pe(bin_dir / "wsap24.dll", bits)
    wp.PROGRAM_FILES_64 = install / "PF64"
    wp.PROGRAM_FILES_32 = install / "PF32"
    publisher = WebPublisher(config_path=tmp_path / "none.json")

    result = publisher.select_webinst("8.3.27.1688", "x86", 64)

    assert result.startswith(str(wp.PROGRAM_FILES_64))


def test_select_webinst_mismatch_raises(tmp_path):
    """Только 32-битная установка при 64-битном Apache -> понятная ошибка."""
    bin32 = tmp_path / "PF" / "PF32" / "8.3.27.1688" / "bin"
    bin32.mkdir(parents=True)
    (bin32 / "webinst.exe").write_bytes(b"fake")
    fake_pe(bin32 / "wsap24.dll", 32)
    wp.PROGRAM_FILES_64 = tmp_path / "PF" / "PF64"
    wp.PROGRAM_FILES_32 = tmp_path / "PF" / "PF32"
    publisher = WebPublisher(config_path=tmp_path / "none.json")

    with pytest.raises(PublishError, match="Разрядность не совпадает"):
        publisher.select_webinst("8.3.27.1688", "x86", 64)


# ------------------------------------------------------------------ #
#  Параметры команды                                                  #
# ------------------------------------------------------------------ #

def test_build_connstr_passes_connect_as_is():
    assert WebPublisher.build_connstr(make_db()) == 'Srvr="srv-1c-8325:1541";Ref="ZUP_0730_Pechericadv_3";'
    assert WebPublisher.build_connstr(make_db(connect='File="D:\\Bases\\OldBase";')) == 'File="D:\\Bases\\OldBase";'


def test_build_wsdir_from_name_sanitized():
    # Кириллическое имя не годится для wsdir — берётся Ref из Connect
    assert WebPublisher.build_wsdir(make_db(name="ЗУП 0730 Печерица")) == "ZUP_0730_Pechericadv_3"


def test_build_wsdir_latin_name_kept():
    assert WebPublisher.build_wsdir(make_db(name="Shop Base", connect="")) == "Shop_Base"


def test_build_wsdir_from_ref_when_name_empty():
    assert WebPublisher.build_wsdir(make_db(name="", connect='Srvr="s";Ref="ZUP_test";')) == "ZUP_test"


def test_build_wsdir_explicit_override():
    assert WebPublisher.build_wsdir(make_db(name="ЗУП"), "oldbase") == "oldbase"


def test_build_wsdir_from_publish_name():
    """Поле базы PublishName используется, если имя кириллическое."""
    assert WebPublisher.build_wsdir(make_db(name="ЗУП", publish_name="shop")) == "shop"


def test_build_command_publish_server_base(tmp_path, monkeypatch):
    exe = fake_platform_install(tmp_path)
    publisher = make_publisher(tmp_path)
    db = make_db()

    args = publisher.build_command(db)

    assert args[0] == str(exe)
    assert args[1] == "-publish"
    assert args[2] == "-apache24"
    assert args[3] == "-wsdir"
    assert args[5] == "-dir"
    assert args[6] == str(tmp_path / "Apache24" / "htdocs" / "ZUP_0730_Pechericadv_3")
    assert args[7] == "-connstr"
    assert args[8] == db.connect
    assert args[9] == "-confpath"
    assert args[10] == str(tmp_path / "Apache24" / "conf" / "httpd.conf")


def test_build_command_uses_publish_dir_and_name(tmp_path):
    """PublishName -> wsdir, PublishDir -> -dir из настроек базы (Ctrl+E)."""
    fake_platform_install(tmp_path, version="8.3.27.1688")
    publisher = make_publisher(tmp_path)
    pub_dir = tmp_path / "1CWEB" / "shop"
    db = make_db(name="АСТОР", version="8.3.27.1688", publish_name="shop", publish_dir=str(pub_dir))

    args = publisher.build_command(db)

    assert args[4] == "shop"
    assert args[6] == str(pub_dir)
    assert pub_dir.exists()  # каталог публикации создан


def test_build_command_unpublish_omits_dir_and_connstr(tmp_path):
    fake_platform_install(tmp_path)
    publisher = make_publisher(tmp_path)
    args = publisher.build_command(make_db(), unpublish=True)
    assert "-unpublish" in args
    assert "-dir" not in args
    assert "-connstr" not in args
    assert "-wsdir" in args


def test_build_command_unknown_version_raises(tmp_path):
    fake_platform_install(tmp_path)
    publisher = make_publisher(tmp_path)
    with pytest.raises(PublishError, match="не найден экземпляр Apache"):
        publisher.build_command(make_db(version="8.3.99.9999"))


def test_build_command_empty_connect_raises(tmp_path):
    fake_platform_install(tmp_path)
    publisher = make_publisher(tmp_path)
    with pytest.raises(PublishError, match="пустая строка подключения"):
        publisher.build_command(make_db(connect=""))


def test_build_publication_url(tmp_path):
    publisher = make_publisher(tmp_path)
    assert publisher.build_publication_url(make_db(version="8.3.27.1688")) == "http://127.0.0.1:81/ZUP_0730_Pechericadv_3"
    assert publisher.build_publication_url(make_db(version="8.3.25.1394")) == "http://127.0.0.1/ZUP_0730_Pechericadv_3"


# ------------------------------------------------------------------ #
#  Запуск webinst.exe (subprocess замокан)                            #
# ------------------------------------------------------------------ #

def test_run_success(tmp_path, monkeypatch):
    fake_platform_install(tmp_path)
    fake_run(monkeypatch, returncode=0, stdout="Опубликовано успешно".encode("cp866"))
    publisher = make_publisher(tmp_path)

    result = publisher.publish(make_db())

    assert result.ok
    assert result.stdout == "Опубликовано успешно"
    assert result.publication_url == "http://127.0.0.1/ZUP_0730_Pechericadv_3"
    assert result.command[1] == "-publish"


def test_run_failure_returncode(tmp_path, monkeypatch):
    fake_platform_install(tmp_path)
    fake_run(monkeypatch, returncode=1, stderr="Ошибка".encode("cp866"))
    publisher = make_publisher(tmp_path)

    result = publisher.publish(make_db())

    assert not result.ok
    assert result.returncode == 1
    assert result.stderr == "Ошибка"


def test_run_timeout_raises(tmp_path, monkeypatch):
    fake_platform_install(tmp_path)

    def timeout(*a, **k):
        raise wp.subprocess.TimeoutExpired("webinst.exe", 120)

    monkeypatch.setattr(wp.subprocess, "run", timeout)
    publisher = make_publisher(tmp_path)

    with pytest.raises(PublishError, match="не завершился"):
        publisher.publish(make_db())


def test_unpublish_uses_unpublish_flag(tmp_path, monkeypatch):
    fake_platform_install(tmp_path)
    fake_run(monkeypatch)
    publisher = make_publisher(tmp_path)

    result = publisher.unpublish(make_db())

    assert result.ok
    assert result.command[1] == "-unpublish"
    assert result.publication_url is None




# ------------------------------------------------------------------ #
#  Конфиг                                                             #
# ------------------------------------------------------------------ #

def test_config_invalid_json_raises(tmp_path):
    cfg = tmp_path / "web_publish.json"
    cfg.write_text("{broken", encoding="utf-8")
    with pytest.raises(PublishError, match="конфиг публикации"):
        WebPublisher(config_path=cfg)


def test_config_custom_instance_loaded(tmp_path):
    cfg = tmp_path / "web_publish.json"
    cfg.write_text(json.dumps({
        "apache_instances": [{"name": "my-apache", "apache_root": "D:/Apache", "port": 8080}],
        "default_host": "localhost",
    }), encoding="utf-8")
    publisher = WebPublisher(config_path=cfg)
    assert publisher.apache_instances[0].port == 8080
    assert publisher.apache_instances[0].conf_path == Path("D:/Apache/conf/httpd.conf")
    assert publisher.select_instance("8.3.25.1394").name == "my-apache"  # versions пусто = любые


# ------------------------------------------------------------------ #
#  Проверка публикации (urllib замокан, сеть не используется)          #
# ------------------------------------------------------------------ #

def test_verify_publication_http_ok(monkeypatch):
    class FakeResp:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(wp.urllib.request, "urlopen", lambda *a, **k: FakeResp())
    assert wp.verify_publication("http://127.0.0.1/zup") is True


def test_verify_publication_http_401_is_alive(monkeypatch):
    def forbidden(*a, **k):
        raise urllib.error.HTTPError("http://x", 401, "Unauthorized", None, None)

    monkeypatch.setattr(wp.urllib.request, "urlopen", forbidden)
    assert wp.verify_publication("http://127.0.0.1/zup") is True


def test_verify_publication_network_error(monkeypatch):
    def down(*a, **k):
        raise urllib.error.URLError("connection refused")

    monkeypatch.setattr(wp.urllib.request, "urlopen", down)
    assert wp.verify_publication("http://127.0.0.1/zup") is False


# ------------------------------------------------------------------ #
#  Авто-копирование и настройка экземпляра Apache                     #
# ------------------------------------------------------------------ #

@pytest.fixture
def template_apache(tmp_path):
    """Шаблон Apache с httpd.conf как на реальной машине (полный путь)."""
    root = tmp_path / "Apache24"
    conf = root / "conf"
    conf.mkdir(parents=True)
    (root / "htdocs").mkdir()
    (root / "bin").mkdir()
    root_fwd = str(root).replace("\\", "/")
    (conf / "httpd.conf").write_text(
        f'Define SRVROOT "{root_fwd}"\n'
        "ServerRoot \"${SRVROOT}\"\n"
        "Listen 80\n"
        'LoadModule _1cws_module "C:/Program Files/1cv8/8.3.25.1394/bin/wsap24.dll"\n',
        encoding="cp1251",
    )
    (root / "bin" / "httpd.exe").write_bytes(b"httpd")
    return root


def test_ensure_instance_ready_clones_and_fixes_config(tmp_path, template_apache):
    publisher = make_publisher(tmp_path, instances=[
        {"name": "apache-80", "apache_root": str(template_apache), "port": 80, "versions": ["8.3.25.1394"]},
        {"name": "apache24-8327", "apache_root": str(tmp_path / "Apache24-8327"), "port": 81, "versions": ["8.3.27.1688"]},
    ])
    target = publisher.select_instance("8.3.27.1688")
    target_fwd = str(target.apache_root).replace("\\", "/")

    assert not target.conf_path.exists()
    assert publisher.ensure_instance_ready(target) is True

    text = target.conf_path.read_text(encoding="cp1251")
    assert f'Define SRVROOT "{target_fwd}"' in text
    assert "Listen 81" in text
    assert "Listen 80" not in text
    # старая версия модуля закомментирована, webinst допишет свою
    assert re.search(r"^\s*LoadModule\s+_1cws_module", text, re.MULTILINE) is None
    assert "# LoadModule _1cws_module" in text
    assert "8.3.25.1394/bin/wsap24.dll" not in text
    assert target.htdocs_root.exists()
    assert (target.apache_root / "logs").exists()  # каталог логов обязателен для Apache
    # шаблон не тронут
    assert 'Listen 80' in template_apache.joinpath("conf/httpd.conf").read_text(encoding="cp1251")


def test_ensure_instance_ready_already_configured(tmp_path, template_apache):
    publisher = make_publisher(tmp_path, instances=[
        {"name": "apache-80", "apache_root": str(template_apache), "port": 80, "versions": ["8.3.25.1394"]},
    ])
    instance = publisher.select_instance("8.3.25.1394")
    assert publisher.ensure_instance_ready(instance) is True
    # конфиг не менялся
    assert 'Listen 80' in instance.conf_path.read_text(encoding="cp1251")


def test_ensure_instance_ready_no_template_raises(tmp_path):
    publisher = make_publisher(tmp_path, instances=[
        {"name": "solo", "apache_root": str(tmp_path / "Missing"), "port": 80, "versions": ["8.3.25.1394"]},
    ])
    instance = publisher.select_instance("8.3.25.1394")
    with pytest.raises(PublishError, match="не найден шаблон"):
        publisher.ensure_instance_ready(instance)


def test_restart_apache_service_mode(tmp_path, template_apache, monkeypatch):
    """Если служба установлена — перезапуск через httpd.exe -k restart -n <имя>."""
    calls = []

    def fake_run(args, **kwargs):
        calls.append(args)
        return SimpleNamespace(returncode=0, stdout=b"ok", stderr=b"")

    monkeypatch.setattr(wp.subprocess, "run", fake_run)
    publisher = make_publisher(tmp_path, instances=[
        {"name": "apache-80", "apache_root": str(template_apache), "port": 80, "versions": ["8.3.25.1394"]},
    ])
    result = publisher.restart_apache(publisher.select_instance("8.3.25.1394"))
    assert result.ok
    # последний вызов — перезапуск службы с именем по умолчанию Apache24-<порт>
    assert calls[-1][1:3] == ["-k", "restart"]
    assert calls[-1][-2:] == ["-n", "Apache24-80"]


def test_restart_apache_missing_httpd(tmp_path, monkeypatch):
    publisher = make_publisher(tmp_path, instances=[
        {"name": "solo", "apache_root": str(tmp_path / "NoBin"), "port": 80, "versions": []},
    ])
    result = publisher.restart_apache(publisher.select_instance("8.3.25.1394"))
    assert not result.ok
    assert "Не найден" in result.stderr


def test_restart_apache_console_mode_starts_hidden(tmp_path, template_apache, monkeypatch):
    """Нет службы, порт не слушается — запускается скрытый процесс."""
    publisher = make_publisher(tmp_path, instances=[
        {"name": "apache-80", "apache_root": str(template_apache), "port": 80, "versions": ["8.3.25.1394"]},
    ])
    monkeypatch.setattr(publisher, "service_exists", lambda instance: False)
    monkeypatch.setattr(publisher, "is_port_listening", lambda port, host="127.0.0.1", timeout=2: False)
    started = []
    monkeypatch.setattr(publisher, "start_apache_hidden", lambda instance, timeout=30: started.append(instance) or SimpleNamespace(ok=True))

    result = publisher.restart_apache(publisher.select_instance("8.3.25.1394"))

    assert result.ok
    assert len(started) == 1


def test_service_exists(tmp_path, monkeypatch):
    def fake_run(args, **kwargs):
        return SimpleNamespace(returncode=0 if args[1] == "query" else 1, stdout=b"", stderr=b"")

    monkeypatch.setattr(wp.subprocess, "run", fake_run)
    publisher = make_publisher(tmp_path, instances=[
        {"name": "apache-80", "apache_root": str(tmp_path / "Apache24"), "port": 80, "versions": []},
    ])
    assert publisher.service_exists(publisher.select_instance("8.3.25.1394")) is True


def test_start_apache_hidden_via_wmi(tmp_path, template_apache, monkeypatch):
    """Запуск вне консольной сессии (WMI) + скрытое окно (Start-Process -WindowStyle Hidden)."""
    calls = []

    def fake_run(args, **kwargs):
        calls.append(args)
        return SimpleNamespace(returncode=0, stdout=b"", stderr=b"")

    monkeypatch.setattr(wp.subprocess, "run", fake_run)
    publisher = make_publisher(tmp_path, instances=[
        {"name": "apache-80", "apache_root": str(template_apache), "port": 80, "versions": []},
    ])
    result = publisher.start_apache_hidden(publisher.select_instance("8.3.25.1394"))
    assert result.ok
    ps_script = calls[0][-1]
    assert "Win32_Process" in ps_script  # процесс вне нашего job-объекта
    assert "EncodedCommand" in ps_script  # внутренний скрипт без проблем с кавычками
    assert "WindowStyle Hidden" in ps_script


def test_ensure_apache_running_hidden_when_no_admin(tmp_path, template_apache, monkeypatch):
    """Без админа и без службы — скрытый процесс (тихо, без окна)."""
    publisher = make_publisher(tmp_path, instances=[
        {"name": "apache-80", "apache_root": str(template_apache), "port": 80, "versions": []},
    ])
    monkeypatch.setattr(publisher, "is_port_listening", lambda port, host="127.0.0.1", timeout=2: False)
    monkeypatch.setattr(publisher, "service_exists", lambda instance: False)
    monkeypatch.setattr(wp, "is_admin", lambda: False)
    started = []
    monkeypatch.setattr(publisher, "start_apache_hidden", lambda instance, timeout=30: started.append(instance) or SimpleNamespace(ok=True))

    result = publisher.ensure_apache_running(publisher.select_instance("8.3.25.1394"))

    assert result.ok
    assert len(started) == 1


def test_ensure_apache_running_admin_installs_service(tmp_path, template_apache, monkeypatch):
    """Под админом, службы нет, консольный httpd слушает порт — ставим службу."""
    publisher = make_publisher(tmp_path, instances=[
        {"name": "apache-80", "apache_root": str(template_apache), "port": 80, "versions": []},
    ])
    instance = publisher.select_instance("8.3.25.1394")
    monkeypatch.setattr(publisher, "service_exists", lambda i: False)
    monkeypatch.setattr(publisher, "is_port_listening", lambda port, host="127.0.0.1", timeout=2: True)
    monkeypatch.setattr(wp, "is_admin", lambda: True)
    stopped = []
    monkeypatch.setattr(publisher, "stop_apache",
                        lambda i, timeout=30: stopped.append(i) or SimpleNamespace(ok=True, stdout="stopped"))
    monkeypatch.setattr(publisher, "install_service",
                        lambda i, timeout=60: SimpleNamespace(ok=True, stdout="installed", stderr=""))
    restarted = []
    monkeypatch.setattr(publisher, "restart_apache",
                        lambda i, timeout=30: restarted.append(i) or SimpleNamespace(ok=True, stdout="started"))

    result = publisher.ensure_apache_running(instance)

    assert result.ok
    assert len(stopped) == 1  # консольный процесс освободил порт
    assert len(restarted) == 1  # служба запущена


def test_install_service_sets_autostart(tmp_path, template_apache, monkeypatch):
    """install_service включает автозапуск (sc config start= auto)."""
    calls = []

    def fake_run(args, **kwargs):
        calls.append(args)
        return SimpleNamespace(returncode=0, stdout=b"", stderr=b"")

    monkeypatch.setattr(wp.subprocess, "run", fake_run)
    publisher = make_publisher(tmp_path, instances=[
        {"name": "apache-80", "apache_root": str(template_apache), "port": 80, "versions": []},
    ])
    result = publisher.install_service(publisher.select_instance("8.3.25.1394"))
    assert result.ok
    auto_call = [c for c in calls if c[0] == "sc" and "config" in c]
    assert auto_call and auto_call[0][2:5] == ["Apache24-80", "start=", "auto"]
    assert "Автозапуск" in result.stdout


def test_verify_uses_publication_url(tmp_path, monkeypatch):
    """verify() строит URL и проверяет HTTP-ответ (urllib замокан)."""
    monkeypatch.setattr(wp, "verify_publication", lambda *a, **k: True)
    publisher = make_publisher(tmp_path)
    assert publisher.verify(make_db(version="8.3.27.1688")) is True


def test_strip_1c_publications():
    conf = (
        'Define SRVROOT "C:/Apache24-8327"\n'
        "Listen 81\n"
        "LoadModule mime_module modules/mod_mime.so\n"
        "# 1c publication\n"
        'Alias "/shop" "c:/1CWEB/shop/"\n'
        '<Directory "c:/1CWEB/shop/">\n'
        "    SetHandler 1c-application\n"
        '    ManagedApplicationDescriptor "c:/1CWEB/shop/default.vrd"\n'
        "</Directory>\n"
        '<IfModule alias_module>\n'
        '    Alias /icons/ "C:/Apache24/icons/"\n'
        '<Directory "C:/Apache24/icons">\n'
        "    Options Indexes MultiViews\n"
        "</Directory>\n"
        "</IfModule>\n"
    )
    stripped = WebPublisher._strip_1c_publications(conf)
    assert 'Alias "/shop"' not in stripped
    assert "1c-application" not in stripped
    assert "ManagedApplicationDescriptor" not in stripped
    # не-1С блоки (иконки) остаются
    assert 'Alias /icons/' in stripped
    assert "mime_module" in stripped
    assert "Listen 81" in stripped


# ------------------------------------------------------------------ #
#  Интеграция в GUI                                                   #
# ------------------------------------------------------------------ #

def test_db_publish_mixin_registered_in_database_actions():
    """Публикация должна быть доступна как действие для базы (F9)."""
    from gui.actions import DatabaseActions
    from gui.mixins.db_publish_mixin import DbPublishMixin

    assert DbPublishMixin in DatabaseActions.__mro__
    assert hasattr(DatabaseActions, "publish_database")
    assert hasattr(DatabaseActions, "unpublish_database")


def test_apache_manager_mixin_registered_in_tree_window():
    """Управление Apache (F2) должно быть доступно в главном окне."""
    from gui.tree_window import TreeWindow
    from gui.mixins import ApacheManagerMixin

    assert ApacheManagerMixin in TreeWindow.__mro__
    assert hasattr(TreeWindow, "open_apache_manager")


def test_settings_dialog_returns_publish_fields(qt_app):
    """Ctrl+E: поля публикации (имя/каталог) попадают в get_settings()."""
    from gui.dialogs.database_settings_dialog import DatabaseSettingsDialog
    from models.database import Database1C

    db = Database1C(id="test-astor", folder="/Тест",
                    name="АСТОР", connect='Srvr="srv-1c-8327:1541";Ref="astor_kom56_0610_Pechericadv_1";',
                    version="8.3.27.1688", app_arch="x86")
    dialog = DatabaseSettingsDialog(None, db)
    dialog.publish_name_edit.setText("shop")
    dialog.publish_dir_edit.setText(r"c:\1CWEB\shop")

    settings = dialog.get_settings()

    assert settings["publish_name"] == "shop"
    assert settings["publish_dir"] == r"c:\1CWEB\shop"


def test_settings_dialog_publish_fields_default_none(qt_app):
    """Без ввода поля публикации возвращают None (не сохраняется мусор)."""
    from gui.dialogs.database_settings_dialog import DatabaseSettingsDialog
    from models.database import Database1C

    db = Database1C(id="test-zup", folder="/Тест",
                    name="ЗУП", connect='Srvr="s";Ref="zup";', version="8.3.25.1394")
    dialog = DatabaseSettingsDialog(None, db)
    settings = dialog.get_settings()
    assert settings["publish_name"] is None
    assert settings["publish_dir"] is None


def test_apache_dialog_has_f1_help(qt_app):
    """В диалоге управления Apache есть кнопка «Справка (F1)» и открывается справка."""
    from gui.dialogs.apache_manager_dialog import ApacheManagerDialog, ApacheHelpDialog
    from services.web_publisher import WebPublisher
    from PySide6.QtWidgets import QPushButton, QTextEdit

    dialog = ApacheManagerDialog(publisher=WebPublisher())
    texts = [b.text() for b in dialog.findChildren(QPushButton)]
    assert "Справка (F1)" in texts
    # справка «что и зачем» открывается (конструктор без ошибок, есть текст)
    help_dialog = ApacheHelpDialog(dialog)
    editors = help_dialog.findChildren(QTextEdit)
    assert editors and "wsap24.dll" in editors[0].toPlainText()
    help_dialog.close()


def test_update_copy_from_snapshot(qt_app, monkeypatch):
    """F12: копия базы с датой + новая строка подключения (спрашиваем только её)."""
    from gui.actions.database_operations import DatabaseOperations
    from models.database import Database1C
    from PySide6.QtWidgets import QInputDialog

    old_connect = 'Srvr="srv-1c-8325:1541";Ref="ZUP_HRAN_old";'
    new_connect = 'Srvr="srv-1c-8325:1541";Ref="blank_database_0804_Pechericadv_3";'
    last_run = datetime.now()
    db = Database1C(id="zup-hran", folder="/Хранилища", name="ЗУП ХРАН", connect=old_connect,
                    version="8.3.25.1394", last_run_time=last_run,
                    publish_name="zup_hran", publish_dir=r"c:\1CWEB\zup")

    messages = []
    win = SimpleNamespace(statusBar=SimpleNamespace(showMessage=lambda m: messages.append(m)))
    saved = []
    reloaded = []
    ops = DatabaseOperations.__new__(DatabaseOperations)
    ops.window = win
    ops.all_bases = [db]
    ops.save_callback = lambda: saved.append(True)
    ops.reload_callback = lambda: reloaded.append(True)

    monkeypatch.setattr(QInputDialog, "getText",
                        staticmethod(lambda *a, **k: (new_connect, True)))

    ops.update_copy_from_snapshot(db, Database1C)

    assert db.name == f"ЗУП ХРАН {datetime.now().strftime('%Y-%m-%d')}"  # исходная — с датой
    assert len(ops.all_bases) == 2
    fresh = ops.all_bases[1]
    assert fresh.name == "ЗУП ХРАН"  # свежая копия под исходным именем
    assert fresh.connect == new_connect  # новая строка подключения подставлена
    assert fresh.publish_name == "zup_hran"  # параметры публикации унаследованы
    assert fresh.last_run_time == last_run  # дата/время запуска — как у оригинала
    assert saved and reloaded
    assert any("Обновлена копия из снапшота" in m or "Создана копия" in m for m in messages)


def test_update_copy_from_snapshot_cancel(qt_app, monkeypatch):
    """Отмена в диалоге — ничего не создаётся."""
    from gui.actions.database_operations import DatabaseOperations
    from models.database import Database1C
    from PySide6.QtWidgets import QInputDialog

    db = Database1C(id="zup-hran", folder="/Хранилища", name="ЗУП ХРАН",
                    connect='Srvr="s";Ref="old";', version="8.3.25.1394")
    win = SimpleNamespace(statusBar=SimpleNamespace(showMessage=lambda m: None))
    ops = DatabaseOperations.__new__(DatabaseOperations)
    ops.window = win
    ops.all_bases = [db]
    ops.save_callback = lambda: None
    ops.reload_callback = lambda: None

    monkeypatch.setattr(QInputDialog, "getText",
                        staticmethod(lambda *a, **k: ("", False)))

    ops.update_copy_from_snapshot(db, Database1C)

    assert len(ops.all_bases) == 1
    assert db.name == "ЗУП ХРАН"


# ------------------------------------------------------------------ #
#  Управление Apache: статус, остановка, базы->инстансы               #
# ------------------------------------------------------------------ #

SC_RUNNING = ("STATE              : 4  RUNNING \n").encode("cp866")
SC_STOPPED = ("STATE              : 1  STOPPED \n").encode("cp866")
SC_RUNNING_RU = ("Состояние          : 4  RUNNING \n").encode("cp866")


def test_service_state_running(tmp_path, monkeypatch):
    monkeypatch.setattr(wp.subprocess, "run",
                        lambda *a, **k: SimpleNamespace(returncode=0, stdout=SC_RUNNING, stderr=b""))
    publisher = make_publisher(tmp_path, instances=[
        {"name": "apache-80", "apache_root": str(tmp_path / "Apache24"), "port": 80, "versions": []},
    ])
    assert publisher.service_state(publisher.select_instance("8.3.25.1394")) == "running"


def test_service_state_stopped(tmp_path, monkeypatch):
    monkeypatch.setattr(wp.subprocess, "run",
                        lambda *a, **k: SimpleNamespace(returncode=0, stdout=SC_STOPPED, stderr=b""))
    publisher = make_publisher(tmp_path, instances=[
        {"name": "apache-80", "apache_root": str(tmp_path / "Apache24"), "port": 80, "versions": []},
    ])
    assert publisher.service_state(publisher.select_instance("8.3.25.1394")) == "stopped"


def test_service_state_russian_locale(tmp_path, monkeypatch):
    """sc.exe может выводить «Состояние» вместо STATE — парсер должен понимать оба."""
    monkeypatch.setattr(wp.subprocess, "run",
                        lambda *a, **k: SimpleNamespace(returncode=0, stdout=SC_RUNNING_RU, stderr=b""))
    publisher = make_publisher(tmp_path, instances=[
        {"name": "apache-80", "apache_root": str(tmp_path / "Apache24"), "port": 80, "versions": []},
    ])
    assert publisher.service_state(publisher.select_instance("8.3.25.1394")) == "running"


def test_service_state_absent(tmp_path, monkeypatch):
    monkeypatch.setattr(wp.subprocess, "run",
                        lambda *a, **k: SimpleNamespace(returncode=1060, stdout=b"", stderr=b""))
    publisher = make_publisher(tmp_path, instances=[
        {"name": "apache-80", "apache_root": str(tmp_path / "Apache24"), "port": 80, "versions": []},
    ])
    assert publisher.service_state(publisher.select_instance("8.3.25.1394")) == "absent"


def test_pid_on_port(tmp_path, monkeypatch):
    netstat_out = (
        "  TCP    0.0.0.0:80     0.0.0.0:0     LISTENING    9092\n"
        "  TCP    0.0.0.0:81     0.0.0.0:0     LISTENING    22584\n"
    ).encode("cp866")
    monkeypatch.setattr(wp.subprocess, "run",
                        lambda *a, **k: SimpleNamespace(returncode=0, stdout=netstat_out, stderr=b""))
    publisher = make_publisher(tmp_path)
    assert publisher._pid_on_port(81) == [22584]
    assert publisher._pid_on_port(80) == [9092]
    assert publisher._pid_on_port(9999) == []


def test_bases_per_instance(tmp_path):
    """Базы распределяются по инстансам согласно версии платформы."""
    publisher = make_publisher(tmp_path)
    zup = make_db(name="ЗУП", version="8.3.25.1394")
    astor = make_db(name="АСТОР", version="8.3.27.1688")
    unknown = make_db(name="Старая", version="8.3.23.2040")

    mapping = publisher.bases_per_instance([zup, astor, unknown])

    assert [b.name for b in mapping["apache-80"]] == ["ЗУП"]
    assert [b.name for b in mapping["apache24-8327"]] == ["АСТОР"]
    assert "Старая" not in [b for bases in mapping.values() for b in bases]


def test_stop_apache_via_service(tmp_path, monkeypatch):
    """Остановка через службу: httpd -k stop -n <имя>."""
    calls = []
    root = tmp_path / "Apache24"
    (root / "bin").mkdir(parents=True)
    (root / "bin" / "httpd.exe").write_bytes(b"httpd")

    def fake_run(args, **kwargs):
        calls.append(args)
        return SimpleNamespace(returncode=0, stdout=b"ok", stderr=b"")

    monkeypatch.setattr(wp.subprocess, "run", fake_run)
    publisher = make_publisher(tmp_path, instances=[
        {"name": "apache-80", "apache_root": str(root), "port": 80, "versions": []},
    ])
    result = publisher.stop_apache(publisher.select_instance("8.3.25.1394"))
    assert result.ok
    stop_call = [c for c in calls if c[0].endswith("httpd.exe") and c[1:3] == ["-k", "stop"]]
    assert stop_call and stop_call[0][-2:] == ["-n", "Apache24-80"]


def test_stop_apache_console_kills_pid(tmp_path, monkeypatch):
    """Без службы — убиваем процесс на порту."""
    calls = []

    def fake_run(args, **kwargs):
        calls.append(args)
        if args[0] == "netstat":
            return SimpleNamespace(returncode=0, stdout=b"  TCP 0.0.0.0:81 0.0.0.0:0 LISTENING 4242\n", stderr=b"")
        if args[0] == "sc":
            return SimpleNamespace(returncode=1060, stdout=b"", stderr=b"")
        return SimpleNamespace(returncode=0, stdout=b"", stderr=b"")

    monkeypatch.setattr(wp.subprocess, "run", fake_run)
    publisher = make_publisher(tmp_path)
    result = publisher.stop_apache(publisher.select_instance("8.3.27.1688"))
    assert result.ok
    kill_call = [c for c in calls if c[0] == "taskkill"]
    assert kill_call and kill_call[0][-1] == "4242"
