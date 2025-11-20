from pathlib import Path
from typing import List
from models.database import Database1C
from datetime import datetime

class BaseReader:
    """Сервис для чтения списка баз из ibases.v8i"""
    
    def __init__(self, ibases_path: Path, encoding: str = 'utf-8-sig'):
        self.ibases_path = ibases_path
        self.encoding = encoding
    
    def read_bases(self) -> List[Database1C]:
        """Читает список баз из файла ibases.v8i"""
        if not self.ibases_path.exists():
            print(f"⚠️ Файл не найден: {self.ibases_path}")
            return []
        
        bases = []
        current_base = {}
        current_section_name = None
        
        try:
            with open(self.ibases_path, 'r', encoding=self.encoding) as file:
                for line in file:
                    line = line.strip()
                    
                    # Пропускаем пустые строки
                    if not line:
                        continue
                    
                    # Если встретили новую секцию [НАЗВАНИЕ], сохраняем предыдущую базу
                    if line.startswith('[') and line.endswith(']'):
                        # Сохраняем предыдущую базу, если она была и у нее непустой connect
                        if current_base and current_section_name:
                            # Проверяем наличие непустого connect
                            connect = current_base.get('Connect', '').strip()
                            if connect:  # Пропускаем записи с пустым connect
                                current_base['SectionName'] = current_section_name
                                bases.append(self._create_database(current_base))
                        
                        # Начинаем новую базу
                        current_base = {}
                        # Извлекаем имя секции из [Название]
                        current_section_name = line[1:-1].strip()
                        continue
                    
                    # Парсим остальные параметры
                    if '=' in line:
                        key, value = line.split('=', 1)
                        current_base[key] = value
                
                # Добавляем последнюю базу, если есть и у нее непустой connect
                if current_base and current_section_name:
                    # Проверяем наличие непустого connect
                    connect = current_base.get('Connect', '').strip()
                    if connect:  # Пропускаем записи с пустым connect
                        current_base['SectionName'] = current_section_name
                        bases.append(self._create_database(current_base))
            
            # Сортируем: сначала недавние (по времени запуска, самые свежие первыми), потом по папкам и OrderInTree
            bases.sort(key=lambda x: (
                not x.is_recent,  # Недавние в начало
                -(x.last_run_time.timestamp() if x.last_run_time else 0),  # Свежие запуски первыми (обратная сортировка)
                x.folder,  # Потом по папкам
                x.order_in_tree or 0  # И по OrderInTree
            ))
                    
        except Exception as e:
            print(f"❌ Ошибка при чтении файла: {e}")
            return []
        
        return bases
    
    def _create_database(self, data: dict) -> Database1C:
        """Создает объект Database1C из словаря"""
        # Преобразуем OrderInTree в float
        order_in_tree = None
        if 'OrderInTree' in data:
            try:
                order_in_tree = float(data['OrderInTree'])
            except ValueError:
                pass
        
        # Парсим IsRecent (1 или true = True, остальное = False)
        is_recent = False
        if 'IsRecent' in data:
            is_recent_value = data['IsRecent'].strip().lower()
            is_recent = is_recent_value in ['1', 'true', 'yes']
        
        # Парсим LastRunTime
        last_run_time = None
        if 'LastRunTime' in data:
            try:
                # Формат: ISO 8601 (например, "2025-11-20T08:30:15")
                last_run_time = datetime.fromisoformat(data['LastRunTime'])
            except ValueError:
                pass
        
        return Database1C(
            id=data.get('ID', ''),
            name=data.get('SectionName', 'Без имени'),  # Имя из [секции]
            folder=data.get('Folder', ''),
            connect=data.get('Connect', ''),
            app=data.get('App', None),
            version=data.get('Version', None),
            app_arch=data.get('AppArch', None),  # Разрядность
            order_in_tree=order_in_tree,
            usr=data.get('Usr', None),  # Пользователь (старое поле)
            pwd=data.get('Pwd', None),  # Пароль (старое поле)
            original_folder=data.get('OriginalFolder', None),  # Оригинальная папка (читаем, но не сохраняем)
            is_recent=is_recent,  # Флаг недавних
            last_run_time=last_run_time,  # Время последнего запуска
            # Новые поля для таблицы учетных данных
            usr_enterprise=data.get('UsrEnterprise', None),
            pwd_enterprise=data.get('PwdEnterprise', None),
            usr_configurator=data.get('UsrConfigurator', None),
            pwd_configurator=data.get('PwdConfigurator', None),
            usr_storage=data.get('UsrStorage', None),
            pwd_storage=data.get('PwdStorage', None),
            storage_path=data.get('StoragePath', None),
        )
    
    def print_bases_list(self, bases: List[Database1C]):
        """Выводит список баз в читаемом формате"""
        if not bases:
            print("📋 Список баз пуст")
            return
        
        print(f"\n{'='*60}")
        print(f"📋 Найдено баз: {len(bases)}")
        print(f"{'='*60}\n")
        
        for i, base in enumerate(bases, 1):
            print(f"{i}. {base.name}")
            print(f"   Папка: {base.get_folder_path()}")
            print(f"   Тип: {base.get_connection_type()}")
            print(f"   Подключение: {base.connect}")
            print(f"   Версия: {base.get_full_version()}")
            print()
