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
   ```

2. **Edit the .env file** with your actual values:
   - `DISCORD_TOKEN`: Your Discord bot token from Discord Developer Portal
   - `DISCORD_OWNER_ID`: Your Discord user ID
   - `ALLDEBRID_API_KEY`: Your AllDebrid API key (optional, for download features)

### AllDebrid API Setup

1. Get your API key from [AllDebrid](https://alldebrid.com/)
2. Add your API key to the `.env` file as `ALLDEBRID_API_KEY`
3. Use the `!AD status` command to verify your API authentication

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

### Basic Commands

- `!download` - Basic download command (legacy)
- `!help` - Show help information
