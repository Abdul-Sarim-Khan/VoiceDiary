#!/usr/bin/env python3
"""VoiceDiary — Development Runner.
VoiceDiary © Abdul Sarim Khan. All Rights Reserved.
"""
import os
import sys

# Ensure src directory is in sys.path
ROOT = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(ROOT, 'src')
if SRC not in sys.path:
    sys.path.insert(0, SRC)

if __name__ == '__main__':
    if sys.platform == 'win32':
        import ctypes
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('abdulsarimkhan.voicediary.app.1.2.0')
        except Exception:
            pass

    from main import main
    main()
