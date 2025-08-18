# PersonalDiscordBot
Just a personal discord bot for my things

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

   # AllDebrid API Configuration (Optional)
   ALLDEBRID_API_KEY=your_alldebrid_api_key_here

   # Channel Management Configuration (Optional)
   REQUEST_CHANNEL_NAME=your_channel_name_here
   REQUEST_CHANNEL_PURGE_HOURS=6
   ```

2. **Edit the .env file** with your actual values:
   - `DISCORD_TOKEN`: Your Discord bot token from Discord Developer Portal
   - `DISCORD_OWNER_ID`: Your Discord user ID
   - `ALLDEBRID_API_KEY`: Your AllDebrid API key (optional, for download features)
   - `REQUEST_CHANNEL_NAME`: Channel name for bot commands (optional)
   - `REQUEST_CHANNEL_PURGE_HOURS`: Hours between channel purges (0,1,2,3,4,6,12) - 0 disables auto-purge (optional)

### AllDebrid API Setup

1. Get your API key from [AllDebrid](https://alldebrid.com/)
2. Add your API key to the `.env` file as `ALLDEBRID_API_KEY`
3. Use the `!AD status` command to verify your API authentication

### Channel Management Setup

1. **Set up channel purging** (optional):
   - Set `REQUEST_CHANNEL_NAME` to the name of your bot command channel
   - Set `REQUEST_CHANNEL_PURGE_HOURS` to one of: 0, 1, 2, 3, 4, 6, 12
   - **0 disables auto-purge** - only manual purging via `!AD purge` will be available
   - **1-12 hours** - The bot will automatically purge the channel every specified hours starting at midnight PDT
   - Reminders will be sent hourly, and every 15 minutes in the final hour

2. **Bot permissions required**:
   - `Manage Messages` permission in the specified channel
   - The bot will automatically start the purge scheduler when loaded

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

**Development with Live Code Changes:**
```bash
# Start with volume mounts for live code changes
docker-compose up -d

# The bot will automatically reload when you modify files in:
# - cogs/ directory
# - utils/ directory
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

### AllDebrid Commands (Prefix: !AD)

- `!AD status` - Check AllDebrid API authentication status
- `!AD history <limit>` - Get download history (default: 10)
- `!AD supported_hosts` - List all supported hosts
- `!AD supported_host <name>` - Check if a specific host is supported
- `!AD download <link>` - Unlock a direct download link
- `!AD magnet_upload <magnet_uri>` - Upload a magnet URI and get magnet ID
- `!AD magnet_get_status <magnet_id>` - Check magnet status and information
- `!AD magnet_get_files <magnet_id>` - Get downloadable files for a magnet
- `!AD magnet_get <magnet_uri>` - Upload magnet and immediately check status
- `!AD magnet_search <url>` - Search for magnet URIs on a given URL
- `!AD purge` - Show channel purge information and allow manual purging

### Basic Commands

- `!download` - Basic download command (legacy)
- `!help` - Show help information

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

### Automatic Channel Purging

The bot includes an automatic channel purging system that:

- **Purges messages** from the specified channel at regular intervals
- **Uses Pacific Daylight Time (PDT)** for scheduling
- **Starts at midnight** and follows the specified hour interval
- **Sends reminders** hourly, and every 15 minutes in the final hour
- **Validates purge intervals** to only allow: 0, 1, 2, 3, 4, 6, or 12 hours (0 disables auto-purge)
- **Requires proper permissions** - the bot needs "Manage Messages" permission

**Example schedule with 6-hour purge:**
- Midnight PDT: Channel purged
- 6:00 AM PDT: Channel purged  
- 12:00 PM PDT: Channel purged
- 6:00 PM PDT: Channel purged
- Reminders sent at 5:00 AM, 11:00 AM, 5:00 PM, and every 15 minutes from 11:00 PM to midnight

**Auto-purge disabled (REQUEST_CHANNEL_PURGE_HOURS = 0):**
- No automatic purging occurs
- Only manual purging via `!AD purge` command is available
- No reminder messages are sent
- The `!AD purge` command will show that auto-purge is disabled

### Manual Channel Purging

The bot also supports manual channel purging:

- **`!AD purge` command** - Shows current purge configuration and next scheduled purge time
- **Interactive confirmation** - Users can react with 👍 to immediately purge the channel
- **Timeout handling** - If no reaction is received within 15 seconds, the operation is cancelled
- **Real-time information** - Displays channel name, purge interval, and time until next scheduled purge

## Technical Details

### Dependencies

**Core:**
- `discord.py` - Discord bot framework
- `python-dotenv` - Environment variable management

**Steam Integration:**
- `selenium>=4.15.0` - Web browser automation
- `webdriver-manager>=4.0.0` - Automatic ChromeDriver management

**AllDebrid Integration:**
- `requests` - HTTP client for API calls

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
│   ├── download.py         # Download and magnet functionality
│   ├── events.py           # Event handlers
│   ├── fun.py              # Fun commands
│   ├── info.py             # Information commands
│   ├── mod.py              # Moderation commands
│   └── steam.py            # Steam integration commands
├── utils/                   # Utility modules
│   ├── config.py           # Configuration management
│   ├── data.py             # Data handling utilities
│   ├── default.py          # Default settings
│   ├── http.py             # HTTP utilities
│   └── permissions.py      # Permission management
├── docker-compose.yml       # Docker orchestration
├── Dockerfile              # Docker image definition
├── requirements.txt         # Python dependencies
├── index.py                # Main bot entry point
└── README.md               # This file
```
