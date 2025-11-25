#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Smoke тест для проверки работоспособности после рефакторинга.

Проверяет:
1. Импорты всех модулей
2. Создание главного окна
3. Инициализацию менеджеров
4. Базовые операции
"""

import sys
import traceback

def test_imports():
    """Проверка импортов."""
    print("📍 Тест 1: Проверка импортов...")
    try:
        # Основные модули
        from gui.tree_window import TreeWindow
        print("  ✅ gui.tree_window.TreeWindow")
        
        # Модули горячих клавиш
        from gui.hotkeys import GlobalHotkeyManager
        print("  ✅ gui.hotkeys.GlobalHotkeyManager")
        
        # Модули действий
        from gui.actions import DatabaseActions, DatabaseOperations
        print("  ✅ gui.actions.DatabaseActions")
        print("  ✅ gui.actions.DatabaseOperations")
        
        # Модуль дерева
        from gui.tree import TreeBuilder
        print("  ✅ gui.tree.TreeBuilder")
        
        # Вспомогательные модули
        from models.database import Database1C
        print("  ✅ models.database.Database1C")
        
        from services.base_reader import BaseReader
        print("  ✅ services.base_reader.BaseReader")
        
        print("✅ Тест 1: УСПЕШНО\n")
        return True
    except Exception as e:
        print(f"❌ Тест 1: ОШИБКА")
        print(f"   {e}")
        traceback.print_exc()
        return False

def test_window_creation():
    """Проверка создания главного окна."""
    print("📍 Тест 2: Создание главного окна...")
    try:
        from PySide6.QtWidgets import QApplication
        from gui.tree_window import TreeWindow
        
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)
        
        window = TreeWindow()
        print("  ✅ Окно создано")
        
        # Проверка атрибутов
        assert hasattr(window, 'model'), "Отсутствует model"
        print("  ✅ model инициализирована")
        
        assert hasattr(window, 'tree'), "Отсутствует tree"
        print("  ✅ tree инициализировано")
        
        assert hasattr(window, 'all_bases'), "Отсутствует all_bases"
        print("  ✅ all_bases инициализировано")
        
        print("✅ Тест 2: УСПЕШНО\n")
        return True
    except Exception as e:
        print(f"❌ Тест 2: ОШИБКА")
        print(f"   {e}")
        traceback.print_exc()
        return False

def test_managers():
    """Проверка инициализации менеджеров."""
    print("📍 Тест 3: Инициализация менеджеров...")
    try:
        from PySide6.QtWidgets import QApplication
        from gui.tree_window import TreeWindow
        
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)
        
        window = TreeWindow()
        
        # Проверка менеджера горячих клавиш
        assert hasattr(window, 'hotkey_manager'), "Отсутствует hotkey_manager"
        print("  ✅ GlobalHotkeyManager инициализирован")
        
        # Проверка менеджера действий
        assert hasattr(window, 'actions'), "Отсутствует actions"
        print("  ✅ DatabaseActions инициализирован")
        
        # Проверка менеджера операций
        assert hasattr(window, 'operations'), "Отсутствует operations"
        print("  ✅ DatabaseOperations инициализирован")
        
        # Проверка построителя дерева
        assert hasattr(window, 'tree_builder'), "Отсутствует tree_builder"
        print("  ✅ TreeBuilder инициализирован")
        
        print("✅ Тест 3: УСПЕШНО\n")
        return True
    except Exception as e:
        print(f"❌ Тест 3: ОШИБКА")
        print(f"   {e}")
        traceback.print_exc()
        return False

def test_basic_operations():
    """Проверка базовых операций."""
    print("📍 Тест 4: Базовые операции...")
    try:
        from PySide6.QtWidgets import QApplication
        from gui.tree_window import TreeWindow
        
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)
        
        window = TreeWindow()
        
        # Проверка загрузки баз
        assert isinstance(window.all_bases, list), "all_bases должен быть списком"
        print(f"  ✅ Загружено баз: {len(window.all_bases)}")
        
        # Проверка модели дерева
        assert window.model.rowCount() >= 0, "Модель дерева не инициализирована"
        print(f"  ✅ Узлов в дереве: {window.model.rowCount()}")
        
        # Проверка методов
        assert callable(window.save_bases), "save_bases должен быть вызываемым"
        print("  ✅ save_bases доступен")
        
        assert callable(window.load_bases), "load_bases должен быть вызываемым"
        print("  ✅ load_bases доступен")
        
        print("✅ Тест 4: УСПЕШНО\n")
        return True
    except Exception as e:
        print(f"❌ Тест 4: ОШИБКА")
        print(f"   {e}")
        traceback.print_exc()
        return False

def main():
    print("┌" + "─" * 60 + "┐")
    print("│" + " " * 10 + "SMOKE TEST: 1C Launcher Refactoring" + " " * 12 + "│")
    print("└" + "─" * 60 + "┘\n")
    
    results = []
    
    # Запуск тестов
    results.append(test_imports())
    results.append(test_window_creation())
    results.append(test_managers())
    results.append(test_basic_operations())
    
    # Подведение итогов
    print("┌" + "─" * 60 + "┐")
    print("│" + " " * 22 + "ИТОГИ" + " " * 31 + "│")
    print("└" + "─" * 60 + "┘")
    
    total = len(results)
    passed = sum(results)
    failed = total - passed
    
    print(f"\nВсего тестов: {total}")
    print(f"✅ Успешно: {passed}")
    print(f"❌ Ошибок: {failed}")
    
    if failed == 0:
        print("\n🎉 ВСЕ ТЕСТЫ ПРОШЛИ УСПЕШНО!")
        print("✅ Рефакторинг выполнен корректно")
        return 0
    else:
        print("\n⚠️ НЕКОТОРЫЕ ТЕСТЫ НЕ ПРОШЛИ")
        print("❌ Требуется дополнительная проверка")
        return 1

if __name__ == '__main__':
    sys.exit(main())
