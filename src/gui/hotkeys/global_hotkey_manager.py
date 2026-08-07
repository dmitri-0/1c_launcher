"""Менеджер глобальных горячих клавиш для Windows.

Предоставляет функционал регистрации и обработки глобальных горячих клавиш
через Windows API.
"""

import platform

from config import GLOBAL_HOTKEY_MODIFIERS, GLOBAL_HOTKEY_VK

# Проверка доступности Windows API для глобальных горячих клавиш
if platform.system() == 'Windows':
    try:
        import ctypes
        from ctypes import wintypes
        WINDOWS_HOTKEY_AVAILABLE = True

        # Явные сигнатуры Windows API: HWND — pointer-size (64 бита), иначе
        # ctypes конвертирует большой hwnd в c_int → OverflowError.
        _USER32 = ctypes.windll.user32
        _USER32.RegisterHotKey.argtypes = [
            wintypes.HWND, ctypes.c_int, ctypes.c_uint, ctypes.c_uint
        ]
        _USER32.RegisterHotKey.restype = wintypes.BOOL
        _USER32.UnregisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int]
        _USER32.UnregisterHotKey.restype = wintypes.BOOL
        _USER32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
        _USER32.SetForegroundWindow.argtypes = [wintypes.HWND]
        _USER32.SetForegroundWindow.restype = wintypes.BOOL
    except ImportError:
        WINDOWS_HOTKEY_AVAILABLE = False
        print("⚠️ Предупреждение: ctypes/wintypes недоступны. Глобальные горячие клавиши будут отключены.")
else:
    WINDOWS_HOTKEY_AVAILABLE = False


class GlobalHotkeyManager:
    """Управление глобальными горячими клавишами Windows.

    Комбинация (модификаторы + VK) настраивается во внешнем файле
    src/launcher.toml ([hotkey]) и читается динамически — без пересборки.

    Attributes:
        HOTKEY_ID: Уникальный идентификатор горячей клавиши
        HOTKEY_MODIFIERS: Модификаторы (из config)
        HOTKEY_VK: Виртуальный код клавиши (из config)
    """

    HOTKEY_ID = 1

    def __init__(self, window):
        """Инициализация менеджера.

        Args:
            window: Объект QMainWindow для которого регистрируются горячие клавиши
        """
        self.window = window
        self.hotkey_registered = False
        # Комбинация читается из launcher.toml — меняется без пересборки
        self.HOTKEY_MODIFIERS = GLOBAL_HOTKEY_MODIFIERS
        self.HOTKEY_VK = GLOBAL_HOTKEY_VK
    
    def register(self):
        """Регистрирует глобальную горячую клавишу для вызова окна.

        Комбинация настраивается в launcher.toml ([hotkey]) рядом с exe
        и читается динамически — правка кода/пересборка не требуется.
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
                key_name = self.get_hotkey_name()
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

        Если в данный момент идёт ожидание закрытия процесса (после Del), глобальная
        клавиша работает как «аварийный сброс»: прерывает ожидание — пользователь
        передумал закрывать 1С (запрос WM_CLOSE уже отправлен, но окно 1С может
        остаться живым, и к нему можно вернуться).

        Использует метод show_from_tray() из TreeWindow, который корректно обрабатывает
        скрытое или свернутое состояние окна.
        """
        # Аварийный сброс ожидания закрытия процесса (Del) — глобальная клавиша
        if getattr(self.window, "_close_wait_active", False):
            abort_event = getattr(self.window, "_close_wait_abort", None)
            if abort_event is not None:
                abort_event.set()
            print("⏹️ Глобальная клавиша: ожидание закрытия прервано (аварийный сброс)")
            return

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
    
    def get_hotkey_name(self):
        """Возвращает читаемое название горячей клавиши (из config, динамически)."""
        modifiers = []
        if self.HOTKEY_MODIFIERS & 0x0008:
            modifiers.append("Win")
        if self.HOTKEY_MODIFIERS & 0x0001:
            modifiers.append("Alt")
        if self.HOTKEY_MODIFIERS & 0x0002:
            modifiers.append("Ctrl")
        if self.HOTKEY_MODIFIERS & 0x0004:
            modifiers.append("Shift")

        # Читаемые имена для VK-кодов (любая клавиша из config получает имя)
        key_names = {}
        for i in range(10):
            key_names[0x30 + i] = str(i)
        for i in range(26):
            key_names[0x41 + i] = chr(ord("A") + i)
        for i in range(1, 13):
            key_names[0x70 + i - 1] = f"F{i}"
        key_names[0xC0] = "`"
        key = key_names.get(self.HOTKEY_VK, f"VK_{hex(self.HOTKEY_VK)}")

        return "+".join(modifiers + [key])
