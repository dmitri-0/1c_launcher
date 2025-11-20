from pathlib import Path
from typing import List
from models.database import Database1C

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
                        # Сохраняем предыдущую базу, если она была
                        if current_base and current_section_name:
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
                
                # Добавляем последнюю базу, если есть
                if current_base and current_section_name:
                    current_base['SectionName'] = current_section_name
                    bases.append(self._create_database(current_base))
            
            # Сортируем: сначала недавние, потом по папкам и OrderInTree
            bases.sort(key=lambda x: (not x.is_recent, x.folder, x.order_in_tree or 0))
                    
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
        
        return Database1C(
            id=data.get('ID', ''),
            name=data.get('SectionName', 'Без имени'),  # Имя из [секции]
            folder=data.get('Folder', ''),
            connect=data.get('Connect', ''),
            app=data.get('App', None),
            version=data.get('Version', None),
            app_arch=data.get('AppArch', None),  # Разрядность
            order_in_tree=order_in_tree,
            usr=data.get('Usr', None),  # Пользователь
            pwd=data.get('Pwd', None),  # Пароль
            original_folder=data.get('OriginalFolder', None),  # Оригинальная папка
            is_recent=is_recent  # Флаг недавних
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
