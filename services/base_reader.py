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
        
        try:
            with open(self.ibases_path, 'r', encoding=self.encoding) as file:
                for line in file:
                    line = line.strip()
                    
                    # Пропускаем пустые строки
                    if not line:
                        # Если накоплена информация о базе, сохраняем её
                        if current_base and 'ID' in current_base:
                            bases.append(self._create_database(current_base))
                            current_base = {}
                        continue
                    
                    # Парсим параметры
                    if '=' in line:
                        key, value = line.split('=', 1)
                        current_base[key] = value
                
                # Добавляем последнюю базу, если есть
                if current_base and 'ID' in current_base:
                    bases.append(self._create_database(current_base))
                    
        except Exception as e:
            print(f"❌ Ошибка при чтении файла: {e}")
            return []
        
        return bases
    
    def _create_database(self, data: dict) -> Database1C:
        """Создает объект Database1C из словаря"""
        return Database1C(
            id=data.get('ID', ''),
            name=data.get('Folder', 'Без имени'),
            folder=data.get('Folder', ''),
            connect=data.get('Connect', ''),
            app=data.get('App', None),
            version=data.get('Version', None)
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
            print(f"   ID: {base.id}")
            print(f"   Тип: {base.get_connection_type()}")
            print(f"   Подключение: {base.connect}")
            if base.version:
                print(f"   Версия: {base.version}")
            print()
