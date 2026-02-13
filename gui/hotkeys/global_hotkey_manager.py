"""Менеджер глобальных горячих клавиш для Windows.

Предоставляет функционал регистрации и обработки глобальных горячих клавиш
через Windows API.
"""

import platform

# Проверка доступности Windows API для глобальных горячих клавиш
if platform.system() == 'Windows':
    try:
        import ctypes
        from ctypes import wintypes
        WINDOWS_HOTKEY_AVAILABLE = True
    except ImportError:
        WINDOWS_HOTKEY_AVAILABLE = False
        print("⚠️ Предупреждение: ctypes/wintypes недоступны. Глобальные горячие клавиши будут отключены.")
else:
    WINDOWS_HOTKEY_AVAILABLE = False


class GlobalHotkeyManager:
    """Управление глобальными горячими клавишами Windows.
    
    Attributes:
        HOTKEY_ID: Уникальный идентификатор горячей клавиши
        HOTKEY_MODIFIERS: Модификаторы (Alt)
        HOTKEY_VK: Виртуальный код клавиши (тильда/ё)
    """
    
    # Константы для глобальной горячей клавиши
    HOTKEY_ID = 1
    # Ctrl (0x0002) + Alt (0x0001) + Shift (0x0004) = 0x0007
    HOTKEY_MODIFIERS = 0x0002 | 0x0004
    HOTKEY_VK = 0xC0  # VK_OEM_3 (клавиша тильды/ё)

    def __init__(self, window):
        """Инициализация менеджера.
        
        Args:
            window: Объект QMainWindow для которого регистрируются горячие клавиши
        """
        self.window = window
        self.hotkey_registered = False
    
    def register(self):
        """Регистрирует глобальную горячую клавишу для вызова окна.
        
        По умолчанию регистрируется Alt+Ё.
        Комбинацию можно изменить через константы HOTKEY_MODIFIERS и HOTKEY_VK.
        """
        if not WINDOWS_HOTKEY_AVAILABLE:
            return
        
        try:
            hwnd = int(self.window.winId())
            user32 = ctypes.windll.user32
            
            result = user32.RegisterHotKey(
                hwnd,
                self.HOTKEY_ID,
                self.HOTKEY_MODIFIERS,
                self.HOTKEY_VK
            )
            
            if result:
                self.hotkey_registered = True
                key_name = self._get_hotkey_name()
                print(f"✅ Глобальная горячая клавиша {key_name} зарегистрирована")
                self.window.statusBar.showMessage(f"✅ Горячая клавиша {key_name} активна", 3000)
            else:
                error_code = ctypes.get_last_error()
                print(f"⚠️ Не удалось зарегистрировать глобальную горячую клавишу (код ошибки: {error_code})")
                print("   Возможно, клавиша уже используется другим приложением.")
                
        except Exception as e:
            print(f"❌ Ошибка регистрации глобальной горячей клавиши: {e}")
            import traceback
            traceback.print_exc()
    
    def unregister(self):
        """Отменяет регистрацию глобальной горячей клавиши."""
        if not WINDOWS_HOTKEY_AVAILABLE or not self.hotkey_registered:
            return
        
        try:
            user32 = ctypes.windll.user32
            hwnd = int(self.window.winId())
            
            user32.UnregisterHotKey(hwnd, self.HOTKEY_ID)
            self.hotkey_registered = False
            print("✅ Глобальная горячая клавиша отменена")
            
        except Exception as e:
            print(f"❌ Ошибка отмены регистрации глобальной горячей клавиши: {e}")
    
    def handle_native_event(self, eventType, message):
        """Обрабатывает нативные события Windows для горячих клавиш.
        
        Args:
            eventType: Тип события
            message: Указатель на структуру MSG
            
        Returns:
            tuple: (handled, result) где handled - True если событие обработано
        """
        if WINDOWS_HOTKEY_AVAILABLE and eventType == "windows_generic_MSG":
            try:
                # Парсим структуру MSG из Windows
                msg = wintypes.MSG.from_address(int(message))
                
                # WM_HOTKEY = 0x0312
                if msg.message == 0x0312:
                    if msg.wParam == self.HOTKEY_ID:
                        # Активируем окно при нажатии нашей горячей клавиши
                        self.activate_window()
                        return True, 0
                        
            except Exception as e:
                print(f"❌ Ошибка обработки nativeEvent: {e}")
        
        return False, 0
    
    def activate_window(self):
        """Активирует и выводит окно на передний план.
        
        Использует метод show_from_tray() из TreeWindow, который корректно обрабатывает
        скрытое или свернутое состояние окна.
        """
        try:
            # Используем единый метод show_from_tray из TreeWindow
            self.window.show_from_tray()
            
            # Дополнительно используем Windows API для гарантированной активации
            if WINDOWS_HOTKEY_AVAILABLE:
                hwnd = int(self.window.winId())
                user32 = ctypes.windll.user32
                
                # SW_RESTORE = 9 (восстановить окно)
                user32.ShowWindow(hwnd, 9)
                # Устанавливаем окно на передний план
                user32.SetForegroundWindow(hwnd)
                
            print("✅ Окно активировано глобальной горячей клавишей")
            
        except Exception as e:
            print(f"❌ Ошибка активации окна: {e}")
    
    def _get_hotkey_name(self):
        """Возвращает читаемое название горячей клавиши."""
        modifiers = []
        if self.HOTKEY_MODIFIERS & 0x0008:
            modifiers.append("Win")
        if self.HOTKEY_MODIFIERS & 0x0001:
            modifiers.append("Alt")
        if self.HOTKEY_MODIFIERS & 0x0002:
            modifiers.append("Ctrl")
        if self.HOTKEY_MODIFIERS & 0x0004:
            modifiers.append("Shift")
        
        # Определяем название клавиши по VK коду
        key_names = {
            0x31: "1", 0x32: "2", 0x33: "3", 0x34: "4", 0x35: "5",
            0x36: "6", 0x37: "7", 0x38: "8", 0x39: "9", 0x30: "0",
            0xC0: "Ё"
        }
        key = key_names.get(self.HOTKEY_VK, f"VK_{hex(self.HOTKEY_VK)}")
        
        return "+".join(modifiers + [key])
