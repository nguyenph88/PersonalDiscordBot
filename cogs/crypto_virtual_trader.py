import discord
from discord.ext import commands, tasks
import sqlite3
import os
import logging
import requests
from datetime import datetime
from utils.default import CustomContext
from utils.data import DiscordBot
from tokenometry import Tokenometry

class VirtualTrader:
    """Virtual trading system that executes trades based on crypto signals"""
    
    def __init__(self, db_path="db/virtual_trader.sqlite"):
        self.db_path = db_path
        self.logger = logging.getLogger("VirtualTrader")
        self.setup_database()
    
    def setup_database(self):
        """Initialize the SQLite database with required tables"""
        # Ensure db directory exists
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Create portfolio table to track coin holdings
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS portfolio (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                coin_symbol TEXT UNIQUE NOT NULL,
                amount REAL DEFAULT 0.0,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Create transactions table to log all trades
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                coin_symbol TEXT NOT NULL,
                transaction_type TEXT NOT NULL,
                amount REAL NOT NULL,
                price REAL NOT NULL,
                total_value REAL NOT NULL,
                strategy_type TEXT NOT NULL,
                signal_id TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Create settings table for trader configuration
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS settings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                key TEXT UNIQUE NOT NULL,
                value TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Create signals table to track all trading signals
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS signals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                strategy_name TEXT NOT NULL,
                coin_symbol TEXT NOT NULL,
                signal_type TEXT NOT NULL,
                signal_strength TEXT NOT NULL,
                price REAL NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                executed BOOLEAN DEFAULT FALSE,
                execution_timestamp TIMESTAMP NULL,
                notes TEXT
            )
        ''')
        
        conn.commit()
        
        # Check if this is the first initialization (no USD in portfolio)
        cursor.execute('SELECT amount FROM portfolio WHERE coin_symbol = ?', ('USD',))
        result = cursor.fetchone()
        
        if not result:
            # Initialize with 10,000 USD as base value (primary wallet currency)
            cursor.execute('''
                INSERT INTO portfolio (coin_symbol, amount, last_updated)
                VALUES (?, ?, CURRENT_TIMESTAMP)
            ''', ('USD', 10000.0))
            
            # Log the initial balance transaction
            cursor.execute('''
                INSERT INTO transactions 
                (coin_symbol, transaction_type, amount, price, total_value, strategy_type, signal_id, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ''', ('USD', 'INITIAL', 10000.0, 1.0, 10000.0, 'SYSTEM', 'initial_setup'))
            
            conn.commit()
            self.logger.info("Initialized portfolio with 10,000 USD")
        else:
            self.logger.info("Portfolio already initialized")
        
        conn.close()
        self.logger.info("Virtual trader database initialized")
    
    def get_coin_balance(self, coin_symbol):
        """Get current balance for a specific coin"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT amount FROM portfolio WHERE coin_symbol = ?', (coin_symbol,))
        result = cursor.fetchone()
        
        conn.close()
        return result[0] if result else 0.0
    
    def update_coin_balance(self, coin_symbol, new_amount):
        """Update the balance for a specific coin"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO portfolio (coin_symbol, amount, last_updated)
            VALUES (?, ?, CURRENT_TIMESTAMP)
        ''', (coin_symbol, new_amount))
        
        conn.commit()
        conn.close()
    
    def log_transaction(self, coin_symbol, transaction_type, amount, price, strategy_type, signal_id=None):
        """Log a transaction to the database"""
        total_value = amount * price
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO transactions 
            (coin_symbol, transaction_type, amount, price, total_value, strategy_type, signal_id, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ''', (coin_symbol, transaction_type, amount, price, total_value, strategy_type, signal_id))
        
        conn.commit()
        conn.close()
    
    def log_signal(self, strategy_name, coin_symbol, signal_type, signal_strength, price, notes=None):
        """Log a trading signal to the database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO signals 
            (strategy_name, coin_symbol, signal_type, signal_strength, price, notes, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ''', (strategy_name, coin_symbol, signal_type, signal_strength, price, notes))
        
        signal_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        self.logger.info(f"Logged signal: {signal_strength} {signal_type} for {coin_symbol} from {strategy_name}")
        return signal_id
    
    def mark_signal_executed(self, signal_id, execution_timestamp=None):
        """Mark a signal as executed"""
        if execution_timestamp is None:
            execution_timestamp = datetime.now()
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE signals 
            SET executed = TRUE, execution_timestamp = ? 
            WHERE id = ?
        ''', (execution_timestamp, signal_id))
        
        conn.commit()
        conn.close()
        
        self.logger.info(f"Marked signal {signal_id} as executed")
    
    def get_signal_history(self, strategy_name=None, coin_symbol=None, limit=50):
        """Get signal history from database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        query = '''
            SELECT id, strategy_name, coin_symbol, signal_type, signal_strength, 
                   price, timestamp, executed, execution_timestamp, notes
            FROM signals
        '''
        params = []
        
        if strategy_name or coin_symbol:
            query += ' WHERE'
            if strategy_name:
                query += ' strategy_name = ?'
                params.append(strategy_name)
            if coin_symbol:
                if strategy_name:
                    query += ' AND'
                query += ' coin_symbol = ?'
                params.append(coin_symbol)
        
        query += ' ORDER BY timestamp DESC LIMIT ?'
        params.append(limit)
        
        cursor.execute(query, params)
        results = cursor.fetchall()
        conn.close()
        
        return results
    
    def execute_buy(self, coin_symbol, amount, price, strategy_type, signal_id=None):
        """Execute a buy transaction"""
        # Skip USD buys as it's the primary wallet currency
        if coin_symbol == "USD":
            self.logger.warning("Cannot buy USD as it's the primary wallet currency")
            return False
        
        # Calculate total USD cost
        total_usd_cost = amount * price
        
        # Check if we have enough USD to buy
        usd_balance = self.get_coin_balance("USD")
        if usd_balance < total_usd_cost:
            self.logger.warning(f"Insufficient USD balance: {usd_balance:.2f} < {total_usd_cost:.2f}")
            return False
        
        # Deduct USD from wallet
        new_usd_balance = usd_balance - total_usd_cost
        self.update_coin_balance("USD", new_usd_balance)
        
        # Add the purchased coin to portfolio
        current_balance = self.get_coin_balance(coin_symbol)
        new_balance = current_balance + amount
        self.update_coin_balance(coin_symbol, new_balance)
        
        # Log the buy transaction
        self.log_transaction(coin_symbol, "BUY", amount, price, strategy_type, signal_id)
        
        # Log the USD deduction
        self.log_transaction("USD", "SPEND", total_usd_cost, 1.0, strategy_type, signal_id)
        
        self.logger.info(f"BUY: {amount} {coin_symbol} at ${price:.2f} for ${total_usd_cost:.2f} USD via {strategy_type}")
        return True
    
    def execute_sell(self, coin_symbol, amount, price, strategy_type, signal_id=None):
        """Execute a sell transaction"""
        # Skip USD sells as it's the primary wallet currency
        if coin_symbol == "USD":
            self.logger.warning("Cannot sell USD as it's the primary wallet currency")
            return False
        
        current_balance = self.get_coin_balance(coin_symbol)
        
        if current_balance < amount:
            self.logger.warning(f"Insufficient balance for {coin_symbol}: {current_balance} < {amount}")
            return False
        
        # Calculate total USD value from sale
        total_usd_value = amount * price
        
        # Remove the sold coin from portfolio
        new_balance = current_balance - amount
        self.update_coin_balance(coin_symbol, new_balance)
        
        # Add USD to wallet
        usd_balance = self.get_coin_balance("USD")
        new_usd_balance = usd_balance + total_usd_value
        self.update_coin_balance("USD", new_usd_balance)
        
        # Log the sell transaction
        self.log_transaction(coin_symbol, "SELL", amount, price, strategy_type, signal_id)
        
        # Log the USD addition
        self.log_transaction("USD", "RECEIVE", total_usd_value, 1.0, strategy_type, signal_id)
        
        self.logger.info(f"SELL: {amount} {coin_symbol} at ${price:.2f} for ${total_usd_value:.2f} USD via {strategy_type}")
        return True
    
    def get_portfolio_summary(self):
        """Get summary of all coin holdings"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT coin_symbol, amount, last_updated FROM portfolio WHERE amount > 0')
        results = cursor.fetchall()
        
        conn.close()
        return results
    
    def get_transaction_history(self, coin_symbol=None, limit=10):
        """Get recent transaction history"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        if coin_symbol:
            cursor.execute('''
                SELECT coin_symbol, transaction_type, amount, price, total_value, strategy_type, timestamp
                FROM transactions 
                WHERE coin_symbol = ?
                ORDER BY timestamp DESC
                LIMIT ?
            ''', (coin_symbol, limit))
        else:
            cursor.execute('''
                SELECT coin_symbol, transaction_type, amount, price, total_value, strategy_type, timestamp
                FROM transactions 
                ORDER BY timestamp DESC
                LIMIT ?
            ''', (limit,))
        
        results = cursor.fetchall()
        conn.close()
        return results
    
    def get_current_price(self, coin_symbol):
        """Get current price from Coinbase API"""
        try:
            # Coinbase API endpoint for ticker
            url = f"https://api.coinbase.com/v2/prices/{coin_symbol}/spot"
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            price = float(data['data']['amount'])
            return price
            
        except Exception as e:
            self.logger.error(f"Error fetching price for {coin_symbol}: {e}")
            return None

class CryptoVirtualTrader(commands.Cog):
    def __init__(self, bot):
        self.bot: DiscordBot = bot
        self.trader = VirtualTrader()
        self.logger = logging.getLogger("CryptoVirtualTrader")
        
        # Strategy configurations
        self.strategies = {
            "day": {
                "name": "Day Trader",
                "config": {
                    "STRATEGY_NAME": "Day Trader",
                    "PRODUCT_IDS": ["BTC-USD", "ETH-USD", "AVAX-USD", "SOL-USD", "ADA-USD"],
                    "GRANULARITY_SIGNAL": "FIVE_MINUTE",
                    "GRANULARITY_TREND": "ONE_HOUR",
                    "GRANULARITY_SECONDS": {
                        "ONE_HOUR": 3600, 
                        "FIVE_MINUTE": 300, 
                        "ONE_DAY": 86400, 
                        "ONE_WEEK": 604800
                    },
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
                    "ATR_STOP_LOSS_MULTIPLIER": 2.0
                },
                "interval": 5  # minutes
            },
            "swing": {
                "name": "Swing Trader",
                "config": {
                    "STRATEGY_NAME": "Aggressive Swing Trader",
                    "PRODUCT_IDS": ["BTC-USD", "ETH-USD", "AVAX-USD", "SOL-USD", "ADA-USD"],
                    "GRANULARITY_SIGNAL": "FOUR_HOUR",
                    "GRANULARITY_TREND": "ONE_DAY",
                    "GRANULARITY_SECONDS": {
                        "ONE_HOUR": 3600, 
                        "FIVE_MINUTE": 300, 
                        "ONE_DAY": 86400, 
                        "FOUR_HOUR": 14400, 
                        "ONE_WEEK": 604800
                    },
                    "TREND_INDICATOR_TYPE": "EMA",
                    "TREND_PERIOD": 50,
                    "SIGNAL_INDICATOR_TYPE": "EMA",
                    "SHORT_PERIOD": 20,
                    "LONG_PERIOD": 50,
                    "RSI_PERIOD": 14,
                    "RSI_OVERBOUGHT": 75,
                    "RSI_OVERSOLD": 25,
                    "MACD_FAST": 12,
                    "MACD_SLOW": 26,
                    "MACD_SIGNAL": 9,
                    "ATR_PERIOD": 14,
                    "VOLUME_FILTER_ENABLED": True,
                    "VOLUME_MA_PERIOD": 20,
                    "VOLUME_SPIKE_MULTIPLIER": 1.5,
                    "HYPOTHETICAL_PORTFOLIO_SIZE": 100000.0,
                    "RISK_PER_TRADE_PERCENTAGE": 1.0,
                    "ATR_STOP_LOSS_MULTIPLIER": 2.5
                },
                "interval": 4  # hours
            },
            "long": {
                "name": "Long Term",
                "config": {
                    "STRATEGY_NAME": "Long-Term Investor",
                    "PRODUCT_IDS": ["BTC-USD", "ETH-USD", "AVAX-USD", "SOL-USD", "ADA-USD"],
                    "GRANULARITY_SIGNAL": "ONE_DAY",
                    "GRANULARITY_TREND": "ONE_WEEK",
                    "GRANULARITY_SECONDS": {
                        "ONE_HOUR": 3600, 
                        "FIVE_MINUTE": 300, 
                        "ONE_DAY": 86400, 
                        "ONE_WEEK": 604800
                    },
                    "TREND_INDICATOR_TYPE": "SMA",
                    "TREND_PERIOD": 30,
                    "SIGNAL_INDICATOR_TYPE": "SMA",
                    "SHORT_PERIOD": 50,
                    "LONG_PERIOD": 200,
                    "RSI_PERIOD": 14,
                    "RSI_OVERBOUGHT": 80,
                    "RSI_OVERSOLD": 20,
                    "MACD_FAST": 12,
                    "MACD_SLOW": 26,
                    "MACD_SIGNAL": 9,
                    "ATR_PERIOD": 14,
                    "VOLUME_FILTER_ENABLED": True,
                    "VOLUME_MA_PERIOD": 20,
                    "VOLUME_SPIKE_MULTIPLIER": 1.5,
                    "HYPOTHETICAL_PORTFOLIO_SIZE": 100000.0,
                    "RISK_PER_TRADE_PERCENTAGE": 1.0,
                    "ATR_STOP_LOSS_MULTIPLIER": 2.5
                },
                "interval": 24  # hours
            }
        }
        
        # Start the signal monitoring loop
        self.start_signal_monitoring()
    
    def start_signal_monitoring(self):
        """Start the continuous signal monitoring loop"""
        self.signal_monitor.start()
        self.logger.info("Signal monitoring started for all strategies")
    
    def cog_unload(self):
        """Clean up when cog is unloaded"""
        if hasattr(self, 'signal_monitor'):
            self.signal_monitor.cancel()
    
    @tasks.loop(minutes=1)  # Check every minute
    async def signal_monitor(self):
        """Monitor for signals from all strategies"""
        try:
            for strategy_key, strategy_info in self.strategies.items():
                await self.check_strategy_signals(strategy_key, strategy_info)
        except Exception as e:
            self.logger.error(f"Error in signal monitor: {e}")
    
    async def check_strategy_signals(self, strategy_key, strategy_info):
        """Check for signals from a specific strategy"""
        try:
            # Create Tokenometry scanner for this strategy
            scanner = Tokenometry(config=strategy_info["config"], logger=self.logger)
            
            # Get signals using the new scan method
            signals = scanner.scan()
            
            if signals:
                await self.process_strategy_signals(strategy_key, strategy_info["name"], signals)
            
        except Exception as e:
            self.logger.error(f"Error checking {strategy_key} strategy: {e}")
    
    async def process_strategy_signals(self, strategy_key, strategy_name, signals):
        """Process and execute signals from a strategy"""
        try:
            # Separate BUY and SELL signals for sequential processing
            buy_signals = []
            sell_signals = []
            other_signals = []
            
            for signal in signals:
                signal_type = signal.get('signal', '').upper()
                coin_symbol = signal.get('asset', '')
                signal_strength = signal.get('strength', 'Unknown')
                price = signal.get('close_price', 0)
                
                self.logger.info(f"Processing {signal_strength} {signal_type} signal for {coin_symbol} from {strategy_name}")
                
                # Log all actionable signals (BUY/SELL) to database
                if signal_type in ['BUY', 'SELL']:
                    # Log the signal to database
                    signal_id = self.trader.log_signal(
                        strategy_name=strategy_name,
                        coin_symbol=coin_symbol,
                        signal_type=signal_type,
                        signal_strength=signal_strength,
                        price=price,
                        notes=f"Auto-detected by {strategy_name} strategy"
                    )
                    
                    # Add signal_id to the signal for tracking
                    signal['db_signal_id'] = signal_id
                    
                    if signal_type == 'BUY':
                        buy_signals.append(signal)
                    elif signal_type == 'SELL':
                        sell_signals.append(signal)
                else:
                    # Log non-actionable signals as well for completeness
                    self.trader.log_signal(
                        strategy_name=strategy_name,
                        coin_symbol=coin_symbol,
                        signal_type=signal_type,
                        signal_strength=signal_strength,
                        price=price,
                        notes=f"Non-actionable signal from {strategy_name} strategy"
                    )
                    other_signals.append(signal)
            
            # Process BUY signals first (sequentially to manage USD balance)
            if buy_signals:
                self.logger.info(f"Processing {len(buy_signals)} BUY signals sequentially")
                await self.process_buy_signals_sequentially(strategy_key, strategy_name, buy_signals)
            
            # Process SELL signals (can be parallel since they don't affect USD balance)
            if sell_signals:
                self.logger.info(f"Processing {len(sell_signals)} SELL signals")
                for signal in sell_signals:
                    await self.execute_signal_trade(strategy_key, strategy_name, signal)
            
            # Process other signals (notifications only)
            for signal in other_signals:
                await self.notify_signal(strategy_key, strategy_name, signal)
                    
        except Exception as e:
            self.logger.error(f"Error processing signals for {strategy_key}: {e}")
    
    async def process_buy_signals_sequentially(self, strategy_key, strategy_name, buy_signals):
        """Process multiple BUY signals sequentially to manage USD balance"""
        try:
            # Sort signals by strength (Strong first, then Medium, then Low)
            strength_order = {'Strong': 3, 'Medium': 2, 'Low': 1}
            sorted_signals = sorted(buy_signals, key=lambda x: strength_order.get(x.get('strength', 'Low'), 1), reverse=True)
            
            self.logger.info(f"Processing {len(sorted_signals)} BUY signals in order of strength")
            
            for i, signal in enumerate(sorted_signals):
                coin_symbol = signal.get('asset', '')
                signal_strength = signal.get('strength', 'Low')
                
                # Check current USD balance before each trade
                current_usd_balance = self.trader.get_coin_balance("USD")
                
                if current_usd_balance <= 0:
                    self.logger.warning(f"Insufficient USD balance for remaining BUY signals. Stopping at signal {i+1}")
                    break
                
                # Calculate trade amount based on signal strength percentage of CURRENT USD balance
                strength_percentages = {
                    'Low': 0.25,      # 25% of current USD balance
                    'Medium': 0.50,   # 50% of current USD balance
                    'Strong': 0.75    # 75% of current USD balance
                }
                
                trade_percentage = strength_percentages.get(signal_strength, 0.25)
                trade_amount_usd = current_usd_balance * trade_percentage
                
                # Ensure we don't spend more than we have
                if trade_amount_usd > current_usd_balance:
                    trade_amount_usd = current_usd_balance
                
                if trade_amount_usd <= 0:
                    self.logger.warning(f"Insufficient USD balance for {signal_strength} BUY signal of {coin_symbol}")
                    continue
                
                # Get current price and execute trade
                price = signal.get('close_price', 0)
                if not price:
                    self.logger.warning(f"No price data for {coin_symbol}, skipping signal")
                    continue
                
                crypto_amount = trade_amount_usd / price
                success = self.trader.execute_buy(
                    coin_symbol, crypto_amount, price, strategy_name, 
                    f"signal_{strategy_key}_{datetime.now().timestamp()}_{i+1}"
                )
                
                if success:
                    await self.send_trade_notification(strategy_name, "BUY", coin_symbol, crypto_amount, price, trade_amount_usd, signal_strength)
                    self.logger.info(f"Executed {signal_strength} BUY signal #{i+1}: {crypto_amount:.8f} {coin_symbol} at ${price:.2f} (${trade_amount_usd:.2f} USD)")
                    
                    # Log remaining USD balance
                    remaining_usd = self.trader.get_coin_balance("USD")
                    self.logger.info(f"Remaining USD balance after signal #{i+1}: ${remaining_usd:.2f}")
                else:
                    self.logger.warning(f"Failed to execute BUY signal #{i+1} for {coin_symbol}")
                    
        except Exception as e:
            self.logger.error(f"Error processing BUY signals sequentially: {e}")
    
    async def execute_signal_trade(self, strategy_key, strategy_name, signal):
        """Execute a trade based on signal strength"""
        try:
            coin_symbol = signal.get('asset', '')
            signal_type = signal.get('signal', '').upper()
            price = signal.get('close_price', 0)
            signal_strength = signal.get('strength', 'Low')  # Default to Low if not provided
            
            if not coin_symbol or not price:
                self.logger.warning(f"Invalid signal data: {signal}")
                return
            
            # Calculate trade percentage based on signal strength
            strength_percentages = {
                'Low': 0.25,      # 25% of total value
                'Medium': 0.50,   # 50% of total value
                'Strong': 0.75    # 75% of total value
            }
            
            trade_percentage = strength_percentages.get(signal_strength, 0.25)
            
            if signal_type == "BUY":
                # Calculate trade amount based on signal strength percentage of USD balance
                usd_balance = self.trader.get_coin_balance("USD")
                trade_amount_usd = usd_balance * trade_percentage
                
                # Execute buy
                crypto_amount = trade_amount_usd / price
                success = self.trader.execute_buy(
                    coin_symbol, crypto_amount, price, strategy_name, 
                    f"signal_{strategy_key}_{datetime.now().timestamp()}"
                )
                
                if success:
                    await self.send_trade_notification(strategy_name, "BUY", coin_symbol, crypto_amount, price, trade_amount_usd, signal_strength)
                    self.logger.info(f"Executed {signal_strength} BUY signal: {crypto_amount:.8f} {coin_symbol} at ${price:.2f} (${trade_amount_usd:.2f} USD)")
                else:
                    self.logger.warning(f"Failed to execute BUY signal for {coin_symbol}")
                    
            elif signal_type == "SELL":
                # Check if we have the coin to sell
                current_balance = self.trader.get_coin_balance(coin_symbol)
                if current_balance > 0:
                    # Sell based on signal strength percentage of holdings
                    sell_amount = current_balance * trade_percentage
                    success = self.trader.execute_sell(
                        coin_symbol, sell_amount, price, strategy_name,
                        f"signal_{strategy_key}_{datetime.now().timestamp()}"
                    )
                    
                    if success:
                        await self.send_trade_notification(strategy_name, "SELL", coin_symbol, sell_amount, price, sell_amount * price, signal_strength)
                        self.logger.info(f"Executed {signal_strength} SELL signal: {sell_amount:.8f} {coin_symbol} at ${price:.2f} (${sell_amount * price:.2f} USD)")
                    else:
                        self.logger.warning(f"Failed to execute SELL signal for {coin_symbol}")
                else:
                    self.logger.info(f"No {coin_symbol} to sell for SELL signal")
                    
        except Exception as e:
            self.logger.error(f"Error executing signal trade: {e}")
    
    async def notify_signal(self, strategy_key, strategy_name, signal):
        """Notify about non-trade signals"""
        try:
            coin_symbol = signal.get('asset', '')
            signal_type = signal.get('signal', '')
            
            # Only log non-trade signals, don't post to channel
            self.logger.info(f"Signal notification: {signal_type} for {coin_symbol} from {strategy_name}")
            
        except Exception as e:
            self.logger.error(f"Error notifying signal: {e}")
    
    async def send_trade_notification(self, strategy_name, trade_type, coin_symbol, amount, price, usd_value, signal_strength):
        """Send trade notification to the virtual trader channel"""
        try:
            if not self.bot.config.virtual_trader_channel:
                return
            
            # Find the channel
            channel = None
            for guild in self.bot.guilds:
                channel = discord.utils.get(guild.channels, name=self.bot.config.virtual_trader_channel)
                if channel:
                    break
            
            if not channel:
                self.logger.warning(f"Virtual trader channel not found: {self.bot.config.virtual_trader_channel}")
                return
            
            # Create trade notification embed
            color = discord.Color.green() if trade_type == "BUY" else discord.Color.red()
            emoji = "🟢" if trade_type == "BUY" else "🔴"
            
            # Add strength indicator with emojis
            strength_indicators = {
                "Strong": "🟢",
                "Medium": "🟡", 
                "Low": "🔴"
            }
            strength_emoji = strength_indicators.get(signal_strength, '⚪')
            
            embed = discord.Embed(
                title=f"{emoji} Auto-Trade Executed",
                description=f"**{strategy_name}** strategy triggered a **{trade_type}** order",
                color=color,
                timestamp=discord.utils.utcnow()
            )
            
            embed.add_field(name="Signal Strength", value=f"{strength_emoji} {signal_strength}", inline=True)
            embed.add_field(name="Coin", value=coin_symbol, inline=True)
            embed.add_field(name="Amount", value=f"{amount:.8f}", inline=True)
            embed.add_field(name="Price", value=f"${price:.2f}", inline=True)
            embed.add_field(name="USD Value", value=f"${usd_value:.2f}", inline=True)
            embed.add_field(name="Strategy", value=strategy_name, inline=True)
            embed.add_field(name="Type", value=trade_type, inline=True)
            
            await channel.send(embed=embed)
            
        except Exception as e:
            self.logger.error(f"Error sending trade notification: {e}")
    
    async def check_channel_permission(self, ctx):
        """Check if the command is being used in the correct channel"""
        if not self.bot.config.virtual_trader_channel:
            await ctx.send("❌ **Error:** Virtual trader channel not configured in .env file")
            return False
        
        if ctx.channel.name != self.bot.config.virtual_trader_channel:
            await ctx.send(f"❌ **Error:** This command can only be used in the `#{self.bot.config.virtual_trader_channel}` channel")
            return False
        
        return True
    
    @commands.group(invoke_without_command=True)
    async def trader(self, ctx: CustomContext):
        """Virtual crypto trading commands"""
        if not await self.check_channel_permission(ctx):
            return
        
        await ctx.send("Available commands:\n"
                      "`!trader portfolio` - View current holdings\n"
                      "`!trader buy <coin> <usd_amount>` - Execute buy order with USD\n"
                      "`!trader sell <coin> <crypto_amount>` - Execute sell order with crypto amount\n"
                      "`!trader balance <coin>` - Check coin balance\n"
                      "`!trader history [coin] [limit]` - View transaction history\n"
                      "`!trader signal <coin> <strength> [type]` - Test manual trading signal (BUY/SELL)\n"
                      "`!trader signals [strategy] [coin] [limit]` - View signal history\n"
                      "`!trader status` - Check scanner status and health\n"
                      "`!trader add_coin <strategy> <coin>` - Add coin to strategy\n"
                      "`!trader remove_coin <strategy> <coin>` - Remove coin from strategy\n"
                      "`!trader execute_signal <signal_data>` - Execute trade from signal")
    
    @trader.command()
    async def portfolio(self, ctx: CustomContext):
        """View current portfolio holdings"""
        if not await self.check_channel_permission(ctx):
            return
        
        holdings = self.trader.get_portfolio_summary()
        
        if not holdings:
            await ctx.send("📭 **Portfolio Empty:** No coins currently held")
            return
        
        embed = discord.Embed(
            title="💰 Virtual Trading Portfolio",
            color=discord.Color.blue(),
            timestamp=discord.utils.utcnow()
        )
        
        # Calculate total portfolio value in USD
        total_usd_value = 0.0
        usd_balance = 0.0
        crypto_holdings = []
        
        for coin_symbol, amount, last_updated in holdings:
            if coin_symbol == "USD":
                usd_balance = amount
                total_usd_value += amount
            else:
                # Get current price for crypto
                current_price = self.trader.get_current_price(coin_symbol)
                if current_price is not None:
                    crypto_value_usd = amount * current_price
                    total_usd_value += crypto_value_usd
                    crypto_holdings.append((coin_symbol, amount, current_price, crypto_value_usd))
                else:
                    # If price fetch fails, still show the holding but without USD value
                    crypto_holdings.append((coin_symbol, amount, None, 0.0))
        
        # Add total portfolio value as the main highlight
        embed.add_field(
            name="🏆 **Total Portfolio Value**",
            value=f"**${total_usd_value:,.2f} USD**",
            inline=False
        )
        
        # Add USD balance
        embed.add_field(
            name="💵 **USD** (Main Wallet)",
            value=f"**${usd_balance:,.2f} USD**",
            inline=False
        )
        
        # Add crypto holdings with USD values
        if crypto_holdings:
            for coin_symbol, amount, current_price, crypto_value_usd in crypto_holdings:
                # Format crypto amounts with appropriate precision
                if amount >= 1:
                    formatted_amount = f"{amount:.4f}"
                elif amount >= 0.01:
                    formatted_amount = f"{amount:.6f}"
                else:
                    formatted_amount = f"{amount:.8f}"
                
                if current_price is not None:
                    name = f"🪙 {coin_symbol}"
                    value = f"**{formatted_amount} {coin_symbol}**\n${crypto_value_usd:,.2f} USD"
                    embed.add_field(name=name, value=value, inline=True)
                else:
                    name = f"🪙 {coin_symbol}"
                    value = f"**{formatted_amount} {coin_symbol}**\n*Price unavailable*"
                    embed.add_field(name=name, value=value, inline=True)
        
        embed.set_footer(text=f"Last Updated • {len(holdings)} total holdings")
        await ctx.send(embed=embed)
    
    @trader.command()
    async def buy(self, ctx: CustomContext, coin_symbol: str, usd_amount: float):
        """Execute a buy order with USD amount"""
        if not await self.check_channel_permission(ctx):
            return
        
        if usd_amount <= 0:
            await ctx.send("❌ **Error:** USD amount must be positive")
            return
        
        coin_symbol = coin_symbol.upper()
        
        # Prevent buying USD as it's the primary wallet currency
        if coin_symbol == "USD":
            await ctx.send("❌ **Error:** Cannot buy USD as it's the primary wallet currency")
            return
        
        # Check if we have enough USD for the purchase
        usd_balance = self.trader.get_coin_balance("USD")
        
        if usd_balance < usd_amount:
            await ctx.send(f"❌ **Insufficient USD Balance:** You need ${usd_amount:.2f} USD but only have ${usd_balance:.2f} USD")
            return
        
        # Get current price from Coinbase
        current_price = self.trader.get_current_price(coin_symbol)
        if current_price is None:
            await ctx.send(f"❌ **Error:** Could not fetch current price for {coin_symbol}")
            return
        
        # Calculate crypto amount from USD
        crypto_amount = usd_amount / current_price
        
        try:
            success = self.trader.execute_buy(coin_symbol, crypto_amount, current_price, "MANUAL", f"manual_{ctx.author.id}")
            
            if success:
                embed = discord.Embed(
                    title="✅ Buy Order Executed",
                    description=f"Successfully purchased {crypto_amount:.8f} {coin_symbol}",
                    color=discord.Color.green(),
                    timestamp=discord.utils.utcnow()
                )
                embed.add_field(name="USD Spent", value=f"${usd_amount:.2f} USD", inline=True)
                embed.add_field(name="Current Price", value=f"${current_price:.2f}", inline=True)
                embed.add_field(name="Crypto Amount", value=f"{crypto_amount:.8f} {coin_symbol}", inline=True)
                embed.add_field(name="New Balance", value=f"{self.trader.get_coin_balance(coin_symbol):.8f} {coin_symbol}", inline=True)
                embed.add_field(name="USD Balance", value=f"{self.trader.get_coin_balance('USD'):.2f} USD", inline=True)
                
                await ctx.send(embed=embed)
            else:
                await ctx.send("❌ **Error:** Failed to execute buy order")
                
        except Exception as e:
            self.logger.error(f"Error executing buy order: {e}")
            await ctx.send(f"❌ **Error:** {str(e)}")
    
    @trader.command()
    async def sell(self, ctx: CustomContext, coin_symbol: str, crypto_amount: float):
        """Execute a sell order with crypto amount"""
        if not await self.check_channel_permission(ctx):
            return
        
        if crypto_amount <= 0:
            await ctx.send("❌ **Error:** Crypto amount must be positive")
            return
        
        coin_symbol = coin_symbol.upper()
        
        # Prevent selling USD as it's the primary wallet currency
        if coin_symbol == "USD":
            await ctx.send("❌ **Error:** Cannot sell USD as it's the primary wallet currency")
            return
        
        # Check if we have enough of the crypto to sell
        current_balance = self.trader.get_coin_balance(coin_symbol)
        
        if current_balance < crypto_amount:
            await ctx.send(f"❌ **Insufficient Balance:** You only have {current_balance:.8f} {coin_symbol}")
            return
        
        # Get current price from Coinbase
        current_price = self.trader.get_current_price(coin_symbol)
        if current_price is None:
            await ctx.send(f"❌ **Error:** Could not fetch current price for {coin_symbol}")
            return
        
        # Calculate USD value from crypto amount
        usd_value = crypto_amount * current_price
        
        try:
            success = self.trader.execute_sell(coin_symbol, crypto_amount, current_price, "MANUAL", f"manual_{ctx.author.id}")
            
            if success:
                embed = discord.Embed(
                    title="✅ Sell Order Executed",
                    description=f"Successfully sold {crypto_amount:.8f} {coin_symbol}",
                    color=discord.Color.red(),
                    timestamp=discord.utils.utcnow()
                )
                embed.add_field(name="Crypto Amount", value=f"{crypto_amount:.8f} {coin_symbol}", inline=True)
                embed.add_field(name="Current Price", value=f"${current_price:.2f}", inline=True)
                embed.add_field(name="USD Received", value=f"${usd_value:.2f} USD", inline=True)
                embed.add_field(name="Remaining Balance", value=f"{self.trader.get_coin_balance(coin_symbol):.8f} {coin_symbol}", inline=True)
                embed.add_field(name="USD Balance", value=f"{self.trader.get_coin_balance('USD'):.2f} USD", inline=True)
                
                await ctx.send(embed=embed)
            else:
                await ctx.send("❌ **Error:** Failed to execute sell order")
                
        except Exception as e:
            self.logger.error(f"Error executing sell order: {e}")
            await ctx.send(f"❌ **Error:** {str(e)}")
    
    @trader.command()
    async def balance(self, ctx: CustomContext, coin_symbol: str):
        """Check balance for a specific coin"""
        if not await self.check_channel_permission(ctx):
            return
        
        coin_symbol = coin_symbol.upper()
        balance = self.trader.get_coin_balance(coin_symbol)
        
        embed = discord.Embed(
            title=f"💰 {coin_symbol} Balance",
            color=discord.Color.blue(),
            timestamp=discord.utils.utcnow()
        )
        embed.add_field(name="Balance", value=f"{balance:.6f} {coin_symbol}", inline=True)
        
        if balance > 0:
            embed.color = discord.Color.green()
        else:
            embed.color = discord.Color.orange()
            embed.add_field(name="Status", value="No holdings", inline=True)
        
        await ctx.send(embed=embed)
    
    @trader.command()
    async def history(self, ctx: CustomContext, coin_symbol: str = None, limit: int = 10):
        """View transaction history"""
        if not await self.check_channel_permission(ctx):
            return
        
        if limit > 25:
            limit = 25  # Cap at 25 for performance
        
        transactions = self.trader.get_transaction_history(coin_symbol, limit)
        
        if not transactions:
            coin_text = f" for {coin_symbol}" if coin_symbol else ""
            await ctx.send(f"📭 **No Transactions Found{coin_text}**")
            return
        
        embed = discord.Embed(
            title="📊 Transaction History",
            color=discord.Color.blue(),
            timestamp=discord.utils.utcnow()
        )
        
        for coin, tx_type, amount, price, total_value, strategy, timestamp in transactions:
            emoji = "🟢" if tx_type == "BUY" else "🔴"
            embed.add_field(
                name=f"{emoji} {tx_type} {coin}",
                value=f"Amount: {amount:.6f}\nPrice: ${price:.2f}\nTotal: ${total_value:.2f}\nStrategy: {strategy}\nTime: {timestamp}",
                inline=False
            )
        
        embed.set_footer(text=f"Showing last {len(transactions)} transactions")
        await ctx.send(embed=embed)
    
    @trader.command()
    async def signal(self, ctx: CustomContext, coin_symbol: str, strength: str, signal_type: str = "buy"):
        """Manually test trading signals with specified coin, strength, and type"""
        if not await self.check_channel_permission(ctx):
            return
        
        # Validate strength parameter
        valid_strengths = ['low', 'medium', 'strong']
        if strength.lower() not in valid_strengths:
            await ctx.send(f"❌ **Invalid Strength:** Must be one of: {', '.join(valid_strengths).title()}")
            return
        
        # Validate signal type parameter
        valid_types = ['buy', 'sell']
        if signal_type.lower() not in valid_types:
            await ctx.send(f"❌ **Invalid Signal Type:** Must be one of: {', '.join(valid_types).title()}")
            return
        
        # Capitalize for consistency
        signal_strength = strength.capitalize()
        signal_type = signal_type.upper()
        coin_symbol = coin_symbol.upper()
        
        # Get current price from Coinbase
        current_price = self.trader.get_current_price(coin_symbol)
        if current_price is None:
            await ctx.send(f"❌ **Error:** Could not fetch current price for {coin_symbol}")
            return
        
        # Create a mock signal for testing
        mock_signal = {
            'asset': coin_symbol,
            'signal': signal_type,
            'strength': signal_strength,
            'close_price': current_price,
            'timestamp': datetime.now().isoformat()
        }
        
        # Execute the signal
        await ctx.send(f"🔄 **Testing {signal_strength} {signal_type} Signal** for {coin_symbol} at ${current_price:.2f}")
        
        try:
            await self.execute_signal_trade("manual", "Manual Test", mock_signal)
            await ctx.send(f"✅ **Signal Test Complete:** {signal_strength} {signal_type} signal for {coin_symbol} executed successfully!")
        except Exception as e:
            await ctx.send(f"❌ **Signal Test Failed:** {str(e)}")
    
    @trader.command()
    async def signals(self, ctx: CustomContext, strategy_name: str = None, coin_symbol: str = None, limit: int = 20):
        """View signal history from the database"""
        if not await self.check_channel_permission(ctx):
            return
        
        if limit > 50:
            limit = 50  # Cap at 50 for performance
        
        # Get signal history from database
        signals = self.trader.get_signal_history(strategy_name, coin_symbol, limit)
        
        if not signals:
            strategy_text = f" for {strategy_name}" if strategy_name else ""
            coin_text = f" and {coin_symbol}" if coin_symbol else ""
            await ctx.send(f"📭 **No Signals Found{strategy_text}{coin_text}**")
            return
        
        embed = discord.Embed(
            title="📊 Signal History",
            color=discord.Color.blue(),
            timestamp=discord.utils.utcnow()
        )
        
        for signal_id, strategy, coin, signal_type, strength, price, timestamp, executed, exec_timestamp, notes in signals:
            # Create strength indicator with emojis
            strength_indicators = {
                "Strong": "🟢",
                "Medium": "🟡", 
                "Low": "🔴"
            }
            strength_emoji = strength_indicators.get(strength, '⚪')
            
            # Create execution status indicator
            exec_status = "✅ Executed" if executed else "⏳ Pending"
            exec_time = f" at {exec_timestamp}" if exec_timestamp else ""
            
            embed.add_field(
                name=f"{strength_emoji} {signal_type} {coin}",
                value=f"**Strategy:** {strategy}\n**Strength:** {strength}\n**Price:** ${price:.2f}\n**Status:** {exec_status}{exec_time}\n**Time:** {timestamp}",
                inline=False
            )
        
        embed.set_footer(text=f"Showing last {len(signals)} signals")
        await ctx.send(embed=embed)
    
    @trader.command()
    async def status(self, ctx: CustomContext):
        """Check the status of all trading scanners"""
        if not await self.check_channel_permission(ctx):
            return
        
        embed = discord.Embed(
            title="🔍 Scanner Status Report",
            color=discord.Color.blue(),
            timestamp=discord.utils.utcnow()
        )
        
        # Check each strategy scanner
        for strategy_key, strategy_info in self.strategies.items():
            try:
                # Test the scanner by creating a quick instance
                scanner = Tokenometry(config=strategy_info["config"], logger=self.logger)
                
                # Try to get a small sample of data to verify it's working
                test_signals = scanner.scan()
                
                if test_signals is not None:
                    # Scanner is working
                    status_emoji = "🟢"
                    status_text = "Active"
                    signal_count = len(test_signals) if test_signals else 0
                    
                    embed.add_field(
                        name=f"{status_emoji} {strategy_info['name']}",
                        value=f"**Status:** {status_text}\n**Interval:** {strategy_info['interval']} {'minutes' if strategy_info['interval'] < 60 else 'hours'}\n**Products:** {len(strategy_info['config']['PRODUCT_IDS'])} coins\n**Coins:** {', '.join(strategy_info['config']['PRODUCT_IDS'])}\n**Last Check:** {datetime.now().strftime('%H:%M:%S')}\n**Signals Found:** {signal_count}",
                        inline=False
                    )
                else:
                    # Scanner returned None (potential issue)
                    status_emoji = "🟡"
                    status_text = "Warning - No Response"
                    
                    embed.add_field(
                        name=f"{status_emoji} {strategy_info['name']}",
                        value=f"**Status:** {status_text}\n**Interval:** {strategy_info['interval']} {'minutes' if strategy_info['interval'] < 60 else 'hours'}\n**Products:** {len(strategy_info['config']['PRODUCT_IDS'])} coins\n**Coins:** {', '.join(strategy_info['config']['PRODUCT_IDS'])}\n**Last Check:** {datetime.now().strftime('%H:%M:%S')}\n**Issue:** Scanner returned no data",
                        inline=False
                    )
                    
            except Exception as e:
                # Scanner has an error
                status_emoji = "🔴"
                status_text = "Error"
                
                embed.add_field(
                    name=f"{status_emoji} {strategy_info['name']}",
                    value=f"**Status:** {status_text}\n**Interval:** {strategy_info['interval']} {'minutes' if strategy_info['interval'] < 60 else 'hours'}\n**Products:** {len(strategy_info['config']['PRODUCT_IDS'])} coins\n**Coins:** {', '.join(strategy_info['config']['PRODUCT_IDS'])}\n**Last Check:** {datetime.now().strftime('%H:%M:%S')}\n**Error:** {str(e)[:50]}...",
                    inline=False
                )
        
        # Add overall system status
        signal_monitor_status = "🟢 Running" if self.signal_monitor.is_running() else "🔴 Stopped"
        embed.add_field(
            name="📊 System Status",
            value=f"**Signal Monitor:** {signal_monitor_status}\n**Total Strategies:** {len(self.strategies)}\n**Database:** Connected\n**Last Update:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            inline=False
        )
        
        embed.set_footer(text="Scanner health check completed")
        await ctx.send(embed=embed)
    
    @trader.command()
    async def add_coin(self, ctx: CustomContext, strategy: str, coin: str):
        """Add a coin to a strategy's PRODUCT_IDS"""
        if not await self.check_channel_permission(ctx):
            return
        
        strategy = strategy.lower()
        coin = coin.upper()
        
        # Validate strategy
        if strategy not in self.strategies:
            valid_strategies = ", ".join(self.strategies.keys())
            await ctx.send(f"❌ **Invalid Strategy:** Must be one of: {valid_strategies}")
            return
        
        # Validate coin format (should end with -USD)
        if not coin.endswith('-USD'):
            await ctx.send("❌ **Invalid Coin Format:** Coin must end with '-USD' (e.g., BTC-USD)")
            return
        
        # Check if coin is already in the strategy
        current_coins = self.strategies[strategy]["config"]["PRODUCT_IDS"]
        if coin in current_coins:
            await ctx.send(f"❌ **Coin Already Exists:** {coin} is already in {strategy} strategy")
            return
        
        # Add coin to strategy
        self.strategies[strategy]["config"]["PRODUCT_IDS"].append(coin)
        
        embed = discord.Embed(
            title="✅ Coin Added Successfully",
            color=discord.Color.green(),
            timestamp=discord.utils.utcnow()
        )
        embed.add_field(name="Strategy", value=strategy.title(), inline=True)
        embed.add_field(name="Coin Added", value=coin, inline=True)
        embed.add_field(name="Total Coins", value=len(self.strategies[strategy]["config"]["PRODUCT_IDS"]), inline=True)
        
        await ctx.send(embed=embed)
    
    @trader.command()
    async def remove_coin(self, ctx: CustomContext, strategy: str, coin: str):
        """Remove a coin from a strategy's PRODUCT_IDS"""
        if not await self.check_channel_permission(ctx):
            return
        
        strategy = strategy.lower()
        coin = coin.upper()
        
        # Validate strategy
        if strategy not in self.strategies:
            valid_strategies = ", ".join(self.strategies.keys())
            await ctx.send(f"❌ **Invalid Strategy:** Must be one of: {valid_strategies}")
            return
        
        # Check if coin exists in the strategy
        current_coins = self.strategies[strategy]["config"]["PRODUCT_IDS"]
        if coin not in current_coins:
            await ctx.send(f"❌ **Coin Not Found:** {coin} is not in {strategy} strategy")
            return
        
        # Remove coin from strategy
        self.strategies[strategy]["config"]["PRODUCT_IDS"].remove(coin)
        
        embed = discord.Embed(
            title="✅ Coin Removed Successfully",
            color=discord.Color.red(),
            timestamp=discord.utils.utcnow()
        )
        embed.add_field(name="Strategy", value=strategy.title(), inline=True)
        embed.add_field(name="Coin Removed", value=coin, inline=True)
        embed.add_field(name="Remaining Coins", value=len(self.strategies[strategy]["config"]["PRODUCT_IDS"]), inline=True)
        
        await ctx.send(embed=embed)
    
    @trader.command()
    async def execute_signal(self, ctx: CustomContext, *, signal_data: str):
        """Execute a trade based on signal data (for future integration with crypto.py)"""
        if not await self.check_channel_permission(ctx):
            return
        
        # This is a placeholder for future signal integration
        await ctx.send("🔄 **Signal Execution:** This feature will be integrated with crypto.py signals in the future")
    
    async def process_crypto_signal(self, signal, strategy_type):
        """Process a signal from crypto.py and execute virtual trade"""
        try:
            coin_symbol = signal['asset']
            signal_type = signal['signal']
            price = signal['close_price']
            
            # For now, use a fixed amount - this can be made configurable later
            trade_amount = 0.001  # Small amount for testing
            
            if signal_type == "BUY":
                success = self.trader.execute_buy(coin_symbol, trade_amount, price, strategy_type, f"signal_{datetime.now().timestamp()}")
            elif signal_type == "SELL":
                success = self.trader.execute_sell(coin_symbol, trade_amount, price, strategy_type, f"signal_{datetime.now().timestamp()}")
            else:
                self.logger.warning(f"Unknown signal type: {signal_type}")
                return False
            
            if success:
                self.logger.info(f"Successfully executed {signal_type} signal for {coin_symbol} via {strategy_type}")
            else:
                self.logger.warning(f"Failed to execute {signal_type} signal for {coin_symbol}")
            
            return success
            
        except Exception as e:
            self.logger.error(f"Error processing crypto signal: {e}")
            return False

async def setup(bot):
    await bot.add_cog(CryptoVirtualTrader(bot))
