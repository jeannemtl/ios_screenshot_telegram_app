# iOS Screenshot AI

An intelligent macOS application that automatically processes and analyzes screenshots using AI, with optional Telegram integration for notifications.

## Features

- 🖥️ **Desktop Screenshot Monitoring**: Automatically detects new screenshots on your Mac
- 🤖 **AI-Powered Analysis**: Processes screenshots using Anthropic's Claude AI
- 📱 **Telegram Integration**: Optional notifications and sharing via Telegram bot
- 🌐 **Web Interface**: Local web server for configuration and management
- 🔄 **Real-time Processing**: Instant analysis of new screenshots
- 🛡️ **Privacy-First**: All processing happens locally and on your terms

## Requirements

### System Requirements
- macOS 10.15 (Catalina) or later
- Intel or Apple Silicon processor
- 100 MB free disk space

### Dependencies
- Python 3.8+ (for building from source)
- Flask
- Requests
- Watchdog

## Installation

### Option 1: Download Pre-built App (Recommended)
1. Download the latest `iOS-Screenshot-AI.dmg` from the releases page
2. Open the DMG file
3. Drag the app to your Applications folder
4. Launch from Applications (see Security Note below)

### Option 2: Build from Source

1. **Clone the repository:**
```bash
git clone https://github.com/jeannemtl/ios_screenshot_telegram_app.git
cd ios_screenshot_telegram_app
```

2. **Create virtual environment:**
```bash
python3 -m venv screenshot_app_env
source screenshot_app_env/bin/activate
```

3. **Install dependencies:**
```bash
pip install -r requirements.txt
```

4. **Build the application:**
```bash
Usethe commands in the BUILD.md
```

5. **Run the built app:**
```bash
cd "dist/iOS Screenshot AI"
./iOS\ Screenshot\ AI
```

## Security Note (macOS)

When first launching the app, macOS will show a security warning:
> "iOS Screenshot AI.app can't be opened because Apple cannot check it for malicious software."

**To allow the app:**
1. Click "OK" to dismiss the warning
2. Open **System Settings** → **Privacy & Security**
3. Click **"Open Anyway"** next to the blocked app message
4. Enter your password and launch the app again

## Configuration

On first launch, you'll be prompted to configure:

### Required
- **Anthropic API Key**: Get from [console.anthropic.com](https://console.anthropic.com)

### Optional
- **Telegram Bot Token**: Message @BotFather on Telegram, send `/newbot`
- **Telegram Chat ID**: Message @userinfobot on Telegram for your ID

## Usage

1. **Launch the app** from Applications
2. **Complete setup** with your API credentials
3. **Take screenshots** on your Mac (Cmd+Shift+4, Cmd+Shift+3, etc.)
4. **Screenshots are automatically processed** and analyzed
5. **View results** through the web interface or Telegram notifications

## Build Script Details

The application is built using PyInstaller with the following configuration:

```bash
pyinstaller --onedir \
    --windowed \
    --name "iOS Screenshot AI" \
    --hidden-import=watchdog \
    --hidden-import=watchdog.observers \
    --hidden-import=watchdog.events \
    --collect-all=watchdog \
    ios_screenshot_processor.py
```

## Development

### Project Structure
```
ios_screenshot_telegram_app/
├── ios_screenshot_processor.py    # Main application file
├── build_enhanced.sh             # Build script
├── requirements.txt              # Python dependencies
└── README.md                    # This file
```

### Running in Development
```bash
source screenshot_app_env/bin/activate
python ios_screenshot_processor.py
```

## Troubleshooting

### App Won't Start
- Ensure you've followed the security steps above
- Check Console.app for error messages
- Verify system requirements are met

### API Keys Not Working
- Verify API key is valid at [console.anthropic.com](https://console.anthropic.com)
- Check internet connection
- Ensure sufficient API credits

### Screenshots Not Detected
- Check if app has necessary permissions
- Verify screenshot location (usually ~/Desktop)
- Look for error messages in the app interface

### Telegram Not Working
- Verify bot token is correct
- Ensure chat ID is accurate
- Test bot independently by messaging it

## Privacy & Security

- All screenshot processing happens on your local machine
- API calls are made directly to Anthropic's servers
- No data is stored or transmitted without your explicit configuration
- Telegram integration is entirely
