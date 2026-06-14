"""
AutoCommenter entry point.

Launch modes:
  python app_ac.py              → GUI mode (normal, requires license + Campaign Server)
  python app_ac.py --test       → GUI mode with local CSVs (no license, no server needed)
                                  (disabled in packaged .exe builds)
"""

__version__ = "1.0.0"

if __name__ == "__main__":
    import sys
    import os

    # Detect if running as a packaged PyInstaller exe
    _is_frozen = getattr(sys, 'frozen', False)

    test_mode = "--test" in sys.argv
    if test_mode:
        if _is_frozen:
            # Test mode is disabled in packaged builds
            print("Error: --test mode is not available in the packaged application.")
            sys.exit(1)
        sys.argv.remove("--test")

    from gui_ac import main
    main(test_mode=test_mode)
