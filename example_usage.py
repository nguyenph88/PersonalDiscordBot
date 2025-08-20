#!/usr/bin/env python3
"""
Example usage of the Tokenometry library for different trading strategies.

This example demonstrates how to configure and use the Tokenometry class
for day trading, swing trading, and long-term investment strategies.
Now includes signal strength analysis and filtering capabilities.
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

def display_signal_with_strength(signal):
    """
    Display a signal with enhanced formatting that highlights the signal strength.
    
    Args:
        signal: Dictionary containing signal information including strength
    """
    # Create strength indicator with emojis
    strength_indicators = {
        "Strong": "🟢",
        "Medium": "🟡", 
        "Low": "🔴"
    }
    
    strength_emoji = strength_indicators.get(signal.get('strength', 'Unknown'), '⚪')
    
    print(f"\n{strength_emoji} SIGNAL: {signal['signal']} {signal['asset']}")
    print(f"   📊 Strength: {signal['strength']}")
    print(f"   📈 Trend: {signal['trend']}")
    print(f"   💰 Price: ${signal['close_price']:.2f}")
    print(f"   🕒 Time: {signal['timestamp']}")
    
    # Display trade plan if available
    if signal.get('trade_plan'):
        tp = signal['trade_plan']
        print(f"   📋 Trade Plan:")
        print(f"      Stop Loss: ${tp['stop_loss']:.2f}")
        print(f"      Position Size: {tp['position_size_crypto']:.6f} {signal['asset'].split('-')[0]}")
        print(f"      USD Value: ${tp['position_size_usd']:.2f}")

def filter_signals_by_strength(signals, min_strength="Medium"):
    """
    Filter signals based on minimum strength requirement.
    
    Args:
        signals: List of signal dictionaries
        min_strength: Minimum strength required ("Low", "Medium", or "Strong")
        
    Returns:
        Filtered list of signals meeting the strength requirement
    """
    strength_order = {"Low": 1, "Medium": 2, "Strong": 3}
    min_strength_value = strength_order.get(min_strength, 2)
    
    filtered_signals = []
    for signal in signals:
        signal_strength_value = strength_order.get(signal.get('strength', 'Low'), 1)
        if signal_strength_value >= min_strength_value:
            filtered_signals.append(signal)
    
    return filtered_signals

def analyze_signal_distribution(signals):
    """
    Analyze the distribution of signal strengths in the results.
    
    Args:
        signals: List of signal dictionaries
    """
    if not signals:
        print("No signals to analyze.")
        return
    
    strength_counts = {"Strong": 0, "Medium": 0, "Low": 0}
    signal_types = {"BUY": 0, "SELL": 0}
    
    for signal in signals:
        strength = signal.get('strength', 'Unknown')
        if strength in strength_counts:
            strength_counts[strength] += 1
        
        signal_type = signal.get('signal', 'Unknown')
        if signal_type in signal_types:
            signal_types[signal_type] += 1
    
    print(f"\n📊 SIGNAL ANALYSIS SUMMARY:")
    print(f"   Total Signals: {len(signals)}")
    print(f"   Signal Types: {signal_types}")
    print(f"   Strength Distribution: {strength_counts}")

def run_strategy_example():
    """Run an example analysis with the day trader strategy."""
    
    # Create configuration
    config = create_day_trader_config()
    
    # Initialize Tokenometry
    scanner = Tokenometry(config=config, logger=logger)
    
    # Run analysis
    logger.info("Starting Tokenometry analysis...")
    signals = scanner.scan()
    
    # Display results with enhanced formatting
    if signals:
        logger.info("--- ACTIONABLE SIGNALS FOUND ---")
        
        # Display all signals with strength information
        for signal in signals:
            display_signal_with_strength(signal)
        
        # Analyze signal distribution
        analyze_signal_distribution(signals)
        
        # Demonstrate strength filtering
        print(f"\n🔍 FILTERING EXAMPLES:")
        
        # Show only strong signals
        strong_signals = filter_signals_by_strength(signals, "Strong")
        print(f"   Strong signals only: {len(strong_signals)} found")
        
        # Show medium and strong signals
        medium_plus_signals = filter_signals_by_strength(signals, "Medium")
        print(f"   Medium+ strength signals: {len(medium_plus_signals)} found")
        
        # Example of using strength for decision making
        print(f"\n💡 DECISION MAKING WITH SIGNAL STRENGTH:")
        for signal in signals:
            if signal.get('strength') == 'Strong':
                print(f"   🚀 {signal['asset']}: Strong {signal['signal']} signal - Consider immediate action")
            elif signal.get('strength') == 'Medium':
                print(f"   ⚡ {signal['asset']}: Medium {signal['signal']} signal - Monitor closely, wait for confirmation")
            elif signal.get('strength') == 'Low':
                print(f"   ⚠️  {signal['asset']}: Low {signal['signal']} signal - Exercise caution, wait for stronger signals")
    else:
        logger.info("No signals generated.")

def run_multiple_strategies_example():
    """Run analysis with multiple strategies to compare signal strengths."""
    
    strategies = [
        ("Day Trader", create_day_trader_config()),
        ("Swing Trader", create_swing_trader_config()),
        ("Long-Term Investor", create_long_term_config())
    ]
    
    print("🔄 COMPARING MULTIPLE STRATEGIES")
    print("=" * 50)
    
    for strategy_name, config in strategies:
        print(f"\n📈 {strategy_name.upper()} STRATEGY")
        print("-" * 30)
        
        scanner = Tokenometry(config=config, logger=logger)
        signals = scanner.scan()
        
        if signals:
            # Count signals by strength
            strength_counts = {"Strong": 0, "Medium": 0, "Low": 0}
            for signal in signals:
                strength = signal.get('strength', 'Unknown')
                if strength in strength_counts:
                    strength_counts[strength] += 1
            
            print(f"   Total Signals: {len(signals)}")
            print(f"   Strong: {strength_counts['Strong']}")
            print(f"   Medium: {strength_counts['Medium']}")
            print(f"   Low: {strength_counts['Low']}")
            
            # Show strongest signal
            strong_signals = filter_signals_by_strength(signals, "Strong")
            if strong_signals:
                print(f"   🎯 Strongest signal: {strong_signals[0]['asset']} - {strong_signals[0]['signal']}")
        else:
            print("   No signals generated")

if __name__ == "__main__":
    # Run single strategy example
    run_strategy_example()
    
    print("\n" + "="*60)
    
    # Run multiple strategies comparison
    run_multiple_strategies_example()
