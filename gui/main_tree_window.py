# ... (остальной код без изменений)
    def _launch_1c_process(self, executable, mode, database):
        """
        Универсальный метод запуска 1С
        mode: 'ENTERPRISE' или 'DESIGNER'
        """
        try:
            # Формируем параметры командной строки (всегда в кавычках)
            params = [mode]
            
            if database.connect:
                params.append(f'/S"{database.connect}"')
            if database.usr:
                params.append(f'/N"{database.usr}"')
            if database.pwd:
                params.append(f'/P"{database.pwd}"')
            
            # Формируем строку строго как в примере
            cmd_line = f'"{executable}" ' + ' '.join(params)
            
            print("\n" + "="*80)
            print(f"КОМАНДА ЗАПУСКА 1С ({mode}):")
            print(cmd_line)
            print("="*80 + "\n")
            
            if platform.system() == 'Windows':
                try:
                    import tempfile
                    with tempfile.NamedTemporaryFile(mode='w', suffix='.bat', delete=False, encoding='cp866') as bat_file:
                        bat_file.write('@echo off\n')
                        bat_file.write(f'start "" {cmd_line}\n')
                        bat_file.write('exit\n')
                        bat_path = bat_file.name
                    os.startfile(bat_path)
                    from PySide6.QtCore import QTimer
                    QTimer.singleShot(3000, lambda: self._cleanup_temp_file(bat_path))
                    return True
                except Exception as e:
                    print(f"МЕТОД 1 (os.startfile) не сработал: {e}")
                    try:
                        subprocess.Popen(
                            cmd_line,
                            shell=True,
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,
                            stdin=subprocess.DEVNULL,
                            creationflags=subprocess.CREATE_NEW_CONSOLE | subprocess.CREATE_BREAKAWAY_FROM_JOB
                        )
                        return True
                    except Exception as e2:
                        print(f"МЕТОД 2 (subprocess с shell) не сработал: {e2}")
                        command = [str(executable), mode]
                        if database.connect:
                            command.append(f'/S"{database.connect}"')
                        if database.usr:
                            command.append(f'/N"{database.usr}"')
                        if database.pwd:
                            command.append(f'/P"{database.pwd}"')
                        try:
                            subprocess.Popen(
                                command,
                                stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL,
                                stdin=subprocess.DEVNULL,
                                creationflags=subprocess.CREATE_NEW_CONSOLE
                            )
                            return True
                        except Exception as e3:
                            print(f"МЕТОД 3 (subprocess без detached) не сработал: {e3}")
                            raise e3
            else:
                command = [str(executable), mode]
                if database.connect:
                    command.append(f'/S"{database.connect}"')
                if database.usr:
                    command.append(f'/N"{database.usr}"')
                if database.pwd:
                    command.append(f'/P"{database.pwd}"')
                subprocess.Popen(
                    command,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    stdin=subprocess.DEVNULL
                )
                return True
        except Exception as e:
            print(f"ВСЕ МЕТОДЫ ЗАПУСКА НЕ СРАБОТАЛИ: {e}")
            import traceback
            traceback.print_exc()
            return False
# ... (остальной код без изменений)
