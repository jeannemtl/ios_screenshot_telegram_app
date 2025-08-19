#!/bin/bash

# iOS Screenshot AI Build Script
# This script builds the macOS application using PyInstaller

echo "📱 iOS Screenshot AI - Build Script"
echo "=================================="

# Clean rebuild with the complete script
echo "🧹 Cleaning old build artifacts..."
rm -rf build/ dist/ *.spec

# Build with watchdog support
echo "🔨 Building application with PyInstaller..."
pyinstaller --onedir \
    --windowed \
    --name "iOS Screenshot AI" \
    --hidden-import=watchdog \
    --hidden-import=watchdog.observers \
    --hidden-import=watchdog.events \
    --collect-all=watchdog \
    ios_screenshot_processor.py

# Check if build was successful
if [ $? -eq 0 ]; then
    echo "✅ Build completed successfully!"
    echo "📍 Application location: dist/iOS Screenshot AI/"
    
    # Test the new complete version
    echo "🚀 Testing the built application..."
    cd "dist/iOS Screenshot AI"
    ./iOS\ Screenshot\ AI
else
    echo "❌ Build failed!"
    exit 1
fi
