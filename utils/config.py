from dataclasses import dataclass
from dotenv import dotenv_values
import os


@dataclass
class Config:
    """
    This class is used to store the bot's configuration.
    You can load it from a dictionary or from a .env file (recommended).
    By default in this Discord bot template, we use from_env classmethod.
    """
    discord_token: str
    discord_prefix: str
    discord_owner_id: int
    discord_join_message: str

    discord_activity_name: str
    discord_activity_type: str
    discord_status_type: str
    
    # AllDebrid API configuration
    alldebrid_api_key: str = None
    
    # Channel management configuration
    request_channel_name: str = None
    request_channel_purge_hours: int = None
    
    # Crypto trading channel names
    crypto_day_trade_channel: str = "day-trade"
    crypto_swing_trade_channel: str = "swing-trade"
    crypto_long_term_trade_channel: str = "long-term-trade"
    
    # Crypto trading strategy coin configurations
    crypto_day_strategy_coins: str = "AVAX-USD,SOL-USD,ADA-USD,GRT-USD,CRV-USD"
    crypto_swing_strategy_coins: str = "MATIC-USD,QNT-USD,LCX-USD"
    crypto_long_strategy_coins: str = "AVAX-USD,CHZ-USD,ICP-USD"
    
    # Virtual trader channel
    virtual_trader_channel: str = "virtual-trader"
    
    # Virtual trader database configuration
    virtual_trader_database_type: str = "sqlite"
    virtual_trader_database_port: int = 3306
    virtual_trader_database_host: str = "127.0.0.1"
    virtual_trader_database_name: str = "virtualtrader"
    virtual_trader_database_user: str = "trader"
    virtual_trader_database_password: str = ""
    
    # Virtual trader strategy coin configurations
    virtual_trader_day_strategy_coins: str = "AVAX-USD,SOL-USD,ADA-USD,GRT-USD,CRV-USD"
    virtual_trader_swing_strategy_coins: str = "MATIC-USD,QNT-USD,LCX-USD"
    virtual_trader_long_strategy_coins: str = "AVAX-USD,CHZ-USD,ICP-USD"

    @classmethod
    def from_dict(self, **kwargs) -> "Config":
        """ Create a Config object from a dictionary. """
        kwargs_overwrite = {}

        for k, v in kwargs.items():
            # Convert environment variable names to dataclass field names
            if k == "REQUEST_CHANNEL_NAME":
                new_key = "request_channel_name"
            elif k == "REQUEST_CHANNEL_PURGE_HOURS":
                new_key = "request_channel_purge_hours"
            else:
                new_key = k.lower()

            if v.isdigit():
                kwargs_overwrite[new_key] = int(v)
            else:
                kwargs_overwrite[new_key] = v

        return Config(**kwargs_overwrite)

    @classmethod
    def from_env(self, filename: str = ".env") -> "Config":
        """ Create a Config object from a .env file. """
        # Check if .env file exists
        if not os.path.exists(filename):
            print(f"Warning: {filename} file not found. Please create it with the required environment variables.")
            print("Required variables: DISCORD_TOKEN, DISCORD_PREFIX, DISCORD_OWNER_ID, DISCORD_JOIN_MESSAGE, DISCORD_ACTIVITY_NAME, DISCORD_ACTIVITY_TYPE, DISCORD_STATUS_TYPE")
            print("Optional variables: ALLDEBRID_API_KEY, REQUEST_CHANNEL_NAME, REQUEST_CHANNEL_PURGE_HOURS, CRYPTO_DAY_TRADE_CHANNEL, CRYPTO_SWING_TRADE_CHANNEL, CRYPTO_LONG_TERM_TRADE_CHANNEL, CRYPTO_DAY_STRATEGY_COINS, CRYPTO_SWING_STRATEGY_COINS, CRYPTO_LONG_STRATEGY_COINS, VIRTUAL_TRADER_CHANNEL, VIRTUAL_TRADER_DATABASE_TYPE, VIRTUAL_TRADER_DATABASE_PORT, VIRTUAL_TRADER_DATABASE_HOST, VIRTUAL_TRADER_DATABASE_NAME, VIRTUAL_TRADER_DATABASE_USER, VIRTUAL_TRADER_DATABASE_PASSWORD, VIRTUAL_TRADER_DAY_STRATEGY_COINS, VIRTUAL_TRADER_SWING_STRATEGY_COINS, VIRTUAL_TRADER_LONG_STRATEGY_COINS")
            raise FileNotFoundError(f"{filename} file not found. Please create it with the required environment variables.")
        
        return Config.from_dict(**dotenv_values(filename))
