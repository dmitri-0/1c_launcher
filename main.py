from config import IBASES_PATH, ENCODING
from services.base_reader import BaseReader

def main():
    """Главная функция запуска лончера"""
    print("🚀 Лончер баз 1С")
    print(f"📂 Путь к файлу: {IBASES_PATH}\n")
    
    # Создаем сервис для чтения баз
    reader = BaseReader(IBASES_PATH, ENCODING)
    
    # Читаем список баз
    bases = reader.read_bases()
    
    # Выводим список на экран
    reader.print_bases_list(bases)

if __name__ == "__main__":
    main()
