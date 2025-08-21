import discord
from discord.ext import commands, tasks
import sqlite3
import os
import logging
import requests
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from utils.default import CustomContext
from utils.data import DiscordBot
from tokenometry import Tokenometry

# Add PostgreSQL support
try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
    PSYCOPG2_AVAILABLE = True
except ImportError:
    PSYCOPG2_AVAILABLE = False
    print("Warning: psycopg2 not available. PostgreSQL support disabled.")

# ============================================================================
# CONFIGURATION CLASSES
# ============================================================================

@dataclass
class StrategyConfig:
    """Configuration for a trading strategy"""
    name: str
    strategy_name: str
    product_ids: List[str]
    granularity_signal: str
    granularity_trend: str
    trend_indicator: str
    trend_period: int
    signal_indicator: str
    short_period: int
    long_period: int
    rsi_period: int
    rsi_overbought: int
    rsi_oversold: int
    macd_fast: int
    macd_slow: int
    macd_signal: int
    atr_period: int
    volume_filter_enabled: bool
    volume_ma_period: int
    volume_spike_multiplier: float
    hypothetical_portfolio_size: float
    risk_per_trade_percentage: float
    atr_stop_loss_multiplier: float
    interval: int

@dataclass
class TradeSignal:
    """Represents a trading signal"""
    strategy_name: str
    coin_symbol: str
    signal_type: str
    signal_strength: str
    price: float
    timestamp: datetime
    signal_id: str

# ============================================================================
# DATABASE MANAGER
# ============================================================================

