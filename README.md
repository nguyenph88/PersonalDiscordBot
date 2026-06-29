# PersonalDiscordBot
Just a personal discord bot for my things, build on top of the discord bot by AlexF

## Setup

### Environment Variables

1. **Create the .env file** (choose one method):
   
   **Option A: Use the helper script**
   ```bash
   python create_env.py
   ```
   
   **Option B: Create manually**
   Create a `.env` file in the root directory with the following variables:

   ```env
   # Discord Bot Configuration
   DISCORD_TOKEN=your_discord_bot_token_here
   DISCORD_PREFIX=!
   DISCORD_OWNER_ID=your_discord_user_id_here
   DISCORD_JOIN_MESSAGE=Thanks for adding me to your server!

   # Discord Bot Activity
   DISCORD_ACTIVITY_NAME=!help
   DISCORD_ACTIVITY_TYPE=playing
   DISCORD_STATUS_TYPE=online
   ```

2. **Edit the .env file** with your actual values:
   - `DISCORD_TOKEN`: Your Discord bot token from Discord Developer Portal
   - `DISCORD_OWNER_ID`: Your Discord user ID

## Running the Bot

### Option 1: Docker (Recommended)

**Prerequisites:**
- Docker and Docker Compose installed
- `.env` file configured

**Quick Start:**
```bash
# Build and start the bot
docker-compose up -d

# View logs
docker-compose logs -f

# Stop the bot
docker-compose down

# Rebuild and restart (for code changes)
docker-compose up --build -d
```

**Troubleshooting:**
```bash
# Force recreate container
docker-compose up -d --force-recreate

# Full restart
docker-compose down
docker-compose up -d

# Check container status
docker-compose ps

# View detailed logs
docker-compose logs -f --tail=100
```

### Option 2: Local Python

**Prerequisites:**
- Python 3.8+
- Google Chrome (for Steam functionality)
- ChromeDriver (automatically managed by webdriver-manager)

**Setup:**
```bash
# Install dependencies
pip install -r requirements.txt

# Run the bot
python index.py
```

## Commands

### Steam Commands (Prefix: !Steam)

- `!Steam login <username> <password>` - Login to Steam web interface
- `!Steam activate <key1,key2;key3>` - Activate product key(s) (supports multiple keys separated by comma or semicolon)
- `!Steam quit` - Close browser session
- `!Steam list` - Show active session status

**Steam Features:**
- **Headless Chrome Automation**: Uses Selenium with headless Chrome for reliable Steam web interaction
- **Multi-Factor Authentication**: Supports email verification codes and Steam Mobile App approval
- **Product Key Activation**: Automatically activates Steam product keys with error handling
- **Session Management**: Maintains browser session for multiple operations
- **Multiple Key Support**: Activate multiple keys with automatic delays between activations

## Features

### Steam Integration

The bot includes comprehensive Steam functionality:

- **Secure Login**: Uses headless Chrome browser automation for reliable Steam web login
- **Authentication Handling**: Supports various Steam authentication methods:
  - Email verification codes (5-character codes)
  - Steam Mobile App approval
  - CAPTCHA detection
- **Product Key Management**: 
  - Activate single or multiple product keys
  - Automatic error detection and reporting
  - Game name extraction on successful activation
  - Support for comma/semicolon separated key lists
- **Session Persistence**: Maintains browser session for efficient multiple operations
- **Cross-Platform**: Works on Windows, Linux, and macOS via Docker

## Technical Details

### Dependencies

**Core:**
- `discord.py` - Discord bot framework
- `python-dotenv` - Environment variable management
- `psutil` - System utilities

**Steam Integration:**
- `selenium>=4.15.0` - Web browser automation
- `webdriver-manager>=4.0.0` - Automatic ChromeDriver management

### Docker Configuration

The Docker setup includes:
- **Python 3.10-slim** base image
- **Google Chrome** installation for Selenium automation
- **Volume mounts** for live code development
- **Health checks** for container monitoring
- **Environment variables** for headless Chrome display

### File Structure

```
PersonalDiscordBot/
├── cogs/                    # Discord bot command modules
│   ├── admin.py            # Administrative commands
│   ├── discord.py          # Discord-specific commands
│   ├── encryption.py       # Encryption/encoding utilities
│   ├── events.py           # Event handlers
│   ├── fun.py              # Fun commands
│   ├── info.py             # Information commands
│   ├── mod.py              # Moderation commands
│   └── steam.py            # Steam integration commands
├── utils/                   # Utility modules
│   ├── config.py           # Configuration management
│   ├── data.py             # Data handling utilities
│   ├── default.py          # Default settings
│   └── permissions.py      # Permission management
├── docker-compose.yml       # Docker orchestration
├── Dockerfile              # Docker image definition
├── requirements.txt         # Python dependencies
├── index.py                # Main bot entry point
└── README.md               # This file
```
