#!/usr/bin/env python3
"""
Example usage of the Tokenometry library for different trading strategies.

This example demonstrates how to configure and use the Tokenometry class
for day trading, swing trading, and long-term investment strategies.
"""

import logging
from tokenometry import Tokenometry

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('TokenometryExample')

def create_day_trader_config():
    """Configuration for aggressive day trading strategy."""
    return {
        "STRATEGY_NAME": "Day Trader",
        "PRODUCT_IDS": ["BTC-USD", "ETH-USD", "SOL-USD", "AVAX-USD"],
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
        "ATR_STOP_LOSS_MULTIPLIER": 2.0,
    }

def create_swing_trader_config():
    """Configuration for swing trading strategy."""
    return {
        "STRATEGY_NAME": "Aggressive Swing Trader",
        "PRODUCT_IDS": ["BTC-USD", "ETH-USD", "LINK-USD"],
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
    }

def create_long_term_config():
    """Configuration for long-term investment strategy."""
    return {
        "STRATEGY_NAME": "Long-Term Investor",
        "PRODUCT_IDS": ["BTC-USD", "ETH-USD"],
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
    }

def run_strategy_example():
    """Run an example analysis with the day trader strategy."""
    
    # Create configuration
    config = create_day_trader_config()
    
    # Initialize Tokenometry
    scanner = Tokenometry(config=config, logger=logger)
    
    # Run analysis
    logger.info("Starting Tokenometry analysis...")
    signals = scanner.scan()
    
    # Display results
    if signals:
        logger.info("--- ACTIONABLE SIGNALS FOUND ---")
        for signal in signals:
            logger.info(f"  Signal: {signal}")
    else:
        logger.info("No signals generated.")

if __name__ == "__main__":
    # Run single strategy example
    run_strategy_example()
