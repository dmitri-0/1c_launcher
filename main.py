"""
Точка входа для консольной версии лончера
Для GUI версии используйте main_gui.py
"""
from config import IBASES_PATH, ENCODING
from services.base_reader import BaseReader

def main():
    """Главная функция запуска лончера (консольная версия)"""
    print("🚀 Лончер баз 1С (консольная версия)")
    print(f"📂 Путь к файлу: {IBASES_PATH}\n")
    print("Для GUI версии запустите: python main_gui.py\n")
    
    reader = BaseReader(IBASES_PATH, ENCODING)
    bases = reader.read_bases()
    reader.print_bases_list(bases)

if __name__ == "__main__":
    main()
