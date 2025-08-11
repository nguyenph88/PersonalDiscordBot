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

## Commands

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
