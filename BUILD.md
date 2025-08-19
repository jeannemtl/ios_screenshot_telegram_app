# Clean rebuild with the complete script
rm -rf build/ dist/ *.spec

# Build with watchdog support
pyinstaller --onedir \
    --windowed \
    --name "iOS Screenshot AI" \
    --hidden-import=watchdog \
    --hidden-import=watchdog.observers \
    --hidden-import=watchdog.events \
    --collect-all=watchdog \
    ios_screenshot_processor.py

# Test the new complete version
cd "dist/iOS Screenshot AI"
./iOS\ Screenshot\ AI

