"""Публикация базы 1С на веб-сервере Apache через webinst.exe.

Проблема, которую решает модуль:
    Один экземпляр Apache может загрузить только одну версию модуля
    расширения веб-сервера 1С (wsap24.dll). Модуль жёстко регистрируется
    под именем ``_1cws_module`` и привязан к версии платформы, поэтому две
    базы на разных версиях платформы не могут одновременно работать через
    один Apache — на второй возникает ошибка 409 (различаются версии
    клиента и сервера).

Решение (вариант A):
    Несколько экземпляров Apache, по одному на версию платформы, каждый
    на своём порту (80, 81, ...). База публикуется webinst.exe ТОЙ ЖЕ
    версии платформы, что и сама база, в конфиг своего экземпляра Apache.
    Путь к wsap24.dll в httpd.conf webinst пишет сам — из каталога, где
    лежит webinst.exe.

Модуль не зависит от GUI и от models.database: ему достаточно объекта с
атрибутами ``connect``, ``name``, ``version``, ``app_arch`` (duck typing).
"""

import base64
import json
import os
import re
import shutil
import subprocess
import urllib.request
import urllib.error
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Sequence

# ------------------------------------------------------------------ #
#  Конфигурация по умолчанию                                          #
# ------------------------------------------------------------------ #

# Путь к пользовательскому JSON-конфигу с описанием экземпляров Apache.
# Формат:
#   {
#     "apache_instances": [
#       {
#         "name": "apache24-8327",
#         "apache_root": "C:/Apache24-8327",
#         "port": 81,
#         "versions": ["8.3.27.1688"],
#         "template_root": "C:/Apache24"   # необязательно: откуда копировать
#       },
#       ...
#     ],
#     "default_host": "127.0.0.1"
#   }
def _default_config_path() -> Path:
    appdata = os.getenv('APPDATA') or str(Path.home())
    return Path(appdata) / '1c_launcher' / 'web_publish.json'


DEFAULT_APACHE_INSTANCES = [
    {
        "name": "apache",
        "apache_root": r"C:\Apache24",
        "port": 80,
        "versions": [],
    },
]

# Стандартные корни установки платформы 1С
PROGRAM_FILES_64 = Path(r"C:\Program Files\1cv8")
PROGRAM_FILES_32 = Path(r"C:\Program Files (x86)\1cv8")


class PublishError(Exception):
    """Ошибка публикации базы на веб-сервере."""


def detect_pe_bits(path: Path) -> Optional[int]:
    """Разрядность PE-файла (32 или 64) по заголовку, None если не удалось."""
    try:
        with open(path, "rb") as f:
            header = f.read(2)
            if header != b"MZ":
                return None
            f.seek(0x3C)
            e_lfanew = int.from_bytes(f.read(4), "little")
            f.seek(e_lfanew)
            if f.read(4) != b"PE\0\0":
                return None
            machine = int.from_bytes(f.read(2), "little")
    except OSError:
        return None
    if machine == 0x8664:
        return 64
    if machine == 0x14C:
        return 32
    return None


def is_admin() -> bool:
    """True, если процесс запущен с правами администратора (Windows)."""
    try:
        import ctypes

        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


@dataclass
class ApacheInstance:
    """Один экземпляр Apache (свой httpd.conf и свой порт)."""

    name: str
    apache_root: Path
    port: int = 80
    versions: List[str] = field(default_factory=list)
    host: str = "127.0.0.1"
    template_root: Optional[Path] = None
    apache_bits: Optional[int] = None  # 32/64; если None — определяется по httpd.exe
    service_name: Optional[str] = None  # имя службы Windows; по умолчанию Apache24-<порт>

    @property
    def conf_path(self) -> Path:
        return self.apache_root / "conf" / "httpd.conf"

    @property
    def htdocs_root(self) -> Path:
        return self.apache_root / "htdocs"

    @property
    def httpd_exe(self) -> Path:
        return self.apache_root / "bin" / "httpd.exe"

    def supports_version(self, version: str) -> bool:
        """Версия подходит, если совпадает точно или по префиксу."""
        if not self.versions:
            return True
        v = version.strip()
        return any(v == item or v.startswith(item) for item in self.versions)

    @classmethod
    def from_dict(cls, data: dict) -> "ApacheInstance":
        return cls(
            name=str(data["name"]),
            apache_root=Path(data.get("apache_root", r"C:\Apache24")),
            port=int(data.get("port", 80)),
            versions=[str(v) for v in data.get("versions", [])],
            host=str(data.get("host", "127.0.0.1")),
            template_root=Path(data["template_root"]) if data.get("template_root") else None,
            apache_bits=int(data["apache_bits"]) if data.get("apache_bits") else None,
            service_name=str(data["service_name"]) if data.get("service_name") else None,
        )

    @property
    def effective_service_name(self) -> str:
        """Имя службы Windows: из конфига или Apache24-<порт>."""
        return self.service_name or f"Apache24-{self.port}"


