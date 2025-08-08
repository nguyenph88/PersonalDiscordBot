#!/usr/bin/env python3
"""
Helper script to create a .env file template
"""

import os

def create_env_template():
    """Create a .env file template if it doesn't exist"""
    
    if os.path.exists('.env'):
        print("✅ .env file already exists!")
        return
    
    env_content = """# Discord Bot Configuration
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
"""
    
    try:
        with open('.env', 'w') as f:
            f.write(env_content)
        print("✅ Created .env file template!")
        print("📝 Please edit the .env file with your actual values:")
        print("   - DISCORD_TOKEN: Your Discord bot token")
        print("   - DISCORD_OWNER_ID: Your Discord user ID")
        print("   - ALLDEBRID_API_KEY: Your AllDebrid API key (optional)")
    except Exception as e:
        print(f"❌ Error creating .env file: {e}")

if __name__ == "__main__":
    create_env_template()
