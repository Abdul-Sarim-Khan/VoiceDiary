"""VoiceDiary — Classroom Lecture & Speaker Diarization Engine.
VoiceDiary © Abdul Sarim Khan. All Rights Reserved.
"""
import sys
import os
import multiprocessing
import logging


def get_resource_path(relative_path):
    """Get absolute path to resource, works for dev and PyInstaller."""
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), relative_path)


def setup_logging():
    """Configure application logging to file and console without duplicate handlers."""
    from config import get_app_data_dir
    log_dir = get_app_data_dir() / 'logs'
    log_dir.mkdir(parents=True, exist_ok=True)

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    # Clear any existing handlers to prevent duplicate lines in console
    if root_logger.handlers:
        root_logger.handlers.clear()

    formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(name)s: %(message)s')

    file_handler = logging.FileHandler(str(log_dir / 'voicediary.log'), encoding='utf-8')
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)
    root_logger.addHandler(stream_handler)


def main():
    """Launch the VoiceDiary application."""
    multiprocessing.freeze_support()

    # Add src directory to Python path
    src_dir = os.path.dirname(os.path.abspath(__file__))
    if src_dir not in sys.path:
        sys.path.insert(0, src_dir)

    # Windows AppUserModelID & Taskbar icon configuration
    if sys.platform == 'win32':
        import ctypes
        try:
            myappid = 'abdulsarimkhan.voicediary.app.1.2.0'
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
        except Exception:
            pass

    setup_logging()
    logger = logging.getLogger('VoiceDiary')
    logger.info('Starting VoiceDiary © Abdul Sarim Khan...')

    try:
        from config import APP_NAME, APP_VERSION, PROJECT_ROOT, ensure_dirs
        ensure_dirs()

        from ui.bridge import Api
        import webview
        import threading
        import time

        api = Api()
        gui_dir = get_resource_path('ui/static')
        window_title = f'{APP_NAME} — Bilingual Lecture & Diarization Engine v{APP_VERSION}'

        # Locate application icon
        icon_path = get_resource_path('ui/static/assets/icon.ico')
        if not os.path.isfile(icon_path):
            icon_path = os.path.join(src_dir, 'ui', 'static', 'assets', 'icon.ico')

        window = webview.create_window(
            window_title,
            url=os.path.join(gui_dir, 'index.html'),
            js_api=api,
            width=1280,
            height=820,
            min_size=(960, 640),
            background_color='#080C14',
            text_select=True,
        )
        api.set_window(window)

        # Background thread to set Win32 Taskbar and Titlebar icon
        def set_win32_taskbar_icon():
            if sys.platform != 'win32' or not os.path.isfile(icon_path):
                return
            for _ in range(20):  # retry until window is fully rendered
                time.sleep(0.2)
                try:
                    import ctypes
                    user32 = ctypes.windll.user32
                    hwnd = user32.FindWindowW(None, window_title)
                    if hwnd:
                        IMAGE_ICON = 1
                        LR_LOADFROMFILE = 0x00000010
                        LR_DEFAULTSIZE = 0x00000040
                        hicon = user32.LoadImageW(None, icon_path, IMAGE_ICON, 0, 0, LR_LOADFROMFILE | LR_DEFAULTSIZE)
                        if hicon:
                            WM_SETICON = 0x0080
                            ICON_SMALL = 0
                            ICON_BIG = 1
                            user32.SendMessageW(hwnd, WM_SETICON, ICON_SMALL, hicon)
                            user32.SendMessageW(hwnd, WM_SETICON, ICON_BIG, hicon)
                            logger.info("Custom taskbar and title icon applied successfully.")
                            break
                except Exception as ex:
                    logger.debug("Taskbar icon set: %s", ex)

        threading.Thread(target=set_win32_taskbar_icon, daemon=True).start()

        logger.info('Launching GUI window...')
        webview.start(debug=False, http_server=True)
        logger.info('VoiceDiary closed.')

    except Exception as e:
        import traceback
        err_msg = traceback.format_exc()
        logger.critical('Fatal startup error:\n%s', err_msg)
        try:
            from config import get_app_data_dir
            crash_log = get_app_data_dir() / 'logs' / 'crash.log'
            crash_log.parent.mkdir(parents=True, exist_ok=True)
            crash_log.write_text(err_msg, encoding='utf-8')
        except Exception:
            pass

        if sys.platform == 'win32':
            try:
                import ctypes
                from config import get_app_data_dir
                ctypes.windll.user32.MessageBoxW(
                    0,
                    f"Failed to start VoiceDiary:\n\n{e}\n\nPlease check logs at:\n{get_app_data_dir() / 'logs'}",
                    "VoiceDiary Startup Error",
                    0x10
                )
            except Exception:
                pass
        sys.exit(1)


if __name__ == '__main__':
    main()