@dataclass
class PublishResult:
    """Результат выполнения webinst.exe."""

    ok: bool
    command: Sequence[str]
    returncode: Optional[int] = None
    stdout: str = ""
    stderr: str = ""
    publication_url: Optional[str] = None


class WebPublisher:
    """Публикация базы 1С на Apache.

    Args:
        config_path: путь к JSON-конфигу с экземплярами Apache.
            Если файл не существует — используются DEFAULT_APACHE_INSTANCES.
    """

    def __init__(self, config_path: Optional[os.PathLike] = None):
        self.config_path = Path(config_path) if config_path else _default_config_path()
        self.default_host = "127.0.0.1"
        self.apache_instances: List[ApacheInstance] = []
        self._load_config()

    # ------------------------------------------------------------------ #
    #  Конфигурация                                                       #
    # ------------------------------------------------------------------ #

    def _load_config(self):
        """Загружает список экземпляров Apache из JSON (или дефолты)."""
        if self.config_path and self.config_path.exists():
            try:
                with open(self.config_path, encoding="utf-8-sig") as f:
                    data = json.load(f)
                instances = data.get("apache_instances") or []
                self.default_host = str(data.get("default_host", self.default_host))
            except (OSError, json.JSONDecodeError) as e:
                raise PublishError(
                    f"Не удалось прочитать конфиг публикации {self.config_path}: {e}"
                ) from e
        else:
            instances = DEFAULT_APACHE_INSTANCES

        if not instances:
            raise PublishError("В конфиге публикации нет ни одного экземпляра Apache")

        self.apache_instances = [ApacheInstance.from_dict(i) for i in instances]

    # ------------------------------------------------------------------ #
    #  Выбор экземпляра Apache и webinst.exe                              #
    # ------------------------------------------------------------------ #

    def select_instance(self, version: Optional[str]) -> ApacheInstance:
        """Выбирает экземпляр Apache для версии платформы базы."""
        if not version:
            raise PublishError(
                "У базы не указана версия платформы (поле Version в ibases.v8i). "
                "Заполните версию в настройках базы (Ctrl+E)."
            )
        for instance in self.apache_instances:
            if instance.supports_version(version):
                return instance
        supported = ", ".join(
            f"{i.name} (порт {i.port}, версии: {', '.join(i.versions) or 'любые'})"
            for i in self.apache_instances
        )
        raise PublishError(
            f"Для версии платформы {version!r} не найден экземпляр Apache. "
            f"Доступны: {supported}. Дополните конфиг {self.config_path}."
        )

    def find_webinst(self, version: Optional[str], app_arch: Optional[str] = None) -> Optional[str]:
        """Ищет webinst.exe нужной версии платформы с учётом разрядности."""
        if not version:
            return None

        roots = []
        if app_arch == "x86_64":
            roots = [PROGRAM_FILES_64, PROGRAM_FILES_32]
        elif app_arch == "x86":
            roots = [PROGRAM_FILES_32, PROGRAM_FILES_64]
        else:
            roots = [PROGRAM_FILES_64, PROGRAM_FILES_32]

        for root in roots:
            candidate = root / version / "bin" / "webinst.exe"
            if candidate.exists():
                return str(candidate)
        return None

    def get_apache_bits(self, instance: ApacheInstance) -> Optional[int]:
        """Разрядность Apache: из httpd.exe, затем из конфига, по умолчанию 64."""
        if instance.httpd_exe.exists():
            bits = detect_pe_bits(instance.httpd_exe)
            if bits:
                return bits
        if instance.apache_bits:
            return instance.apache_bits
        return 64

    def select_webinst(self, version: Optional[str], app_arch: Optional[str], apache_bits: Optional[int]) -> str:
        """Выбирает webinst.exe версии платформы под разрядность Apache.

        Модуль расширения веб-сервера (wsap24.dll) должен совпадать по
        разрядности с Apache: в 64-битный Apache 32-битная платформа не
        загрузится. Сначала ищем установку платформы, совпадающую с
        разрядностью Apache, затем — с разрядностью из настроек базы.
        """
        if not version:
            raise PublishError("У базы не указана версия платформы (поле Version)")

        apache_bits = apache_bits or 64

        def root_bits(root: Path) -> int:
            return 64 if root == PROGRAM_FILES_64 else 32

        # Приоритет: разрядность Apache, затем разрядность из настроек базы
        def sort_key(root: Path):
            return (
                0 if root_bits(root) == apache_bits else 1,
                0 if root_bits(root) == (64 if app_arch == "x86_64" else 32) else 1,
            )

        roots = sorted([PROGRAM_FILES_64, PROGRAM_FILES_32], key=sort_key)

        for root in roots:
            bin_dir = root / version / "bin"
            webinst = bin_dir / "webinst.exe"
            wsap = bin_dir / "wsap24.dll"
            if webinst.exists() and wsap.exists():
                dll_bits = detect_pe_bits(wsap)
                if dll_bits is None or dll_bits == apache_bits:
                    return str(webinst)
                break  # есть установка, но не той разрядности — дальше искать бессмысленно

        # Ничего не подошло — детализируем ошибку
        for root in roots:
            webinst = root / version / "bin" / "webinst.exe"
            wsap = root / version / "bin" / "wsap24.dll"
            if webinst.exists() and wsap.exists():
                found_bits = detect_pe_bits(wsap)
                raise PublishError(
                    f"Разрядность не совпадает: Apache {apache_bits}-битный, а установка "
                    f"платформы {version!r} — {found_bits or 'неизвестной разрядности'}-битная "
                    f"({root}). Установите {apache_bits}-битную платформу {version} "
                    "или укажите другую разрядность Apache в конфиге публикации."
                )
        raise PublishError(
            f"Не найден webinst.exe/wsap24.dll для версии {version!r} "
            f"(искал в {PROGRAM_FILES_64} и {PROGRAM_FILES_32})"
        )

    # ------------------------------------------------------------------ #
    #  Авто-копирование и настройка экземпляра Apache                     #
    # ------------------------------------------------------------------ #

    def ensure_instance_ready(self, instance: ApacheInstance) -> bool:
        """Готовит экземпляр Apache: если его каталога нет — копирует из шаблона.

        Шаблон: ``instance.template_root`` либо первый настроенный экземпляр
        из конфига, у которого httpd.conf существует.

        При копировании в httpd.conf:
        - все пути источника заменяются на путь назначения (Define SRVROOT и т.п.);
        - ``Listen`` переключается на порт экземпляра;
        - строка ``LoadModule _1cws_module`` комментируется — webinst при
          публикации допишет модуль нужной версии платформы (два LoadModule
          одного имени Apache не загрузит).

        Returns:
            True, если экземпляр готов (существовал или создан).
        """
        if instance.conf_path.exists():
            return True

        source = self._find_template(instance)
        self._clone_apache(source, instance)
        return True

    def _find_template(self, instance: ApacheInstance) -> ApacheInstance:
        """Находит источник для копирования."""
        if instance.template_root and instance.template_root.exists():
            return ApacheInstance(
                name=f"template-{instance.name}",
                apache_root=instance.template_root,
                port=instance.port,
            )
        for candidate in self.apache_instances:
            if candidate.name == instance.name:
                continue
            if candidate.apache_root.exists() and candidate.conf_path.exists():
                return candidate
        raise PublishError(
            f"Экземпляр {instance.name!r} ({instance.apache_root}) не настроен и "
            "не найден шаблон Apache для копирования. Создайте Apache вручную "
            "или укажите template_root в конфиге."
        )

    def _clone_apache(self, source: ApacheInstance, target: ApacheInstance):
        """Копирует дерево Apache и правит конфиги под новый экземпляр."""
        source_root = source.apache_root
        target_root = target.apache_root
        try:
            shutil.copytree(
                source_root,
                target_root,
                ignore=shutil.ignore_patterns("logs"),
            )
        except (OSError, shutil.Error) as e:
            raise PublishError(f"Не удалось скопировать Apache {source_root} -> {target_root}: {e}") from e

        # Каталог логов исключён из копирования — Apache требует его наличие
        (target_root / "logs").mkdir(exist_ok=True)

        for conf_file in self._iter_conf_files(target_root):
            self._fix_cloned_config(conf_file, source_root, target_root, target.port)

    @staticmethod
    def _iter_conf_files(apache_root: Path):
        """Все текстовые конфиги Apache (.conf) под conf/."""
        conf_dir = apache_root / "conf"
        if not conf_dir.exists():
            return []
        files = list(conf_dir.glob("*.conf"))
        extra = conf_dir / "extra"
        if extra.exists():
            files.extend(extra.glob("*.conf"))
        original = conf_dir / "original"
        if original.exists():
            files.extend(original.glob("*.conf"))
        return files

    @staticmethod
    def _fix_cloned_config(conf_file: Path, source_root: Path, target_root: Path, port: int):
        """Правит один конфиг: пути, Listen, LoadModule _1cws_module."""
        try:
            text = conf_file.read_text(encoding="cp1251", errors="replace")
        except OSError:
            return

        # 1. Пути источника -> назначения (обе формы слэшей, без учёта регистра)
        for src, dst in (
            (str(source_root), str(target_root)),
            (str(source_root).replace("\\", "/"), str(target_root).replace("\\", "/")),
        ):
            text = re.sub(re.escape(src), lambda m: dst, text, flags=re.IGNORECASE)

        # 2. Активный Listen -> порт экземпляра
        text = re.sub(
            r"^(Listen\s+)(\d{1,5})(\s*)$",
            lambda m: f"{m.group(1)}{port}{m.group(3)}",
            text,
            count=1,
            flags=re.MULTILINE,
        )
        text = re.sub(
            r"^(Listen\s+[^:\s]*:)(\d{1,5})(\s*)$",
            lambda m: f"{m.group(1)}{port}{m.group(3)}",
            text,
            count=1,
            flags=re.MULTILINE,
        )

        # 3. LoadModule _1cws_module комментируем (webinst допишет свою версию)
        text = re.sub(
            r"^(\s*)LoadModule\s+_1cws_module\b.*$",
            r"\1# LoadModule _1cws_module ... (закомментировано при клонировании; "
            r"webinst добавит модуль нужной версии)",
            text,
            flags=re.MULTILINE,
        )

        # 4. Старые публикации 1С из шаблона убираем — новый Apache обслуживает
        #    только то, что публикуют в НЕГО (иначе на :81 «светятся» чужие базы)
        text = WebPublisher._strip_1c_publications(text)

        try:
            conf_file.write_text(text, encoding="cp1251")
        except OSError:
            pass

    @staticmethod
    def _strip_1c_publications(text: str) -> str:
        """Удаляет блоки публикаций 1С из текста httpd.conf.

        Блок публикации webinst/конфигуратора выглядит так:

            # 1c publication
            Alias "/shop" "c:/1CWEB/shop/"
            <Directory "c:/1CWEB/shop/">
                ...
                SetHandler 1c-application
                ManagedApplicationDescriptor "..."
            </Directory>

        Удаляются блоки, помеченные комментарием ``# 1c publication`` либо
        содержащие ``SetHandler 1c-application``/``ManagedApplicationDescriptor``.
        """
        lines = text.splitlines()
        out = []
        i = 0
        n = len(lines)
        while i < n:
            line = lines[i]
            # Начало блока: комментарий публикации или Alias с последующим <Directory>
            starts_block = bool(re.match(r"^\s*#\s*1c\s+publication\b", line, re.IGNORECASE))
            is_alias = bool(re.match(r'^\s*Alias\s+"[^"]*"\s+"[^"]*"\s*$', line))
            if not starts_block and (is_alias and i + 1 < n
                                     and re.match(r'^\s*<Directory\s+"[^"]*">\s*$', lines[i + 1])):
                # Проверяем содержимое <Directory>...</Directory>
                j = i + 2
                is_1c = False
                while j < n and not re.match(r"^\s*</Directory>\s*$", lines[j]):
                    if re.search(r"SetHandler\s+1c-application|ManagedApplicationDescriptor", lines[j]):
                        is_1c = True
                    j += 1
                if is_1c and j < n:
                    i = j + 1  # пропустить Alias + <Directory>...</Directory>
                    continue

            if starts_block:
                # пропускаем до закрывающего </Directory> включительно
                i += 1
                while i < n and not re.match(r"^\s*</Directory>\s*$", lines[i]):
                    i += 1
                i += 1
                continue

            out.append(line)
            i += 1
        return "\n".join(out)

    def restart_apache(self, instance: ApacheInstance, timeout: float = 30) -> PublishResult:
        """Перезапускает Apache.

        Если Apache установлен как служба — httpd.exe -k restart (fallback
        -k start). Иначе (консольный режим) — запускает скрытый процесс,
        если порт не слушается. Best-effort: при неудаче возвращает
        PublishResult.ok=False, но не бросает исключение.
        """
        httpd = instance.httpd_exe
        command = [str(httpd), "-k", "restart"]
        if not httpd.exists():
            return PublishResult(
                ok=False,
                command=command,
                stderr=f"Не найден {httpd}",
            )

        if self.service_exists(instance):
            for args in (
                [str(httpd), "-k", "restart", "-n", instance.effective_service_name],
                [str(httpd), "-k", "start", "-n", instance.effective_service_name],
            ):
                try:
                    proc = subprocess.run(args, capture_output=True, timeout=timeout)
                    if proc.returncode == 0:
                        stdout = proc.stdout.decode("cp866", errors="replace") if proc.stdout else ""
                        return PublishResult(ok=True, command=args, returncode=0, stdout=stdout)
                except (OSError, subprocess.TimeoutExpired):
                    continue
            return PublishResult(
                ok=False,
                command=command,
                stderr="Служба Apache не перезапущена: httpd.exe -k restart/start завершились с ошибкой",
            )

        # Консольный режим: просто убеждаемся, что процесс работает без окна
        if not self.is_port_listening(instance.port):
            self.start_apache_hidden(instance, timeout=timeout)
        return PublishResult(ok=True, command=command, returncode=0)

    def service_exists(self, instance: ApacheInstance) -> bool:
        """True, если служба Windows с именем инстанса установлена."""
        try:
            proc = subprocess.run(
                ["sc", "query", instance.effective_service_name],
                capture_output=True,
                timeout=15,
            )
            return proc.returncode == 0
        except (OSError, subprocess.TimeoutExpired):
            return False

    def service_state(self, instance: ApacheInstance) -> str:
        """Состояние службы: 'running' | 'stopped' | 'absent'."""
        try:
            proc = subprocess.run(
                ["sc", "query", instance.effective_service_name],
                capture_output=True,
                timeout=15,
            )
        except (OSError, subprocess.TimeoutExpired):
            return "absent"
        if proc.returncode != 0:
            return "absent"
        text = proc.stdout.decode("cp866", errors="replace")
        # sc.exe в разных контекстах пишет по-русски: «Состояние» вместо STATE
        m = re.search(r"(?:STATE|Состояние)\s*:\s*(\d+)", text, re.IGNORECASE)
        if not m:
            return "absent"
        state_code = int(m.group(1))
        # 1 STOPPED, 2 START_PENDING, 3 STOP_PENDING, 4 RUNNING, 5 CONTINUE_PENDING,
        # 6 PAUSE_PENDING, 7 PAUSED
        if state_code == 4:
            return "running"
        if state_code in (1, 3):
            return "stopped"
        return "running" if state_code in (2, 5, 6, 7) else "stopped"

    def get_status(self, instance: ApacheInstance) -> dict:
        """Сводка по инстансу: служба, порт, разрядность, нужен ли вообще."""
        return {
            "instance": instance,
            "service": self.service_state(instance),
            "port_listening": self.is_port_listening(instance.port),
            "bits": self.get_apache_bits(instance),
        }

    @staticmethod
    def _pid_on_port(port: int) -> List[int]:
        """PID процессов, слушающих порт (через netstat)."""
        try:
            proc = subprocess.run(
                ["netstat", "-ano", "-p", "tcp"],
                capture_output=True,
                timeout=20,
            )
        except (OSError, subprocess.TimeoutExpired):
            return []
        text = proc.stdout.decode("cp866", errors="replace")
        pids = set()
        for line in text.splitlines():
            m = re.search(rf":{port}\s+\S+\s+LISTENING\s+(\d+)\s*$", line)
            if m:
                try:
                    pids.add(int(m.group(1)))
                except ValueError:
                    pass
        return sorted(pids)

    def stop_apache(self, instance: ApacheInstance, timeout: float = 30) -> PublishResult:
        """Останавливает Apache: службу или скрытый/консольный процесс на порту."""
        if self.service_exists(instance):
            httpd = instance.httpd_exe
            name = instance.effective_service_name
            for args in (
                [str(httpd), "-k", "stop", "-n", name] if httpd.exists() else None,
                ["sc", "stop", name],
            ):
                if args is None:
                    continue
                try:
                    proc = subprocess.run(args, capture_output=True, timeout=timeout)
                    if proc.returncode == 0:
                        stdout = proc.stdout.decode("cp866", errors="replace") if proc.stdout else ""
                        return PublishResult(ok=True, command=args, returncode=0, stdout=stdout)
                except (OSError, subprocess.TimeoutExpired):
                    continue
            return PublishResult(
                ok=False,
                command=["sc", "stop", name],
                stderr=f"Не удалось остановить службу {name} (нужны права администратора?)",
            )

        pids = self._pid_on_port(instance.port)
        if not pids:
            return PublishResult(ok=True, command=["(nothing to stop)"], returncode=0,
                                 stdout=f"Apache {instance.name} не запущен")
        for pid in pids:
            try:
                subprocess.run(["taskkill", "/F", "/PID", str(pid)],
                               capture_output=True, timeout=timeout)
            except (OSError, subprocess.TimeoutExpired):
                continue
        return PublishResult(
            ok=True,
            command=["taskkill /F /PID " + " ".join(str(p) for p in pids)],
            returncode=0,
            stdout=f"Остановлено процессов: {len(pids)}",
        )

    def bases_per_instance(self, bases) -> dict:
        """Сопоставляет базы экземплярам Apache (по версии платформы базы).

        Returns:
            dict: имя инстанса -> список баз, которые публикуются в него.
        """
        result = {}
        for base in bases:
            try:
                instance = self.select_instance(getattr(base, "version", None))
            except PublishError:
                continue
            result.setdefault(instance.name, []).append(base)
        return result

    def install_service(self, instance: ApacheInstance, timeout: float = 60) -> PublishResult:
        """Устанавливает Apache как службу Windows (нужны права администратора).

        После установки явно включается автозапуск (sc config start= auto).
        """
        httpd = instance.httpd_exe
        name = instance.effective_service_name
        args = [
            str(httpd), "-k", "install",
            "-n", name,
            "-d", str(instance.apache_root),
            "-f", str(instance.conf_path),
        ]
        try:
            proc = subprocess.run(args, capture_output=True, timeout=timeout)
        except (OSError, subprocess.TimeoutExpired) as e:
            return PublishResult(ok=False, command=args, stderr=f"Ошибка установки службы: {e}")
        stdout = proc.stdout.decode("cp866", errors="replace") if proc.stdout else ""
        stderr = proc.stderr.decode("cp866", errors="replace") if proc.stderr else ""
        if proc.returncode != 0:
            return PublishResult(ok=False, command=args, returncode=proc.returncode,
                                 stdout=stdout, stderr=stderr)

        # Явный автозапуск службы (httpd -k install не всегда ставит start=auto)
        try:
            auto = subprocess.run(
                ["sc", "config", name, "start=", "auto"],
                capture_output=True,
                timeout=timeout,
            )
            if auto.returncode == 0:
                stdout += "\nАвтозапуск службы включён (start=auto)."
        except (OSError, subprocess.TimeoutExpired):
            pass
        return PublishResult(ok=True, command=args, returncode=0, stdout=stdout, stderr=stderr)

    def ensure_apache_running(self, instance: ApacheInstance, timeout: float = 30) -> PublishResult:
        """Поднимает Apache «штатно»: служба Windows, если есть права администратора.

        Приоритет:
        1. Служба уже установлена — запускаем/перезапускаем её.
        2. Процесс под администратором — останавливаем консольный процесс на
           порту (если есть), устанавливаем службу с автозапуском и стартуем.
        3. Без прав администратора — скрытый процесс (без окна, но без
           автозапуска после перезагрузки).
        """
        if self.service_exists(instance):
            return self.restart_apache(instance, timeout=timeout)

        if is_admin():
            if self.is_port_listening(instance.port):
                self.stop_apache(instance, timeout=timeout)  # освобождаем порт
            install = self.install_service(instance, timeout=timeout)
            if not install.ok:
                return install
            return self.restart_apache(instance, timeout=timeout)

        if self.is_port_listening(instance.port):
            return PublishResult(ok=True, command=["port-check"], returncode=0,
                                 stdout=f"Apache {instance.name} уже слушает порт {instance.port}")
        return self.start_apache_hidden(instance, timeout=timeout)

    def verify(
        self,
        database,
        instance: Optional[ApacheInstance] = None,
        wsdir: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        timeout: float = 10,
    ) -> bool:
        """Проверяет, отвечает ли публикация базы (HTTP GET).

        True при любом HTTP-ответе (включая 401/403 — значит Apache отвечает),
        False при сетевой ошибке/таймауте.
        """
        url = self.build_publication_url(database, instance=instance, wsdir=wsdir)
        return verify_publication(url, username=username, password=password, timeout=timeout)

    @staticmethod
    def is_port_listening(port: int, host: str = "127.0.0.1", timeout: float = 2) -> bool:
        """True, если на порту уже есть слушающий сокет."""
        import socket

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        try:
            return sock.connect_ex((host, port)) == 0
        finally:
            sock.close()

    def start_apache_hidden(self, instance: ApacheInstance, timeout: float = 60) -> PublishResult:
        """Запускает httpd.exe тихо: через WMI, вне текущей консольной сессии.

        Не требует службы и прав администратора. Окно не показывается
        (powershell -WindowStyle Hidden + Start-Process -WindowStyle Hidden).
        Процесс привязан к сессии пользователя — после перезагрузки машины
        Apache нужно поднять заново (F9 или служба при запуске под админом).
        """
        httpd = instance.httpd_exe
        if not httpd.exists():
            return PublishResult(ok=False, command=[str(httpd)],
                                 stderr=f"Не найден {httpd}")
        bin_dir = str(instance.apache_root / "bin")
        # Внутренний скрипт кодируем base64 (UTF-16LE) — никаких проблем с кавычками
        inner_script = (
            f"Start-Process -FilePath '{httpd}' -WorkingDirectory '{bin_dir}' -WindowStyle Hidden"
        )
        encoded = base64.b64encode(inner_script.encode("utf-16-le")).decode("ascii")
        cmdline = (
            f"powershell.exe -NoProfile -NonInteractive -WindowStyle Hidden "
            f"-EncodedCommand {encoded}"
        )
        # WMI создаёт процесс вне job-объекта нашей консоли — он переживёт её
        ps_script = (
            "$r = Invoke-CimMethod -ClassName Win32_Process -MethodName Create "
            f"-Arguments @{{ CommandLine = '{cmdline}' ; CurrentDirectory = '{bin_dir}' }}; "
            "if ($r.ReturnValue -ne 0) { exit 1 }"
        )
        command = ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_script]
        try:
            proc = subprocess.run(command, capture_output=True, timeout=timeout)
        except (OSError, subprocess.TimeoutExpired) as e:
            return PublishResult(ok=False, command=command, stderr=f"Не удалось запустить httpd: {e}")
        if proc.returncode != 0:
            stderr = proc.stderr.decode("cp866", errors="replace") if proc.stderr else ""
            return PublishResult(
                ok=False, command=command, returncode=proc.returncode,
                stderr=stderr or "WMI-запуск завершился с ошибкой",
            )
        return PublishResult(
            ok=True, command=command, returncode=0,
            stdout=f"Apache {instance.name} запущен скрыто (порт {instance.port})",
        )

    # ------------------------------------------------------------------ #
    #  Формирование параметров webinst.exe                                #
    # ------------------------------------------------------------------ #

    @staticmethod
    def build_connstr(database) -> str:
        """Строка подключения для -connstr (как в Connect базы)."""
        return (database.connect or "").strip()

    @staticmethod
    def build_wsdir(database, wsdir: Optional[str] = None) -> str:
        """Псевдоним публикации (каталог в URL, например /zup).

        Приоритет: явный параметр -> поле базы PublishName -> очищенное имя
        базы; wsdir допустим только из латиницы/цифр. Если имя не даёт
        латинского псевдонима (например, кириллическое имя) — берётся Ref
        из строки подключения.
        """
        if wsdir and wsdir.strip():
            wsdir = wsdir.strip()
        elif database.publish_name and database.publish_name.strip():
            wsdir = database.publish_name.strip()
        else:
            wsdir = (database.name or "").strip()

        wsdir = re.sub(r"[^A-Za-z0-9_-]+", "_", wsdir).strip("_")

        # Псевдоним без латинских букв (кириллица/цифры) в URL не годится
        if not wsdir or not re.search(r"[A-Za-z]", wsdir):
            ref = re.search(r'(?i)Ref\s*=\s*["\']?([^;"\']+)', database.connect or "")
            if ref:
                wsdir = re.sub(r"[^A-Za-z0-9_-]+", "_", ref.group(1).strip()).strip("_")

        if not wsdir:
            raise PublishError("Не удалось сформировать псевдоним публикации (wsdir)")
        return wsdir

    def build_command(
        self,
        database,
        instance: Optional[ApacheInstance] = None,
        wsdir: Optional[str] = None,
        unpublish: bool = False,
    ) -> List[str]:
        """Формирует аргументы командной строки для webinst.exe."""
        instance = instance or self.select_instance(database.version)
        apache_bits = self.get_apache_bits(instance)
        webinst = self.select_webinst(database.version, database.app_arch, apache_bits)

        connstr = self.build_connstr(database)
        if not connstr:
            raise PublishError("У базы пустая строка подключения (Connect)")
        wsdir = self.build_wsdir(database, wsdir)
        publish_dir_path = self._publish_dir(database, instance, wsdir)

        args = [webinst]
        args.append("-unpublish" if unpublish else "-publish")
        args.append("-apache24")
        args.append("-wsdir")
        args.append(wsdir)
        if not unpublish:
            args.append("-dir")
            args.append(str(publish_dir_path))
            args.append("-connstr")
            args.append(connstr)
        args.append("-confpath")
        args.append(str(instance.conf_path))
        return args

    def _publish_dir(self, database, instance: ApacheInstance, wsdir: str) -> Path:
        """Каталог публикации: поле базы PublishDir или htdocs/<wsdir>."""
        publish_dir = (database.publish_dir or "").strip()
        if publish_dir:
            publish_dir_path = Path(publish_dir)
        else:
            publish_dir_path = instance.htdocs_root / wsdir
        publish_dir_path.mkdir(parents=True, exist_ok=True)
        return publish_dir_path

    def build_publication_url(
        self,
        database,
        instance: Optional[ApacheInstance] = None,
        wsdir: Optional[str] = None,
        host: Optional[str] = None,
    ) -> str:
        """URL публикации для проверки: http://host:port/wsdir."""
        instance = instance or self.select_instance(database.version)
        wsdir = self.build_wsdir(database, wsdir)
        host = host or instance.host or self.default_host
        port = "" if instance.port == 80 else f":{instance.port}"
        return f"http://{host}{port}/{wsdir}"

    # ------------------------------------------------------------------ #
    #  Запуск                                                             #
    # ------------------------------------------------------------------ #

    def run(
        self,
        database,
        instance: Optional[ApacheInstance] = None,
        wsdir: Optional[str] = None,
        unpublish: bool = False,
        timeout: float = 120,
    ) -> PublishResult:
        """Запускает webinst.exe и возвращает результат."""
        args = self.build_command(database, instance=instance, wsdir=wsdir, unpublish=unpublish)
        command_display = " ".join(f'"{a}"' for a in args)
        try:
            proc = subprocess.run(
                args,
                capture_output=True,
                timeout=timeout,
            )
        except FileNotFoundError as e:
            raise PublishError(f"webinst.exe не запускается: {e}") from e
        except subprocess.TimeoutExpired:
            raise PublishError(
                f"webinst.exe не завершился за {timeout} с. Команда: {command_display}"
            ) from None

        stdout = proc.stdout.decode("cp866", errors="replace") if proc.stdout else ""
        stderr = proc.stderr.decode("cp866", errors="replace") if proc.stderr else ""
        url = None
        if not unpublish:
            try:
                url = self.build_publication_url(database, instance=instance, wsdir=wsdir)
            except PublishError:
                url = None

        return PublishResult(
            ok=proc.returncode == 0,
            command=args,
            returncode=proc.returncode,
            stdout=stdout,
            stderr=stderr,
            publication_url=url,
        )

    # ------------------------------------------------------------------ #
    #  Высокоуровневые операции                                           #
    # ------------------------------------------------------------------ #

    def publish(self, database, wsdir: Optional[str] = None, instance: Optional[ApacheInstance] = None) -> PublishResult:
        """Опубликовать базу.

        webinst.exe перезаписывает default.vrd в каталоге публикации — это
        штатно: webinst подключается к базе (-connstr) и генерирует свежий
        vrd из конфигурации (веб-сервисы/точки берутся из самой базы).
        """
        return self.run(database, instance=instance, wsdir=wsdir, unpublish=False)

    def unpublish(self, database, wsdir: Optional[str] = None, instance: Optional[ApacheInstance] = None) -> PublishResult:
        """Отменить публикацию базы."""
        return self.run(database, instance=instance, wsdir=wsdir, unpublish=True)


def verify_publication(url: str, username: Optional[str] = None, password: Optional[str] = None, timeout: float = 10) -> bool:
    """Проверяет доступность URL публикации (HTTP GET).

    Возвращает True при любом HTTP-ответе (даже 401/403 — значит
    публикация отвечает). False — сетевые ошибки/таймаут.
    """
    request = urllib.request.Request(url, method="GET")
    if username is not None:
        import base64

        token = base64.b64encode(f"{username}:{password or ''}".encode("utf-8")).decode("ascii")
        request.add_header("Authorization", f"Basic {token}")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return True
    except urllib.error.HTTPError:
        return True
    except (urllib.error.URLError, OSError):
        return False