class DatabaseManager:
    """Handles all database operations for both SQLite and PostgreSQL"""
    
    def __init__(self, bot_config):
        self.bot_config = bot_config
        self.logger = logging.getLogger("DatabaseManager")
        self.db_type = getattr(bot_config, 'virtual_trader_database_type', 'sqlite').lower()
        
        if self.db_type == 'postgres':
            if not PSYCOPG2_AVAILABLE:
                self.logger.error("PostgreSQL requested but psycopg2 not available. Falling back to SQLite.")
                self.db_type = 'sqlite'
                self.db_path = "db/virtual_trader.sqlite"
            else:
                self._setup_postgres_connection()
        else:
            # Default to SQLite
            self.db_type = 'sqlite'
            self.db_path = "db/virtual_trader.sqlite"
        
        self.logger.info(f"🚀 Initializing {self.db_type.upper()} database manager...")
        self._ensure_db_directory()
        self._create_tables()
        self._initialize_portfolio()
        self.logger.info(f"✅ {self.db_type.upper()} database manager initialized successfully")
    
    def _setup_postgres_connection(self):
        """Setup PostgreSQL connection parameters"""
        self.pg_config = {
            'host': getattr(self.bot_config, 'virtual_trader_database_host', '127.0.0.1'),
            'port': getattr(self.bot_config, 'virtual_trader_database_port', 5432),
            'database': getattr(self.bot_config, 'virtual_trader_database_name', 'virtual_trader'),
            'user': getattr(self.bot_config, 'virtual_trader_database_user', 'trader'),
            'password': getattr(self.bot_config, 'virtual_trader_database_password', '')
        }
        
        # Test connection immediately
        try:
            test_conn = psycopg2.connect(**self.pg_config)
            test_conn.close()
            self.logger.info(f"✅ PostgreSQL connection test successful: {self.pg_config['host']}:{self.pg_config['port']}")
        except psycopg2.OperationalError as e:
            error_msg = str(e)
            if "connection refused" in error_msg.lower():
                self.logger.error(f"❌ Cannot connect to PostgreSQL: Server is not running or port {self.pg_config['port']} is closed")
            elif "authentication failed" in error_msg.lower():
                self.logger.error(f"❌ Cannot connect to PostgreSQL: Wrong username/password for user '{self.pg_config['user']}'")
            elif "does not exist" in error_msg.lower():
                self.logger.error(f"❌ Cannot connect to PostgreSQL: Database '{self.pg_config['database']}' does not exist")
            elif "timeout" in error_msg.lower():
                self.logger.error(f"❌ Cannot connect to PostgreSQL: Connection timeout - server may be down or firewall blocking")
            else:
                self.logger.error(f"❌ Cannot connect to PostgreSQL: {error_msg}")
            raise
        except Exception as e:
            self.logger.error(f"❌ Cannot connect to PostgreSQL: Unexpected error - {str(e)}")
            raise
    
    def _get_connection(self):
        """Get database connection based on type"""
        if self.db_type == 'postgres':
            try:
                conn = psycopg2.connect(**self.pg_config)
                # Log successful connection on first connect
                if not hasattr(self, '_first_connection_logged'):
                    self.logger.info("✅ Successfully connected to PostgreSQL database!")
                    self._first_connection_logged = True
                return conn
            except Exception as e:
                self.logger.error(f"PostgreSQL connection failed: {e}")
                raise
        else:
            if not hasattr(self, '_first_connection_logged'):
                self.logger.info("✅ Successfully connected to SQLite database!")
                self._first_connection_logged = True
            return sqlite3.connect(self.db_path)
    
    def _ensure_db_directory(self):
        """Ensure database directory exists (for SQLite)"""
        if self.db_type == 'sqlite':
            db_dir = os.path.dirname(self.db_path)
            if not os.path.exists(db_dir):
                os.makedirs(db_dir, exist_ok=True)
                self.logger.info(f"📁 Created database directory: {db_dir}")
            else:
                self.logger.info(f"📁 Using existing database directory: {db_dir}")
    
    def _create_tables(self):
        """Create all required database tables"""
        self.logger.info(f"🔧 Setting up {self.db_type.upper()} database for virtual trading...")
        
        if self.db_type == 'postgres':
            self._create_postgres_tables()
        else:
            self._create_sqlite_tables()
    
    def _create_postgres_tables(self):
        """Create PostgreSQL tables"""
        tables = {
            'portfolio': '''
                CREATE TABLE IF NOT EXISTS portfolio (
                    id SERIAL PRIMARY KEY,
                    coin_symbol VARCHAR(20) UNIQUE NOT NULL,
                    amount DECIMAL(20,8) DEFAULT 0.0,
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''',
            'transactions': '''
                CREATE TABLE IF NOT EXISTS transactions (
                    id SERIAL PRIMARY KEY,
                    coin_symbol VARCHAR(20) NOT NULL,
                    transaction_type VARCHAR(20) NOT NULL,
                    amount DECIMAL(20,8) NOT NULL,
                    price DECIMAL(20,8) NOT NULL,
                    total_value DECIMAL(20,8) NOT NULL,
                    strategy_type VARCHAR(50) NOT NULL,
                    signal_id VARCHAR(100),
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''',
            'signals': '''
                CREATE TABLE IF NOT EXISTS signals (
                    id SERIAL PRIMARY KEY,
                    strategy_name VARCHAR(50) NOT NULL,
                    coin_symbol VARCHAR(20) NOT NULL,
                    signal_type VARCHAR(20) NOT NULL,
                    signal_strength VARCHAR(20) NOT NULL,
                    price DECIMAL(20,8) NOT NULL,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    executed BOOLEAN DEFAULT FALSE,
                    execution_timestamp TIMESTAMP NULL,
                    notes TEXT
                )
            '''
        }
        
        with self._get_connection() as conn:
            with conn.cursor() as cursor:
                for table_name, sql in tables.items():
                    cursor.execute(sql)
                    self.logger.debug(f"Created/verified PostgreSQL table: {table_name}")
                conn.commit()
                self.logger.info("PostgreSQL database tables created/verified successfully")
    
    def _create_sqlite_tables(self):
        """Create SQLite tables"""
        tables = {
            'portfolio': '''
                CREATE TABLE IF NOT EXISTS portfolio (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    coin_symbol TEXT UNIQUE NOT NULL,
                    amount REAL DEFAULT 0.0,
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''',
            'transactions': '''
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
            ''',
            'signals': '''
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
            '''
        }
        
        # SQLite cursors don't support context manager
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        for table_name, sql in tables.items():
            cursor.execute(sql)
            self.logger.debug(f"Created/verified SQLite table: {table_name}")
        cursor.close()
        conn.commit()
        conn.close()
        self.logger.info("SQLite database tables created/verified successfully")
    
    def _initialize_portfolio(self):
        """Initialize portfolio with starting USD balance"""
        with self._get_connection() as conn:
            if self.db_type == 'postgres':
                with conn.cursor() as cursor:
                    # Check if USD already exists
                    cursor.execute('SELECT amount FROM portfolio WHERE coin_symbol = %s', ('USD',))
                    if not cursor.fetchone():
                        # Initialize with 10,000 USD
                        cursor.execute('''
                            INSERT INTO portfolio (coin_symbol, amount, last_updated)
                            VALUES (%s, %s, CURRENT_TIMESTAMP)
                        ''', ('USD', 10000.0))
                        
                        # Log initial transaction
                        cursor.execute('''
                            INSERT INTO transactions 
                            (coin_symbol, transaction_type, amount, price, total_value, strategy_type, signal_id)
                            VALUES (%s, %s, %s, %s, %s, %s, %s)
                        ''', ('USD', 'INITIAL', 10000.0, 1.0, 10000.0, 'SYSTEM', 'initial_setup'))
                        
                        self.logger.info("🎉 First time setup: Initialized PostgreSQL portfolio with 10,000 USD")
                        conn.commit()
                    else:
                        self.logger.info("✅ PostgreSQL portfolio already initialized")
            else:
                # SQLite cursors don't support context manager
                cursor = conn.cursor()
                # Check if USD already exists
                cursor.execute('SELECT amount FROM portfolio WHERE coin_symbol = ?', ('USD',))
                if not cursor.fetchone():
                    # Initialize with 10,000 USD
                    cursor.execute('''
                        INSERT INTO portfolio (coin_symbol, amount, last_updated)
                        VALUES (?, ?, CURRENT_TIMESTAMP)
                    ''', ('USD', 10000.0))
                    
                    # Log initial transaction
                    cursor.execute('''
                        INSERT INTO transactions 
                        (coin_symbol, transaction_type, amount, price, total_value, strategy_type, signal_id)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    ''', ('USD', 'INITIAL', 10000.0, 1.0, 10000.0, 'SYSTEM', 'initial_setup'))
                    
                    self.logger.info("🎉 First time setup: Initialized SQLite portfolio with 10,000 USD")
                    conn.commit()
                else:
                    self.logger.info("✅ SQLite portfolio already initialized")
                cursor.close()
    
    def get_coin_balance(self, coin_symbol: str) -> float:
        """Get current balance of a coin"""
        with self._get_connection() as conn:
            if self.db_type == 'postgres':
                with conn.cursor() as cursor:
                    cursor.execute('SELECT amount FROM portfolio WHERE coin_symbol = %s', (coin_symbol,))
                    result = cursor.fetchone()
                    return float(result[0]) if result else 0.0
            else:
                # SQLite cursors don't support context manager
                cursor = conn.cursor()
                cursor.execute('SELECT amount FROM portfolio WHERE coin_symbol = ?', (coin_symbol,))
                result = cursor.fetchone()
                cursor.close()
                return result[0] if result else 0.0
    
    def update_coin_balance(self, coin_symbol: str, new_amount: float):
        """Update coin balance in portfolio"""
        with self._get_connection() as conn:
            if self.db_type == 'postgres':
                with conn.cursor() as cursor:
                    cursor.execute('''
                        INSERT INTO portfolio (coin_symbol, amount, last_updated)
                        VALUES (%s, %s, CURRENT_TIMESTAMP)
                        ON CONFLICT (coin_symbol) DO UPDATE SET
                        amount = EXCLUDED.amount,
                        last_updated = CURRENT_TIMESTAMP
                    ''', (coin_symbol, new_amount))
            else:
                # SQLite cursors don't support context manager
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT OR REPLACE INTO portfolio (coin_symbol, amount, last_updated)
                    VALUES (?, ?, CURRENT_TIMESTAMP)
                ''', (coin_symbol, new_amount))
                cursor.close()
    
    def log_transaction(self, coin_symbol: str, transaction_type: str, amount: float, 
                       price: float, strategy_type: str, signal_id: Optional[str] = None):
        """Log a transaction to the database"""
        total_value = amount * price
        with self._get_connection() as conn:
            if self.db_type == 'postgres':
                with conn.cursor() as cursor:
                    cursor.execute('''
                        INSERT INTO transactions 
                        (coin_symbol, transaction_type, amount, price, total_value, strategy_type, signal_id)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ''', (coin_symbol, transaction_type, amount, price, total_value, strategy_type, signal_id))
            else:
                # SQLite cursors don't support context manager
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO transactions 
                    (coin_symbol, transaction_type, amount, price, total_value, strategy_type, signal_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (coin_symbol, transaction_type, amount, price, total_value, strategy_type, signal_id))
                cursor.close()
    
    def save_signal(self, signal: TradeSignal):
        """Save a trading signal to the database"""
        with self._get_connection() as conn:
            if self.db_type == 'postgres':
                with conn.cursor() as cursor:
                    cursor.execute('''
                        INSERT INTO signals 
                        (strategy_name, coin_symbol, signal_type, signal_strength, price, timestamp)
                        VALUES (%s, %s, %s, %s, %s, %s)
                    ''', (signal.strategy_name, signal.coin_symbol, signal.signal_type, 
                          signal.signal_strength, signal.price, signal.timestamp))
            else:
                # SQLite cursors don't support context manager
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO signals 
                    (strategy_name, coin_symbol, signal_type, signal_strength, price, timestamp)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (signal.strategy_name, signal.coin_symbol, signal.signal_type, 
                      signal.signal_strength, signal.price, signal.timestamp))
                cursor.close()
    
    def get_signals(self, strategy_name: Optional[str] = None, coin_symbol: Optional[str] = None, 
                   limit: int = 10) -> List[Tuple]:
        """Get trading signals with optional filters"""
        query = 'SELECT * FROM signals WHERE 1=1'
        params = []
        
        if strategy_name:
            query += ' AND strategy_name = %s' if self.db_type == 'postgres' else ' AND strategy_name = ?'
            params.append(strategy_name)
        if coin_symbol:
            query += ' AND coin_symbol = %s' if self.db_type == 'postgres' else ' AND coin_symbol = ?'
            params.append(coin_symbol)
        
        query += ' ORDER BY timestamp DESC LIMIT %s' if self.db_type == 'postgres' else ' ORDER BY timestamp DESC LIMIT ?'
        params.append(limit)
        
        with self._get_connection() as conn:
            if self.db_type == 'postgres':
                with conn.cursor() as cursor:
                    cursor.execute(query, params)
                    return cursor.fetchall()
            else:
                # SQLite cursors don't support context manager
                cursor = conn.cursor()
                cursor.execute(query, params)
                result = cursor.fetchall()
                cursor.close()
                return result
    
    def get_portfolio_summary(self) -> List[Tuple]:
        """Get summary of all coin holdings"""
        with self._get_connection() as conn:
            if self.db_type == 'postgres':
                with conn.cursor() as cursor:
                    cursor.execute('SELECT coin_symbol, amount, last_updated FROM portfolio WHERE amount > 0')
                    return cursor.fetchall()
            else:
                # SQLite cursors don't support context manager
                cursor = conn.cursor()
                cursor.execute('SELECT coin_symbol, amount, last_updated FROM portfolio WHERE amount > 0')
                result = cursor.fetchall()
                cursor.close()
                return result
    
    def get_transaction_history(self, coin_symbol: Optional[str] = None, limit: int = 10) -> List[Tuple]:
        """Get recent transaction history"""
        with self._get_connection() as conn:
            if self.db_type == 'postgres':
                with conn.cursor() as cursor:
                    if coin_symbol:
                        cursor.execute('''
                            SELECT coin_symbol, transaction_type, amount, price, total_value, strategy_type, timestamp
                            FROM transactions WHERE coin_symbol = %s ORDER BY timestamp DESC LIMIT %s
                        ''', (coin_symbol, limit))
                    else:
                        cursor.execute('''
                            SELECT coin_symbol, transaction_type, amount, price, total_value, strategy_type, timestamp
                            FROM transactions ORDER BY timestamp DESC LIMIT %s
                        ''', (limit,))
                    return cursor.fetchall()
            else:
                # SQLite cursors don't support context manager
                cursor = conn.cursor()
                if coin_symbol:
                    cursor.execute('''
                        SELECT coin_symbol, transaction_type, amount, price, total_value, strategy_type, timestamp
                        FROM transactions WHERE coin_symbol = ? ORDER BY timestamp DESC LIMIT ?
                    ''', (coin_symbol, limit))
                else:
                    cursor.execute('''
                        SELECT coin_symbol, transaction_type, amount, price, total_value, strategy_type, timestamp
                        FROM transactions ORDER BY timestamp DESC LIMIT ?
                    ''', (limit,))
                result = cursor.fetchall()
                cursor.close()
                return result

# ============================================================================
# PRICE MANAGER
# ============================================================================

class PriceManager:
    """Handles price fetching from external APIs"""
    
    def __init__(self):
        self.logger = logging.getLogger("PriceManager")
    
    def get_current_price(self, coin_symbol: str) -> Optional[float]:
        """Get current price from Coinbase API"""
        try:
            url = f"https://api.coinbase.com/v2/prices/{coin_symbol}/spot"
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            return float(data['data']['amount'])
            
        except Exception as e:
            self.logger.error(f"Error fetching price for {coin_symbol}: {e}")
            return None

# ============================================================================
# TRADING ENGINE
# ============================================================================

class TradingEngine:
    """Core trading logic and execution"""
    
    def __init__(self, db_manager: DatabaseManager, price_manager: PriceManager):
        self.db = db_manager
        self.price_manager = price_manager
        self.logger = logging.getLogger("TradingEngine")
    
    def execute_buy(self, coin_symbol: str, amount: float, price: float, 
                    strategy_type: str, signal_id: Optional[str] = None) -> bool:
        """Execute a buy transaction"""
        if coin_symbol == "USD":
            self.logger.warning("Cannot buy USD as it's the primary wallet currency")
            return False
        
        total_usd_cost = amount * price
        usd_balance = self.db.get_coin_balance("USD")
        usd_balance_float = float(usd_balance)
        
        if usd_balance_float < total_usd_cost:
            self.logger.warning(f"Insufficient USD balance: {usd_balance_float:.2f} < {total_usd_cost:.2f}")
            return False
        
        # Execute the trade
        self.db.update_coin_balance("USD", usd_balance_float - total_usd_cost)
        current_balance = self.db.get_coin_balance(coin_symbol)
        current_balance_float = float(current_balance)
        self.db.update_coin_balance(coin_symbol, current_balance_float + amount)
        
        # Log transactions
        self.db.log_transaction(coin_symbol, "BUY", amount, price, strategy_type, signal_id)
        self.db.log_transaction("USD", "SPEND", total_usd_cost, 1.0, strategy_type, signal_id)
        
        self.logger.info(f"BUY: {amount} {coin_symbol} at ${price:.2f} for ${total_usd_cost:.2f} USD via {strategy_type}")
        return True
    
    def execute_sell(self, coin_symbol: str, amount: float, price: float, 
                     strategy_type: str, signal_id: Optional[str] = None) -> bool:
        """Execute a sell transaction"""
        if coin_symbol == "USD":
            self.logger.warning("Cannot sell USD as it's the primary wallet currency")
            return False
        
        current_balance = self.db.get_coin_balance(coin_symbol)
        current_balance_float = float(current_balance)
        if current_balance_float < amount:
            self.logger.warning(f"Insufficient balance for {coin_symbol}: {current_balance_float} < {amount}")
            return False
        
        total_usd_value = amount * price
        
        # Execute the trade
        self.db.update_coin_balance(coin_symbol, current_balance_float - amount)
        usd_balance = self.db.get_coin_balance("USD")
        usd_balance_float = float(usd_balance)
        self.db.update_coin_balance("USD", usd_balance_float + total_usd_value)
        
        # Log transactions
        self.db.log_transaction(coin_symbol, "SELL", amount, price, strategy_type, signal_id)
        self.db.log_transaction("USD", "RECEIVE", total_usd_value, 1.0, strategy_type, signal_id)
        
        self.logger.info(f"SELL: {amount} {coin_symbol} at ${price:.2f} for ${total_usd_value:.2f} USD via {strategy_type}")
        return True
    
    def calculate_trade_size(self, signal_strength: str, usd_balance: float) -> float:
        """Calculate trade size based on signal strength"""
        strength_multipliers = {
            "Low": 0.25,
            "Medium": 0.50,
            "Strong": 0.75
        }
        multiplier = strength_multipliers.get(signal_strength, 0.25)
        return usd_balance * multiplier

# ============================================================================
# STRATEGY MANAGER
# ============================================================================

class StrategyManager:
    """Manages trading strategies and their configurations"""
    
    def __init__(self):
        self.strategies = self._create_default_strategies()
    
    def _create_default_strategies(self) -> Dict[str, StrategyConfig]:
        """Create default strategy configurations"""
        return {
            "day": StrategyConfig(
                name="Day Trader",
                strategy_name="Day Trader",
                product_ids=["BTC-USD", "ETH-USD", "AVAX-USD", "SOL-USD", "ADA-USD"],
                granularity_signal="FIVE_MINUTE",
                granularity_trend="ONE_HOUR",
                trend_indicator="EMA",
                trend_period=50,
                signal_indicator="EMA",
                short_period=9,
                long_period=21,
                rsi_period=14,
                rsi_overbought=70,
                rsi_oversold=30,
                macd_fast=12,
                macd_slow=26,
                macd_signal=9,
                atr_period=14,
                volume_filter_enabled=True,
                volume_ma_period=20,
                volume_spike_multiplier=2.0,
                hypothetical_portfolio_size=100000.0,
                risk_per_trade_percentage=0.5,
                atr_stop_loss_multiplier=2.0,
                interval=5
            ),
            "swing": StrategyConfig(
                name="Swing Trader",
                strategy_name="Aggressive Swing Trader",
                product_ids=["BTC-USD", "ETH-USD", "AVAX-USD", "SOL-USD", "ADA-USD"],
                granularity_signal="FOUR_HOUR",
                granularity_trend="ONE_DAY",
                trend_indicator="EMA",
                trend_period=50,
                signal_indicator="EMA",
                short_period=20,
                long_period=50,
                rsi_period=14,
                rsi_overbought=75,
                rsi_oversold=25,
                macd_fast=12,
                macd_slow=26,
                macd_signal=9,
                atr_period=14,
                volume_filter_enabled=True,
                volume_ma_period=20,
                volume_spike_multiplier=1.5,
                hypothetical_portfolio_size=100000.0,
                risk_per_trade_percentage=1.0,
                atr_stop_loss_multiplier=2.5,
                interval=4
            ),
            "long": StrategyConfig(
                name="Long Term",
                strategy_name="Long-Term Investor",
                product_ids=["BTC-USD", "ETH-USD", "AVAX-USD", "SOL-USD", "ADA-USD"],
                granularity_signal="ONE_DAY",
                granularity_trend="ONE_WEEK",
                trend_indicator="SMA",
                trend_period=30,
                signal_indicator="SMA",
                short_period=50,
                long_period=200,
                rsi_period=14,
                rsi_overbought=80,
                rsi_oversold=20,
                macd_fast=12,
                macd_slow=26,
                macd_signal=9,
                atr_period=14,
                volume_filter_enabled=True,
                volume_ma_period=20,
                volume_spike_multiplier=1.5,
                hypothetical_portfolio_size=100000.0,
                risk_per_trade_percentage=1.0,
                atr_stop_loss_multiplier=2.5,
                interval=24
            )
        }
    
    def get_strategy(self, strategy_key: str) -> Optional[StrategyConfig]:
        """Get a strategy configuration by key"""
        return self.strategies.get(strategy_key)
    
    def add_coin_to_strategy(self, strategy_key: str, coin: str) -> bool:
        """Add a coin to a strategy's product IDs"""
        strategy = self.strategies.get(strategy_key)
        if not strategy or coin in strategy.product_ids:
            return False
        
        strategy.product_ids.append(coin)
        return True
    
    def remove_coin_from_strategy(self, strategy_key: str, coin: str) -> bool:
        """Remove a coin from a strategy's product IDs"""
        strategy = self.strategies.get(strategy_key)
        if not strategy or coin not in strategy.product_ids:
            return False
        
        strategy.product_ids.remove(coin)
        return True
    
    def get_strategy_coins(self, strategy_key: str) -> List[str]:
        """Get all coins for a strategy"""
        strategy = self.strategies.get(strategy_key)
        return strategy.product_ids if strategy else []
    
    def convert_to_tokenometry_config(self, strategy: StrategyConfig) -> Dict:
        """Convert StrategyConfig to Tokenometry format"""
        return {
            "STRATEGY_NAME": strategy.strategy_name,
            "PRODUCT_IDS": strategy.product_ids,
            "GRANULARITY_SIGNAL": strategy.granularity_signal,
            "GRANULARITY_TREND": strategy.granularity_trend,
            "GRANULARITY_SECONDS": {
                "ONE_HOUR": 3600,
                "FIVE_MINUTE": 300,
                "ONE_DAY": 86400,
                "FOUR_HOUR": 14400,
                "ONE_WEEK": 604800
            },
            "TREND_INDICATOR_TYPE": strategy.trend_indicator,
            "TREND_PERIOD": strategy.trend_period,
            "SIGNAL_INDICATOR_TYPE": strategy.signal_indicator,
            "SHORT_PERIOD": strategy.short_period,
            "LONG_PERIOD": strategy.long_period,
            "RSI_PERIOD": strategy.rsi_period,
            "RSI_OVERBOUGHT": strategy.rsi_overbought,
            "RSI_OVERSOLD": strategy.rsi_oversold,
            "MACD_FAST": strategy.macd_fast,
            "MACD_SLOW": strategy.macd_slow,
            "MACD_SIGNAL": strategy.macd_signal,
            "ATR_PERIOD": strategy.atr_period,
            "VOLUME_FILTER_ENABLED": strategy.volume_filter_enabled,
            "VOLUME_MA_PERIOD": strategy.volume_ma_period,
            "VOLUME_SPIKE_MULTIPLIER": strategy.volume_spike_multiplier,
            "HYPOTHETICAL_PORTFOLIO_SIZE": strategy.hypothetical_portfolio_size,
            "RISK_PER_TRADE_PERCENTAGE": strategy.risk_per_trade_percentage,
            "ATR_STOP_LOSS_MULTIPLIER": strategy.atr_stop_loss_multiplier
        }

# ============================================================================
# SIGNAL MONITOR
# ============================================================================

class SignalMonitor:
    """Monitors and processes trading signals"""
    
    def __init__(self, strategy_manager: StrategyManager, trading_engine: TradingEngine, 
                 db_manager: DatabaseManager, price_manager: PriceManager):
        self.strategy_manager = strategy_manager
        self.trading_engine = trading_engine
        self.db_manager = db_manager
        self.price_manager = price_manager
        self.logger = logging.getLogger("SignalMonitor")
        self.is_running = False
    
    def start(self):
        """Start the signal monitoring"""
        self.is_running = True
        self.logger.info("Signal monitor started")
    
    def stop(self):
        """Stop the signal monitoring"""
        self.is_running = False
        self.logger.info("Signal monitor stopped")
    
    def is_running(self) -> bool:
        """Check if monitor is running"""
        return self.is_running
    
    def process_signals(self):
        """Process signals from all strategies"""
        if not self.is_running:
            return
        
        for strategy_key, strategy in self.strategy_manager.strategies.items():
            try:
                # Create Tokenometry scanner
                config = self.strategy_manager.convert_to_tokenometry_config(strategy)
                scanner = Tokenometry(config=config, logger=self.logger)
                
                # Scan for signals
                signals = scanner.scan()
                if signals:
                    self._process_strategy_signals(strategy_key, signals)
                    
            except Exception as e:
                self.logger.error(f"Error processing {strategy_key} strategy: {e}")
    
    def _process_strategy_signals(self, strategy_key: str, signals: List):
        """Process signals for a specific strategy"""
        usd_balance = self.db_manager.get_coin_balance("USD")
        
        # Sort signals by strength (Strong > Medium > Low)
        strength_order = {"Strong": 3, "Medium": 2, "Low": 1}
        sorted_signals = sorted(signals, key=lambda s: strength_order.get(s.get('signal_strength', 'Low'), 0), reverse=True)
        
        remaining_usd = usd_balance
        
        for signal in sorted_signals:
            if signal.get('signal_type') in ['BUY', 'SELL']:
                coin_symbol = signal.get('coin_symbol')
                signal_strength = signal.get('signal_strength', 'Low')
                
                # Get current price
                current_price = self.price_manager.get_current_price(coin_symbol)
                if not current_price:
                    continue
                
                # Create trade signal
                trade_signal = TradeSignal(
                    strategy_name=strategy_key,
                    coin_symbol=coin_symbol,
                    signal_type=signal.get('signal_type'),
                    signal_strength=signal_strength,
                    price=current_price,
                    timestamp=datetime.now(),
                    signal_id=f"{strategy_key}_{coin_symbol}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                )
                
                # Save signal to database
                self.db_manager.save_signal(trade_signal)
                
                # Execute trade based on signal type
                if signal.get('signal_type') == 'BUY' and remaining_usd > 0:
                    trade_size = self.trading_engine.calculate_trade_size(signal_strength, remaining_usd)
                    if trade_size <= remaining_usd:
                        amount = trade_size / current_price
                        if self.trading_engine.execute_buy(coin_symbol, amount, current_price, strategy_key, trade_signal.signal_id):
                            remaining_usd -= trade_size
                
                elif signal.get('signal_type') == 'SELL':
                    coin_balance = self.db_manager.get_coin_balance(coin_symbol)
                    if coin_balance > 0:
                        trade_size = self.trading_engine.calculate_trade_size(signal_strength, coin_balance)
                        amount = min(trade_size, coin_balance)
                        self.trading_engine.execute_sell(coin_symbol, amount, current_price, strategy_key, trade_signal.signal_id)

# ============================================================================
# DISCORD COG
# ============================================================================

class CryptoVirtualTrader(commands.Cog):
    """Discord cog for crypto virtual trading commands"""
    
    def __init__(self, bot: DiscordBot):
        self.bot = bot
        self.logger = logging.getLogger("CryptoVirtualTrader")
        
        # Initialize components
        self.db_manager = DatabaseManager(bot.config)
        self.price_manager = PriceManager()
        self.trading_engine = TradingEngine(self.db_manager, self.price_manager)
        self.strategy_manager = StrategyManager()
        self.signal_monitor = SignalMonitor(
            self.strategy_manager, 
            self.trading_engine, 
            self.db_manager, 
            self.price_manager
        )
        
        # Start signal monitoring
        self.signal_monitor.start()
        self.signal_monitor_task.start()
    

    
    def cog_unload(self):
        """Cleanup when cog is unloaded"""
        self.signal_monitor.stop()
        if self.signal_monitor_task.is_running():
            self.signal_monitor_task.cancel()
    
    @tasks.loop(minutes=1)
    async def signal_monitor_task(self):
        """Background task to monitor signals"""
        self.signal_monitor.process_signals()
    
    @commands.group(name="trader")
    async def trader(self, ctx: CustomContext):
        """Virtual trading commands"""
        if ctx.invoked_subcommand is None:
            await self._show_help(ctx)
    
    async def _show_help(self, ctx: CustomContext):
        """Show help for trader commands"""
        embed = discord.Embed(
            title="🤖 Virtual Trader Commands",
            description="Manage your virtual crypto trading portfolio",
            color=discord.Color.blue(),
            timestamp=discord.utils.utcnow()
        )
        
        commands_info = [
            ("`!trader portfolio`", "View your current portfolio"),
            ("`!trader balance <coin>`", "Check balance of specific coin"),
            ("`!trader history [coin] [limit]`", "View transaction history"),
            ("`!trader buy <coin> <usd_amount>`", "Buy crypto with USD"),
            ("`!trader sell <coin> <crypto_amount>`", "Sell crypto for USD"),
            ("`!trader add_coin <strategy> <coin>`", "Add coin to strategy"),
            ("`!trader remove_coin <strategy> <coin>`", "Remove coin from strategy"),
            ("`!trader status`", "Check scanner status"),
            ("`!trader signals [strategy] [coin] [limit]`", "View signal history"),
            ("`!trader signal <coin> <strength> [type]`", "Test manual signal")
        ]
        
        for cmd, desc in commands_info:
            embed.add_field(name=cmd, value=desc, inline=False)
        
        embed.set_footer(text="Use !trader <command> for more details")
        await ctx.send(embed=embed)
    
    @trader.command()
    async def portfolio(self, ctx: CustomContext):
        """View your current portfolio"""
        portfolio = self.db_manager.get_portfolio_summary()
        
        if not portfolio:
            await ctx.send("❌ **No portfolio data found**")
            return
        
        embed = discord.Embed(
            title="💼 Your Portfolio",
            color=discord.Color.green(),
            timestamp=discord.utils.utcnow()
        )
        
        total_value_usd = 0.0
        
        for coin_symbol, amount, last_updated in portfolio:
            # Convert decimal.Decimal to float for calculations
            amount_float = float(amount)
            
            if coin_symbol == "USD":
                total_value_usd += amount_float
                embed.add_field(
                    name=f"💰 {coin_symbol}",
                    value=f"**Balance:** ${amount_float:,.2f}\n**Type:** Main Wallet",
                    inline=True
                )
            else:
                current_price = self.price_manager.get_current_price(coin_symbol)
                if current_price:
                    coin_value_usd = amount_float * current_price
                    total_value_usd += coin_value_usd
                    embed.add_field(
                        name=f"🪙 {coin_symbol}",
                        value=f"**Amount:** {amount_float:.6f}\n**Price:** ${current_price:.2f}\n**Value:** ${coin_value_usd:.2f}",
                        inline=True
                    )
        
        # Add total portfolio value
        embed.add_field(
            name="📊 Total Portfolio Value",
            value=f"**${total_value_usd:,.2f} USD**",
            inline=False
        )
        
        embed.set_footer(text=f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        await ctx.send(embed=embed)
    
    @trader.command()
    async def balance(self, ctx: CustomContext, coin_symbol: str):
        """Check balance of a specific coin"""
        coin_symbol = coin_symbol.upper()
        balance = self.db_manager.get_coin_balance(coin_symbol)
        
        embed = discord.Embed(
            title=f"💰 {coin_symbol} Balance",
            color=discord.Color.blue(),
            timestamp=discord.utils.utcnow()
        )
        
        # Convert decimal.Decimal to float for calculations
        balance_float = float(balance)
        
        if coin_symbol == "USD":
            embed.add_field(name="Balance", value=f"${balance_float:,.2f}", inline=True)
            embed.add_field(name="Type", value="Main Wallet", inline=True)
        else:
            embed.add_field(name="Amount", value=f"{balance_float:.6f}", inline=True)
            current_price = self.price_manager.get_current_price(coin_symbol)
            if current_price:
                value_usd = balance_float * current_price
                embed.add_field(name="Current Price", value=f"${current_price:.2f}", inline=True)
                embed.add_field(name="Value in USD", value=f"${value_usd:.2f}", inline=True)
        
        await ctx.send(embed=embed)
    
    @trader.command()
    async def buy(self, ctx: CustomContext, coin_symbol: str, usd_amount: float):
        """Buy crypto with USD amount"""
        if usd_amount <= 0:
            await ctx.send("❌ **Error:** USD amount must be positive")
            return
        
        coin_symbol = coin_symbol.upper()
        
        # Prevent buying USD as it's the primary wallet currency
        if coin_symbol == "USD":
            await ctx.send("❌ **Error:** Cannot buy USD as it's the primary wallet currency")
            return
        
        # Check if we have enough USD for the purchase
        usd_balance = self.db_manager.get_coin_balance("USD")
        usd_balance_float = float(usd_balance)
        
        if usd_balance_float < usd_amount:
            await ctx.send(f"❌ **Insufficient USD Balance:** You need ${usd_amount:.2f} USD but only have ${usd_balance_float:.2f} USD")
            return
        
        # Get current price from Coinbase
        current_price = self.price_manager.get_current_price(coin_symbol)
        if current_price is None:
            await ctx.send(f"❌ **Error:** Could not fetch current price for {coin_symbol}")
            return
        
        # Calculate crypto amount from USD
        crypto_amount = usd_amount / current_price
        
        try:
            success = self.trading_engine.execute_buy(coin_symbol, crypto_amount, current_price, "MANUAL", f"manual_{ctx.author.id}")
            
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
                embed.add_field(name="New Balance", value=f"{float(self.db_manager.get_coin_balance(coin_symbol)):.8f} {coin_symbol}", inline=True)
                embed.add_field(name="USD Balance", value=f"{float(self.db_manager.get_coin_balance('USD')):.2f} USD", inline=True)
                
                await ctx.send(embed=embed)
            else:
                await ctx.send("❌ **Error:** Failed to execute buy order")
                
        except Exception as e:
            self.logger.error(f"Error executing buy order: {e}")
            await ctx.send(f"❌ **Error:** {str(e)}")
    
    @trader.command()
    async def sell(self, ctx: CustomContext, coin_symbol: str, crypto_amount: float):
        """Sell crypto for USD"""
        if crypto_amount <= 0:
            await ctx.send("❌ **Error:** Crypto amount must be positive")
            return
        
        coin_symbol = coin_symbol.upper()
        
        # Prevent selling USD as it's the primary wallet currency
        if coin_symbol == "USD":
            await ctx.send("❌ **Error:** Cannot sell USD as it's the primary wallet currency")
            return
        
        # Check if we have enough of the crypto to sell
        current_balance = self.db_manager.get_coin_balance(coin_symbol)
        current_balance_float = float(current_balance)
        
        if current_balance_float < crypto_amount:
            await ctx.send(f"❌ **Insufficient Balance:** You only have {current_balance_float:.8f} {coin_symbol}")
            return
        
        # Get current price from Coinbase
        current_price = self.price_manager.get_current_price(coin_symbol)
        if current_price is None:
            await ctx.send(f"❌ **Error:** Could not fetch current price for {coin_symbol}")
            return
        
        # Calculate USD value from crypto amount
        usd_value = crypto_amount * current_price
        
        try:
            success = self.trading_engine.execute_sell(coin_symbol, crypto_amount, current_price, "MANUAL", f"manual_{ctx.author.id}")
            
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
                embed.add_field(name="Remaining Balance", value=f"{float(self.db_manager.get_coin_balance(coin_symbol)):.8f} {coin_symbol}", inline=True)
                embed.add_field(name="USD Balance", value=f"{float(self.db_manager.get_coin_balance('USD')):.2f} USD", inline=True)
                
                await ctx.send(embed=embed)
            else:
                await ctx.send("❌ **Error:** Failed to execute sell order")
                
        except Exception as e:
            self.logger.error(f"Error executing sell order: {e}")
            await ctx.send(f"❌ **Error:** {str(e)}")
    
    @trader.command()
    async def history(self, ctx: CustomContext, coin_symbol: str = None, limit: int = 10):
        """View transaction history"""
        if not await self._check_channel(ctx):
            return
        
        transactions = self.db_manager.get_transaction_history(coin_symbol, limit)
        
        if not transactions:
            await ctx.send("❌ **No transaction history found**")
            return
        
        embed = discord.Embed(
            title="📜 Transaction History",
            color=discord.Color.blue(),
            timestamp=discord.utils.utcnow()
        )
        
        for coin, tx_type, amount, price, total_value, strategy, timestamp in transactions:
            embed.add_field(
                name=f"{tx_type} {coin}",
                value=f"**Amount:** {amount:.6f}\n**Price:** ${price:.2f}\n**Total:** ${total_value:.2f}\n**Strategy:** {strategy}\n**Time:** {timestamp}",
                inline=False
            )
        
        embed.set_footer(text=f"Showing last {len(transactions)} transactions")
        await ctx.send(embed=embed)
    
    @trader.command()
    async def add_coin(self, ctx: CustomContext, strategy: str, coin: str):
        """Add a coin to a strategy's product IDs"""
        strategy = strategy.lower()
        coin = coin.upper()
        
        if strategy not in self.strategy_manager.strategies:
            valid_strategies = ", ".join(self.strategy_manager.strategies.keys())
            await ctx.send(f"❌ **Invalid Strategy:** Must be one of: {valid_strategies}")
            return
        
        if not coin.endswith('-USD'):
            await ctx.send("❌ **Invalid Coin Format:** Coin must end with '-USD' (e.g., BTC-USD)")
            return
        
        if self.strategy_manager.add_coin_to_strategy(strategy, coin):
            embed = discord.Embed(
                title="✅ Coin Added Successfully",
                color=discord.Color.green(),
                timestamp=discord.utils.utcnow()
            )
            embed.add_field(name="Strategy", value=strategy.title(), inline=True)
            embed.add_field(name="Coin Added", value=coin, inline=True)
            embed.add_field(name="Total Coins", value=len(self.strategy_manager.get_strategy_coins(strategy)), inline=True)
            await ctx.send(embed=embed)
        else:
            await ctx.send(f"❌ **Coin Already Exists:** {coin} is already in {strategy} strategy")
    
    @trader.command()
    async def remove_coin(self, ctx: CustomContext, strategy: str, coin: str):
        """Remove a coin from a strategy's product IDs"""
        strategy = strategy.lower()
        coin = coin.upper()
        
        if strategy not in self.strategy_manager.strategies:
            valid_strategies = ", ".join(self.strategy_manager.strategies.keys())
            await ctx.send(f"❌ **Invalid Strategy:** Must be one of: {valid_strategies}")
            return
        
        if self.strategy_manager.remove_coin_from_strategy(strategy, coin):
            embed = discord.Embed(
                title="✅ Coin Removed Successfully",
                color=discord.Color.red(),
                timestamp=discord.utils.utcnow()
            )
            embed.add_field(name="Strategy", value=strategy.title(), inline=True)
            embed.add_field(name="Coin Removed", value=coin, inline=True)
            embed.add_field(name="Remaining Coins", value=len(self.strategy_manager.get_strategy_coins(strategy)), inline=True)
            await ctx.send(embed=embed)
        else:
            await ctx.send(f"❌ **Coin Not Found:** {coin} is not in {strategy} strategy")
    
    @trader.command()
    async def status(self, ctx: CustomContext):
        """Check the status of all trading scanners"""
        embed = discord.Embed(
            title="🔍 Scanner Status Report",
            color=discord.Color.blue(),
            timestamp=discord.utils.utcnow()
        )
        
        for strategy_key, strategy in self.strategy_manager.strategies.items():
            try:
                # Test scanner
                config = self.strategy_manager.convert_to_tokenometry_config(strategy)
                scanner = Tokenometry(config=config, logger=self.logger)
                test_signals = scanner.scan()
                
                if test_signals is not None:
                    status_emoji = "🟢"
                    status_text = "Active"
                    signal_count = len(test_signals) if test_signals else 0
                    
                    embed.add_field(
                        name=f"{status_emoji} {strategy.name}",
                        value=f"**Status:** {status_text}\n**Interval:** {strategy.interval} {'minutes' if strategy.interval < 60 else 'hours'}\n**Products:** {len(strategy.product_ids)} coins\n**Coins:** {', '.join(strategy.product_ids)}\n**Last Check:** {datetime.now().strftime('%H:%M:%S')}\n**Signals Found:** {signal_count}",
                        inline=False
                    )
                else:
                    embed.add_field(
                        name=f"🟡 {strategy.name}",
                        value=f"**Status:** Warning - No Response\n**Interval:** {strategy.interval} {'minutes' if strategy.interval < 60 else 'hours'}\n**Products:** {len(strategy.product_ids)} coins\n**Coins:** {', '.join(strategy.product_ids)}\n**Last Check:** {datetime.now().strftime('%H:%M:%S')}\n**Issue:** Scanner returned no data",
                        inline=False
                    )
                    
            except Exception as e:
                embed.add_field(
                    name=f"🔴 {strategy.name}",
                    value=f"**Status:** Error\n**Interval:** {strategy.interval} {'minutes' if strategy.interval < 60 else 'hours'}\n**Products:** {len(strategy.product_ids)} coins\n**Coins:** {', '.join(strategy.product_ids)}\n**Last Check:** {datetime.now().strftime('%H:%M:%S')}\n**Error:** {str(e)[:50]}...",
                    inline=False
                )
        
        # System status
        signal_monitor_status = "🟢 Running" if self.signal_monitor.is_running else "🔴 Stopped"
        embed.add_field(
            name="📊 System Status",
            value=f"**Signal Monitor:** {signal_monitor_status}\n**Total Strategies:** {len(self.strategy_manager.strategies)}\n**Database:** Connected\n**Last Update:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            inline=False
        )
        
        embed.set_footer(text="Scanner health check completed")
        await ctx.send(embed=embed)
    
    @trader.command()
    async def signals(self, ctx: CustomContext, strategy_name: str = None, coin_symbol: str = None, limit: int = 10):
        """View trading signal history"""
        signals = self.db_manager.get_signals(strategy_name, coin_symbol, limit)
        
        if not signals:
            await ctx.send("❌ **No signals found**")
            return
        
        embed = discord.Embed(
            title="📡 Trading Signals",
            color=discord.Color.blue(),
            timestamp=discord.utils.utcnow()
        )
        
        for signal in signals:
            embed.add_field(
                name=f"{signal[3]} {signal[2]}",
                value=f"**Strategy:** {signal[1]}\n**Strength:** {signal[4]}\n**Price:** ${signal[5]:.2f}\n**Time:** {signal[6]}",
                inline=False
            )
        
        embed.set_footer(text=f"Showing last {len(signals)} signals")
        await ctx.send(embed=embed)
    
    @trader.command()
    async def signal(self, ctx: CustomContext, coin: str, strength: str, signal_type: str = "BUY"):
        """Test manual trading signal"""
        coin = coin.upper()
        strength = strength.capitalize()
        signal_type = signal_type.upper()
        
        if not coin.endswith('-USD'):
            await ctx.send("❌ **Invalid Coin Format:** Coin must end with '-USD'")
            return
        
        if strength not in ["Low", "Medium", "Strong"]:
            await ctx.send("❌ **Invalid Strength:** Must be Low, Medium, or Strong")
            return
        
        if signal_type not in ["BUY", "SELL"]:
            await ctx.send("❌ **Invalid Signal Type:** Must be BUY or SELL")
            return
        
        current_price = self.price_manager.get_current_price(coin)
        if not current_price:
            await ctx.send(f"❌ **Price Error:** Could not fetch current price for {coin}")
            return
        
        # Create test signal
        test_signal = TradeSignal(
            strategy_name="MANUAL",
            coin_symbol=coin,
            signal_type=signal_type,
            signal_strength=strength,
            price=current_price,
            timestamp=datetime.now(),
            signal_id=f"manual_{coin}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        )
        
        # Save signal
        self.db_manager.save_signal(test_signal)
        
        # Execute the trade based on signal
        trade_executed = False
        trade_details = ""
        
        try:
            if signal_type == "BUY":
                # Calculate trade size based on signal strength
                usd_balance = self.db_manager.get_coin_balance("USD")
                trade_size_usd = self.trading_engine.calculate_trade_size(strength, usd_balance)
                
                if trade_size_usd <= usd_balance:
                    crypto_amount = trade_size_usd / current_price
                    success = self.trading_engine.execute_buy(coin, crypto_amount, current_price, "MANUAL", test_signal.signal_id)
                    
                    if success:
                        trade_executed = True
                        trade_details = f"✅ **BUY Executed:** {crypto_amount:.8f} {coin} for ${trade_size_usd:.2f} USD"
                    else:
                        trade_details = f"❌ **BUY Failed:** Insufficient USD balance or other error"
                else:
                    trade_details = f"❌ **BUY Failed:** Insufficient USD balance (${usd_balance:.2f} < ${trade_size_usd:.2f})"
            
            elif signal_type == "SELL":
                # Calculate trade size based on signal strength
                crypto_balance = self.db_manager.get_coin_balance(coin)
                trade_size_crypto = self.trading_engine.calculate_trade_size(strength, crypto_balance)
                
                if trade_size_crypto <= crypto_balance:
                    success = self.trading_engine.execute_sell(coin, trade_size_crypto, current_price, "MANUAL", test_signal.signal_id)
                    
                    if success:
                        trade_executed = True
                        usd_received = trade_size_crypto * current_price
                        trade_details = f"✅ **SELL Executed:** {trade_size_crypto:.8f} {coin} for ${usd_received:.2f} USD"
                    else:
                        trade_details = f"❌ **SELL Failed:** Insufficient {coin} balance or other error"
                else:
                    trade_details = f"❌ **SELL Failed:** Insufficient {coin} balance ({crypto_balance:.8f} < {trade_size_crypto:.8f})"
        
        except Exception as e:
            trade_details = f"❌ **Trade Execution Error:** {str(e)}"
            self.logger.error(f"Error executing manual signal trade: {e}")
        
        # Create response embed
        embed = discord.Embed(
            title="📡 Manual Signal Executed",
            color=discord.Color.green() if trade_executed else discord.Color.red(),
            timestamp=discord.utils.utcnow()
        )
        embed.add_field(name="Coin", value=coin, inline=True)
        embed.add_field(name="Signal Type", value=signal_type, inline=True)
        embed.add_field(name="Strength", value=strength, inline=True)
        embed.add_field(name="Price", value=f"${current_price:.2f}", inline=True)
        embed.add_field(name="Strategy", value="Manual Test", inline=True)
        embed.add_field(name="Trade Result", value=trade_details, inline=False)
        
        # Add current balances
        if signal_type == "BUY":
            usd_balance = self.db_manager.get_coin_balance("USD")
            embed.add_field(name="Current USD Balance", value=f"${usd_balance:.2f}", inline=True)
        else:
            crypto_balance = self.db_manager.get_coin_balance(coin)
            embed.add_field(name=f"Current {coin} Balance", value=f"{crypto_balance:.8f}", inline=True)
        
        await ctx.send(embed=embed)

async def setup(bot):
    """Setup function for the cog"""
    await bot.add_cog(CryptoVirtualTrader(bot))
