import discord
from discord.ext import commands, tasks
import logging
import time
from tokenometry import Tokenometry

class TradingStrategy:
    """Base class for trading strategies"""
    def __init__(self, name, config, bot, logger, channel_name):
        self.name = name
        self.config = config
        self.bot = bot
        self.logger = logger
        self.channel_name = channel_name  # The full channel name to find
        self.channel = None
        self.scanner = None
        self.scanner_task = None
        
    async def find_channel(self, channel_name=None):
        """Find the trading channel in the guild"""
        # Use the configured channel name if none provided
        if channel_name is None:
            channel_name = self.channel_name
            
        for guild in self.bot.guilds:
            self.logger.info(f"Searching in guild: {guild.name}")
            for channel in guild.channels:
                if isinstance(channel, discord.TextChannel):
                    self.logger.info(f"Checking channel: {channel.name} for exact match: {channel_name}")
                    if channel.name.lower() == channel_name.lower():
                        self.channel = channel
                        self.logger.info(f"Found {self.name} channel: {channel.name}")
                        return True
                    else:
                        self.logger.info(f"Channel {channel.name} doesn't match {channel_name}")
        self.logger.warning(f"No channel found for {self.name} with name: {channel_name}")
        return False
    
    async def setup_scanner(self):
        """Initialize the Tokenometry scanner"""
        if not self.scanner:
            self.scanner = Tokenometry(config=self.config, logger=self.logger)
            self.logger.info(f"{self.name} Tokenometry scanner initialized")
    
    async def get_current_prices(self):
        """Get current prices for monitored assets"""
        try:
            if not self.scanner:
                return None
            
            prices = {}
            for product_id in self.config["PRODUCT_IDS"]:
                try:
                    data = self.scanner._get_historical_data(product_id, self.config["GRANULARITY_SIGNAL"])
                    if data is not None and not data.empty:
                        latest_price = data.iloc[-1]['Close']
                        prices[product_id] = latest_price
                except Exception as e:
                    self.logger.error(f"Error getting price for {product_id}: {e}")
                    continue
            
            return prices
        except Exception as e:
            self.logger.error(f"Error getting current prices: {e}")
            return None
    
    async def send_signals(self, signals):
        """Send trading signals to the channel"""
        if not self.channel:
            return
        
        embed = discord.Embed(
            title=f"🚀 {self.name} Signals",
            description=f"Found {len(signals)} actionable signals",
            color=self.get_embed_color(),
            timestamp=discord.utils.utcnow()
        )
        
        # Add current prices
        current_prices = await self.get_current_prices()
        if current_prices:
            price_text = "**Current Prices:**\n"
            for asset, price in current_prices.items():
                price_text += f"• {asset}: ${price:.2f}\n"
            embed.add_field(name="💰 Market Prices", value=price_text, inline=False)
        
        # Add signals
        for signal in signals:
            signal_text = f"**{signal['signal']}** {signal['asset']}\n"
            signal_text += f"Price: ${signal['close_price']:.2f}\n"
            signal_text += f"Trend: {signal['trend']}\n"
            
            if signal['trade_plan']:
                signal_text += f"Stop Loss: ${signal['trade_plan']['stop_loss']:.2f}\n"
                signal_text += f"Position Size: {signal['trade_plan']['position_size_crypto']:.6f} {signal['asset'].split('-')[0]}\n"
                signal_text += f"USD Value: ${signal['trade_plan']['position_size_usd']:.2f}"
            
            embed.add_field(
                name=f"{'🟢' if signal['signal'] == 'BUY' else '🔴'} {signal['asset']}",
                value=signal_text,
                inline=False
            )
        
        # Tag owner and send
        owner_mention = f"<@{self.bot.config.discord_owner_id}>"
        await self.channel.send(f"{owner_mention} 🚨 {self.name} signals detected!", embed=embed)
        
        # Send DM to owner
        await self.send_owner_dm(signals, current_prices)
    
    async def send_status_update(self, message):
        """Send a status update to the channel"""
        if not self.channel:
            return
        
        embed = discord.Embed(
            title=f"📊 {self.name} Status",
            description=message,
            color=discord.Color.blue(),
            timestamp=discord.utils.utcnow()
        )
        
        # Add current prices
        current_prices = await self.get_current_prices()
        if current_prices:
            price_text = "**Current Prices:**\n"
            for asset, price in current_prices.items():
                price_text += f"• {asset}: ${price:.2f}\n"
            embed.add_field(name="💰 Market Prices", value=price_text, inline=False)
        
        await self.channel.send(embed=embed)
    
    async def send_owner_dm(self, signals, current_prices):
        """Send a direct message to the bot owner"""
        try:
            owner = self.bot.get_user(self.bot.config.discord_owner_id)
            if not owner:
                self.logger.error("Could not find bot owner")
                return
            
            embed = discord.Embed(
                title=f"🚨 {self.name.upper()} SIGNALS",
                description=f"**{len(signals)} new {self.name.lower()} signals detected!**",
                color=discord.Color.red(),
                timestamp=discord.utils.utcnow()
            )
            
            # Add current prices
            if current_prices:
                price_text = "**Current Market Prices:**\n"
                for asset, price in current_prices.items():
                    price_text += f"• {asset}: ${price:.2f}\n"
                embed.add_field(name="💰 Prices", value=price_text, inline=False)
            
            # Add signal summary
            signal_summary = ""
            for signal in signals:
                emoji = "🟢" if signal['signal'] == 'BUY' else "🔴"
                signal_summary += f"{emoji} **{signal['signal']}** {signal['asset']} @ ${signal['close_price']:.2f}\n"
            
            embed.add_field(name="📊 Signals", value=signal_summary, inline=False)
            embed.set_footer(text=f"Check the {self.name.lower()}-trade channel for full details")
            
            await owner.send(embed=embed)
            self.logger.info(f"Sent {self.name} signal DM to owner {owner.name}")
            
        except Exception as e:
            self.logger.error(f"Error sending DM to owner: {e}")
    
    def get_embed_color(self):
        """Get the embed color for this strategy"""
        colors = {
            "Day Trader": discord.Color.green(),
            "Aggressive Swing Trader": discord.Color.blue(),
            "Long-Term Investor": discord.Color.purple()
        }
        return colors.get(self.config["STRATEGY_NAME"], discord.Color.blue())
    
    async def run_scan(self):
        """Run a scan and handle results"""
        self.logger.info(f"Running scan for {self.name}")
        
        if not self.channel:
            self.logger.info(f"No channel cached for {self.name}, searching...")
            if not await self.find_channel():
                self.logger.info(f"{self.name} channel not found, skipping scan")
                return
        
        self.logger.info(f"Found channel for {self.name}: {self.channel.name}")
        
        if not self.scanner:
            self.logger.info(f"Setting up scanner for {self.name}")
            await self.setup_scanner()
        
        # Send initial status message if this is the first scan
        if not hasattr(self, '_initial_status_sent'):
            await self.send_status_update(f"🟢 {self.name} scanner is now active and monitoring the market")
            self._initial_status_sent = True
        
        try:
            self.logger.info(f"Executing scan for {self.name}")
            signals = self.scanner.scan()
            self.logger.info(f"Scan completed for {self.name}, found {len(signals) if signals else 0} signals")
            
            if signals:
                await self.send_signals(signals)
            else:
                await self.send_status_update(f"No actionable {self.name.lower()} signals found")
                
        except Exception as e:
            self.logger.error(f"Error during {self.name.lower()} scan: {e}")
            await self.send_status_update(f"❌ {self.name} scan error: {str(e)}")

class CryptoCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.logger = logging.getLogger("CryptoBot")
        self.logger.setLevel(logging.INFO)
        
        # Strategy configurations
        self.strategies = self._create_strategies_from_env()
    
    def _get_product_ids_from_env(self, env_var_name: str, default_coins: list) -> list:
        """Get product IDs from environment variable with fallback to defaults"""
        try:
            # Get the environment variable value
            env_value = getattr(self.bot.config, env_var_name, None)
            
            if not env_value or env_value.strip() == "":
                print(f"📝 Using default coins for {env_var_name}: {default_coins}")
                return default_coins
            
            # Parse pipe-separated values
            coins = [coin.strip() for coin in env_value.split('|') if coin.strip()]
            
            print(f"📝 Parsed coins from {env_var_name}: {coins}")
            return coins if coins else default_coins
            
        except Exception as e:
            print(f"⚠️ Error parsing {env_var_name}: {e}. Using defaults: {default_coins}")
            return default_coins
    
    def _create_strategies_from_env(self):
        """Create strategy configurations with product IDs from environment variables"""
        return {
            "day": {
                "name": "Day Trader",
                "config": {
                    "STRATEGY_NAME": "Day Trader",
                    "PRODUCT_IDS": self._get_product_ids_from_env("crypto_day_strategy_coins", ["GRT-USD", "AVAX-USD", "CRV-USD"]),
                    "GRANULARITY_SIGNAL": "FIVE_MINUTE",
                    "GRANULARITY_TREND": "ONE_HOUR",
                    "GRANULARITY_SECONDS": {
                        "ONE_HOUR": 3600, 
                        "FIVE_MINUTE": 300, 
                        "ONE_DAY": 86400, 
                        "ONE_WEEK": 604800
                    },
                    "LOOKBACK_DAYS": 30,
                    "TREND_INDICATOR_TYPE": "EMA",
                    "TREND_PERIOD": 50,
                    "SIGNAL_INDICATOR_TYPE": "EMA",
                    "SHORT_PERIOD": 9,
                    "LONG_PERIOD": 21,
                    "RSI_PERIOD": 14, 
                    "RSI_OVERBOUGHT": 70, 
                    "RSI_OVERSOLD": 30,
                    "MACD_FAST": 12, 
                    "MACD_SLOW": 26, 
                    "MACD_SIGNAL": 9,
                    "ATR_PERIOD": 14,
                    "VOLUME_FILTER_ENABLED": True,
                    "VOLUME_MA_PERIOD": 20,
                    "VOLUME_SPIKE_MULTIPLIER": 2.0,
                    "HYPOTHETICAL_PORTFOLIO_SIZE": 100000.0,
                    "RISK_PER_TRADE_PERCENTAGE": 0.5,
                    "ATR_STOP_LOSS_MULTIPLIER": 2.0,
                },
                "interval": 5  # minutes
            },
            "swing": {
                "name": "Aggressive Swing Trader",
                "config": {
                    "STRATEGY_NAME": "Aggressive Swing Trader",
                    "PRODUCT_IDS": self._get_product_ids_from_env("crypto_swing_strategy_coins", ["GRT-USD", "AVAX-USD", "CRV-USD"]),
                    "GRANULARITY_SIGNAL": "FOUR_HOUR",
                    "GRANULARITY_TREND": "ONE_DAY",
                    "GRANULARITY_SECONDS": {
                        "ONE_HOUR": 3600, 
                        "FIVE_MINUTE": 300, 
                        "ONE_DAY": 86400, 
                        "FOUR_HOUR": 14400, 
                        "ONE_WEEK": 604800
                    },
                    "LOOKBACK_DAYS": 30,
                    "TREND_INDICATOR_TYPE": "EMA",
                    "TREND_PERIOD": 50,
                    "SIGNAL_INDICATOR_TYPE": "EMA",
                    "SHORT_PERIOD": 20,
                    "LONG_PERIOD": 50,
                    "RSI_PERIOD": 14, 
                    "RSI_OVERBOUGHT": 70, 
                    "RSI_OVERSOLD": 30,
                    "MACD_FAST": 12, 
                    "MACD_SLOW": 26, 
                    "MACD_SIGNAL": 9,
                    "ATR_PERIOD": 14,
                    "VOLUME_FILTER_ENABLED": True,
                    "VOLUME_MA_PERIOD": 20,
                    "VOLUME_SPIKE_MULTIPLIER": 1.5,
                    "HYPOTHETICAL_PORTFOLIO_SIZE": 100000.0,
                    "RISK_PER_TRADE_PERCENTAGE": 1.0,
                    "ATR_STOP_LOSS_MULTIPLIER": 2.5,
                },
                "interval": 4  # hours
            },
            "long": {
                "name": "Long-Term Investor",
                "config": {
                    "STRATEGY_NAME": "Long-Term Investor",
                    "PRODUCT_IDS": self._get_product_ids_from_env("crypto_long_strategy_coins", ["CRV-USD", "GRT-USD", "ADA-USD", "MATIC-USD"]),
                    "GRANULARITY_SIGNAL": "ONE_DAY",
                    "GRANULARITY_TREND": "ONE_WEEK",
                    "GRANULARITY_SECONDS": {
                        "ONE_HOUR": 3600, 
                        "FIVE_MINUTE": 300, 
                        "ONE_DAY": 86400, 
                        "FOUR_HOUR": 14400, 
                        "ONE_WEEK": 604800
                    },
                    "LOOKBACK_DAYS": 30,
                    "TREND_INDICATOR_TYPE": "SMA",
                    "TREND_PERIOD": 30,
                    "SIGNAL_INDICATOR_TYPE": "SMA",
                    "SHORT_PERIOD": 50,
                    "LONG_PERIOD": 200,
                    "RSI_PERIOD": 14, 
                    "RSI_OVERBOUGHT": 70, 
                    "RSI_OVERSOLD": 30,
                    "MACD_FAST": 12, 
                    "MACD_SLOW": 26, 
                    "MACD_SIGNAL": 9,
                    "ATR_PERIOD": 14,
                    "VOLUME_FILTER_ENABLED": True,
                    "VOLUME_MA_PERIOD": 20,
                    "VOLUME_SPIKE_MULTIPLIER": 1.5,
                    "HYPOTHETICAL_PORTFOLIO_SIZE": 100000.0,
                    "RISK_PER_TRADE_PERCENTAGE": 1.0,
                    "ATR_STOP_LOSS_MULTIPLIER": 2.5,
                },
                "interval": 24  # hours
            }
        }
        
        # Initialize strategy objects
        self.strategy_objects = {}
        for key, strategy_info in self.strategies.items():
            # Map strategy keys to configurable channel names
            channel_name_mapping = {
                "day": self.bot.config.crypto_day_trade_channel,
                "swing": self.bot.config.crypto_swing_trade_channel,
                "long": self.bot.config.crypto_long_term_trade_channel
            }
            channel_name = channel_name_mapping.get(key, f"{key}-trade")
            
            # Skip strategies with blank channel names
            if not channel_name or channel_name.strip() == "":
                self.logger.info(f"Skipping {strategy_info['name']} - no channel configured")
                continue
            
            self.strategy_objects[key] = TradingStrategy(
                strategy_info["name"], 
                strategy_info["config"], 
                self.bot, 
                self.logger,
                channel_name  # Pass the full channel name
            )
        
        # Start scanner tasks
        self.start_scanner_tasks()
    
    def start_scanner_tasks(self):
        """Start all scanner tasks"""
        self.logger.info("Starting scanner tasks...")
        for key, strategy in self.strategy_objects.items():
            interval = self.strategies[key]["interval"]
            self.logger.info(f"Initializing {strategy.name} scanner with {interval} {'minutes' if interval < 60 else 'hours'} interval")
            
            if interval < 60:  # minutes
                task = self.create_scanner_task(strategy, minutes=interval)
            else:  # hours
                task = self.create_scanner_task(strategy, hours=interval)
            
            strategy.scanner_task = task
            task.start()
            self.logger.info(f"Started {strategy.name} scanner task")
    
    def create_scanner_task(self, strategy, **kwargs):
        """Create a scanner task for a strategy"""
        @tasks.loop(**kwargs)
        async def scanner_task():
            await strategy.run_scan()
        
        @scanner_task.before_loop
        async def before_scanner_task():
            await self.bot.wait_until_ready()
            self.logger.info(f"Bot ready, starting {strategy.name} scanner...")
        
        return scanner_task
    
    def cog_unload(self):
        """Cleanup when cog is unloaded"""
        if hasattr(self, 'strategy_objects'):
            for strategy in self.strategy_objects.values():
                if strategy.scanner_task:
                    strategy.scanner_task.cancel()
                if strategy.scanner:
                    strategy.scanner = None
    
    @commands.command(name="crypto")
    async def crypto_command(self, ctx, action: str = None, *, args: str = None):
        """Crypto trading commands"""
        if not action:
            available_strategies = list(self.strategy_objects.keys())
            strategies = "|".join(available_strategies) if available_strategies else "none"
            await ctx.send(f"Available commands:\n`!crypto status [strategy]` - Check scanner status\n`!crypto scan [strategy]` - Run manual scan\n`!crypto stop [strategy]` - Stop scanner\n`!crypto start [strategy]` - Start scanner\n`!crypto all` - Check all scanners\n`!crypto add_product [strategy] <product_id>` - Add product to strategy\n`!crypto remove_product [strategy] <product_id>` - Remove product from strategy\n`!crypto list_products [strategy]` - List products for strategy\n\nAvailable strategies: {strategies}\n\nExamples:\n`!crypto list_products day`\n`!crypto add_product day BTC-USD`\n`!crypto remove_product long GRV-USD`\n`!crypto status swing`")
            return
        
        # Handle "all" command
        if action.lower() == "all":
            embed = discord.Embed(
                title="📊 All Crypto Scanners Status",
                color=discord.Color.blue()
            )
            
            if not self.strategy_objects:
                embed.description = "No strategies are currently enabled. Check your .env file configuration."
                await ctx.send(embed=embed)
                return
            
            for key, strategy_obj in self.strategy_objects.items():
                status = "🟢 Running" if strategy_obj.scanner_task.is_running() else "🔴 Stopped"
                channel_name = strategy_obj.channel.name if strategy_obj.channel else "Not found"
                
                embed.add_field(
                    name=f"{strategy_obj.name}",
                    value=f"Status: {status}\nChannel: {channel_name}\nStrategy: {strategy_obj.config['STRATEGY_NAME']}",
                    inline=False
                )
            
            # Add info about disabled strategies
            disabled_strategies = []
            for key in self.strategies.keys():
                if key not in self.strategy_objects:
                    disabled_strategies.append(key)
            
            if disabled_strategies:
                embed.add_field(
                    name="🔴 Disabled Strategies",
                    value=f"The following strategies are disabled (no channel configured): {', '.join(disabled_strategies)}",
                    inline=False
                )
            
            await ctx.send(embed=embed)
            return
        
        # Parse strategy from args for commands that need it
        strategy = "day"  # default
        if args:
            # Split args to get strategy and remaining arguments
            parts = args.split()
            if parts:
                potential_strategy = parts[0].lower()
                if potential_strategy in self.strategies:
                    strategy = potential_strategy
                    # Remove strategy from args and rejoin remaining parts
                    remaining_args = " ".join(parts[1:]) if len(parts) > 1 else ""
                    args = remaining_args
                else:
                    # If first word is not a strategy, keep original args
                    args = " ".join(parts)
        
        # Check if strategy is enabled (exists in strategy_objects)
        if strategy not in self.strategy_objects:
            available_strategies = list(self.strategy_objects.keys())
            if available_strategies:
                await ctx.send(f"Invalid or disabled strategy. Available strategies: {', '.join(available_strategies)}")
            else:
                await ctx.send("No strategies are currently enabled. Check your .env file configuration.")
            return
        
        strategy_obj = self.strategy_objects[strategy]
        
        if action.lower() == "status":
            status = "🟢 Running" if strategy_obj.scanner_task.is_running() else "🔴 Stopped"
            channel_name = strategy_obj.channel.name if strategy_obj.channel else "Not found"
            
            embed = discord.Embed(
                title=f"{strategy_obj.name} Scanner Status",
                color=discord.Color.blue()
            )
            embed.add_field(name="Scanner", value=status, inline=True)
            embed.add_field(name="Channel", value=channel_name, inline=True)
            embed.add_field(name="Strategy", value=strategy_obj.config["STRATEGY_NAME"], inline=True)
            
            await ctx.send(embed=embed)
        
        elif action.lower() == "scan":
            if not strategy_obj.scanner:
                await strategy_obj.setup_scanner()
            
            await ctx.send(f"Running manual {strategy} scan...")
            try:
                signals = strategy_obj.scanner.scan()
                if signals:
                    await strategy_obj.send_signals(signals)
                else:
                    await ctx.send(f"No {strategy} signals found")
            except Exception as e:
                await ctx.send(f"❌ {strategy.title()} scan error: {str(e)}")
        
        elif action.lower() == "stop":
            strategy_obj.scanner_task.cancel()
            await ctx.send(f"{strategy_obj.name} scanner stopped")
        
        elif action.lower() == "start":
            if not strategy_obj.scanner_task.is_running():
                strategy_obj.scanner_task.start()
                await ctx.send(f"{strategy_obj.name} scanner started")
            else:
                await ctx.send(f"{strategy_obj.name} scanner is already running")
        
        elif action.lower() == "search":
            await ctx.send(f"Searching for {strategy} trading channels...")
            found = await strategy_obj.find_channel()
            if found:
                await ctx.send(f"✅ Found {strategy_obj.name} channel: {strategy_obj.channel.name}")
            else:
                await ctx.send(f"❌ No {strategy_obj.channel_name} channel found in any guild")
        
        elif action.lower() == "add_product":
            if not args:
                await ctx.send(f"Usage: `!crypto add_product {strategy} <product_id>`")
                return
            
            product_id = args.strip().upper()
            if product_id not in strategy_obj.config["PRODUCT_IDS"]:
                strategy_obj.config["PRODUCT_IDS"].append(product_id)
                await ctx.send(f"✅ Added {product_id} to {strategy_obj.name} products")
            else:
                await ctx.send(f"❌ {product_id} is already in {strategy_obj.name} products")
        
        elif action.lower() == "remove_product":
            if not args:
                await ctx.send(f"Usage: `!crypto remove_product {strategy} <product_id>`")
                return
            
            product_id = args.strip().upper()
            if product_id in strategy_obj.config["PRODUCT_IDS"]:
                strategy_obj.config["PRODUCT_IDS"].remove(product_id)
                await ctx.send(f"✅ Removed {product_id} from {strategy_obj.name} products")
            else:
                await ctx.send(f"❌ {product_id} is not in {strategy_obj.name} products")
        
        elif action.lower() == "list_products":
            # For list_products, we don't need args since we already have the strategy
            products = strategy_obj.config["PRODUCT_IDS"]
            if products:
                product_list = "\n".join([f"• {product}" for product in products])
                embed = discord.Embed(
                    title=f"{strategy_obj.name} Products",
                    description=product_list,
                    color=discord.Color.green()
                )
                embed.add_field(name="Total Products", value=str(len(products)), inline=True)
                await ctx.send(embed=embed)
            else:
                await ctx.send(f"❌ No products configured for {strategy_obj.name}")
        

        
        else:
            await ctx.send("Invalid action. Use: status, scan, stop, start, search, add_product, remove_product, list_products, or all")

async def setup(bot):
    await bot.add_cog(CryptoCommands(bot))




