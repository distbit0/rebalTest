import matplotlib.pyplot as plt
import pandas as pd
from datetime import timedelta
import numpy as np
from datetime import datetime
import time
import requests
import math  # Import the math module

def fetch_historical_data(start_date, end_date):
    API_KEY = "YOUR_CRYPTOCOMPARE_API_KEY"  # Replace with your actual API key
    base_url = "https://min-api.cryptocompare.com/data/v2/histoday"
    all_data = []
    current_end_date = end_date

    delta = end_date - start_date
    total_days = delta.days
    num_requests = math.ceil(total_days / 2000)

    for _ in range(num_requests):
        end_timestamp = int(time.mktime(current_end_date.timetuple()))
        url = f"{base_url}?fsym=BTC&tsym=USD&limit=2000&toTs={end_timestamp}&api_key={API_KEY}"

        try:
            response = requests.get(url)
            response.raise_for_status()
            data = response.json()["Data"]["Data"]
            if not data: # Handle cases where API returns no data for a chunk
                print(f"Warning: No data returned from API for end date: {current_end_date}")
                break # No more data to fetch, likely reached the beginning of history or an issue

            all_data.extend(data)

            # Move current_end_date back by 2000 days for the next request
            current_end_date -= timedelta(days=2001) # Subtract slightly more than 2000 to avoid overlap, and to move backwards in time

            if current_end_date < start_date:
                break # Stop if the next chunk would start before the overall start_date

        except requests.exceptions.RequestException as e:
            raise Exception(f"Failed to fetch data due to network issue: {str(e)}")
        except KeyError as e:
            raise Exception(f"Failed to parse data, KeyError: {str(e)}. Response might not have 'Data.Data' structure.")
        except Exception as e:
            raise Exception(f"Failed to fetch data: {str(e)}")

    filtered_data = [
        {"date": datetime.fromtimestamp(d["time"]), "price": d["close"]}
        for d in all_data
        if datetime.fromtimestamp(d["time"]) >= start_date and datetime.fromtimestamp(d["time"]) <= end_date # Ensure all dates are within the requested range
    ]

    # Sort data by date as chunks might be fetched in reverse chronological order
    filtered_data.sort(key=lambda x: x['date'])

    return filtered_data

def calculate_kelly_fraction(data, rebalance_frequency_days, annualized_risk_free=0.0):
    # Generate rebalance dates
    start_date = data[0]['date']
    end_date = data[-1]['date']

    rebalance_dates = [start_date]
    current_date = start_date
    while current_date <= end_date:
        current_date += timedelta(days=rebalance_frequency_days)
        rebalance_dates.append(min(current_date, end_date))

    # Find prices at each rebalance date
    rebalance_prices = []
    for rd in rebalance_dates:
        # Find first price on or after rebalance date
        for d in data:
            if d['date'] >= rd:
                rebalance_prices.append(d['price'])
                break
        else:
            rebalance_prices.append(data[-1]['price'])

    # Calculate periodic risk-free rate
    periodic_risk_free = annualized_risk_free * (rebalance_frequency_days / 365.0)

    # Calculate returns between rebalance periods, now subtracting the periodic risk-free rate
    returns = []
    for i in range(1, len(rebalance_prices)):
        prev_price = rebalance_prices[i-1]
        curr_price = rebalance_prices[i]
        returns.append((curr_price - prev_price)/prev_price - periodic_risk_free)

    if not returns:
        return 0.0

    mu = np.mean(returns)
    sigma_sq = np.var(returns)

    if sigma_sq == 0:
        return 0.0

    return mu / sigma_sq

def rebalance_portfolio(btc_amount, usd_amount, btc_price, target_ratio):
    total_value = btc_amount * btc_price + usd_amount
    target_btc_value = total_value * target_ratio
    target_btc_amount = target_btc_value / btc_price

    return {
        "btc_amount": target_btc_amount,
        "usd_amount": total_value - target_btc_value,
    }

def run_backtest(start_date, end_date, target_ratio, rebalance_frequency_days, initial_usd=10000):
    price_data = fetch_historical_data(start_date, end_date)

    # Initial portfolio accounting for possible leverage/shorting
    initial_btc = (initial_usd * target_ratio) / price_data[0]["price"]
    initial_usd_amt = initial_usd * (1 - target_ratio)

    portfolio = {
        "btc_amount": initial_btc,
        "usd_amount": initial_usd_amt
    }

    results = [{
        "date": price_data[0]["date"],
        "total_value_usd": initial_usd,
        "btc_amount": portfolio["btc_amount"],
        "usd_amount": portfolio["usd_amount"],
        "btc_price": price_data[0]["price"],
    }]

    for i in range(1, len(price_data)):
        current_price = price_data[i]["price"]
        days_since_start = (price_data[i]["date"] - price_data[0]["date"]).days

        if days_since_start % rebalance_frequency_days == 0:
            portfolio = rebalance_portfolio(
                portfolio["btc_amount"],
                portfolio["usd_amount"],
                current_price,
                target_ratio
            )

        total_value = portfolio["btc_amount"] * current_price + portfolio["usd_amount"]

        results.append({
            "date": price_data[i]["date"],
            "total_value_usd": total_value,
            "btc_amount": portfolio["btc_amount"],
            "usd_amount": portfolio["usd_amount"],
            "btc_price": current_price,
        })

    return results

def calculate_max_drawdown(portfolio_values):
    """Calculates the maximum drawdown of a portfolio value series."""
    peak = portfolio_values[0]
    max_drawdown = 0
    for value in portfolio_values:
        if value > peak:
            peak = value
        drawdown = (peak - value) / peak
        if drawdown > max_drawdown:
            max_drawdown = drawdown
    return max_drawdown * 100 # in percentage

def compare_strategies(start_date, end_date, kelly_fraction, rebalance_freq=30, annualized_risk_free=0.0):
    strategies = {
        "Half Kelly": kelly_fraction * 0.5,
        "Optimal Kelly": kelly_fraction,
    }

    # Run backtests and calculate returns
    results = {}
    strategy_returns = {} # Store returns for each strategy
    for name, frac in strategies.items():
        backtest_results = run_backtest(start_date, end_date, frac, rebalance_freq)
        results[name] = backtest_results
        portfolio_values = [res["total_value_usd"] for res in backtest_results]
        strategy_returns[name] = []
        for i in range(1, len(portfolio_values)):
            strategy_returns[name].append((portfolio_values[i] - portfolio_values[i-1]) / portfolio_values[i-1])

    # Fetch price data again to get start and end prices for output
    price_data = fetch_historical_data(start_date, end_date)
    initial_price = price_data[0]["price"]
    end_price = price_data[-1]["price"]
    initial_usd = 10000
    initial_btc_buy_hold = initial_usd / initial_price

    comparison = []
    for name, data in results.items():
        final_value = data[-1]["total_value_usd"]
        return_pct = (final_value/initial_usd - 1)*100

        # Calculate Worst Rebalance Period Return
        worst_period_return_pct = min(strategy_returns[name]) * 100 if strategy_returns[name] else 0.0

        # Calculate max drawdown
        portfolio_values = [d["total_value_usd"] for d in data]
        max_drawdown_pct = calculate_max_drawdown(portfolio_values)

        comparison.append((name, final_value, return_pct, worst_period_return_pct, max_drawdown_pct)) # Removed avg_loss_pct

    # Calculate Buy & Hold BTC values over time
    buy_and_hold_btc_values = [initial_btc_buy_hold * d["price"] for d in price_data]
    btc_returns = (end_price/initial_price - 1)

    # Calculate Buy & Hold BTC Risk Metrics
    buy_hold_btc_returns = []
    for i in range(1, len(buy_and_hold_btc_values)):
        buy_hold_btc_returns.append((buy_and_hold_btc_values[i] - buy_and_hold_btc_values[i-1]) / buy_and_hold_btc_values[i-1])

    buy_hold_worst_period_return_pct = min(buy_hold_btc_returns) * 100 if buy_hold_btc_returns else 0.0
    buy_hold_btc_max_drawdown_pct = calculate_max_drawdown(buy_and_hold_btc_values)

    # Add benchmarks with risk metrics
    comparison.append(("Buy & Hold BTC", buy_and_hold_btc_values[-1], btc_returns*100, buy_hold_worst_period_return_pct, buy_hold_btc_max_drawdown_pct)) # Removed buy_hold_avg_loss_pct
    comparison.append(("Buy & Hold USD", initial_usd, 0.0, 0.0, 0.0)) # USD has zero risk

    # Create DataFrame
    df = pd.DataFrame(comparison, columns=["Strategy", "Final Value", "Return %", "Worst Period Return %", "Max Drawdown %"]) # Updated column names
    df = df.sort_values("Final Value", ascending=False)

    # Plot results
    plt.figure(figsize=(12,6))
    for name, data in results.items():
        plt.plot([d["date"] for d in data],
                 [d["total_value_usd"] for d in data],
                 label=f"{name} (Fraction: {strategies[name]:.3f})") # Added fraction to label

    # Plot Buy & Hold BTC over time
    plt.plot([d["date"] for d in price_data],
             buy_and_hold_btc_values,
             '--', label="Buy & Hold BTC")
    # Plot Buy & Hold USD over time
    plt.plot([d["date"] for d in price_data],
             [initial_usd] * len(price_data), # Directly plot initial_usd array
             '--', label="Buy & Hold USD")

    plt.title("Portfolio Value Comparison (Including Leverage/Shorting)")
    plt.xlabel("Date")
    plt.ylabel("USD Value")
    plt.yscale('log')  # Set y-axis to log scale
    plt.legend()
    plt.grid(True)
    plt.show()

    print("\nBacktest Period Details:") # Added period details print
    print(f"  Data Range: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
    print(f"  Start Price: ${initial_price:.2f}")
    print(f"  End Price: ${end_price:.2f}")
    print(f"  Rebalance Frequency: {rebalance_freq} days")
    print(f"  Annualized Risk-Free Rate (used in Kelly Calculation): {annualized_risk_free*100:.2f}%")
    print("\nStrategy Fractions:") # Added strategy fractions print
    for name, frac in strategies.items():
        print(f"  {name}: {frac:.4f}")

    print("\nRisk Metrics Explanation:") # Explanation of risk metrics
    print("  Worst Period Return:  Indicates the single worst percentage return experienced in any rebalance period during the backtest.") # Updated explanation
    print("  Max Drawdown:  Represents the largest percentage decline from a peak to a trough experienced during the backtest. It shows the maximum potential loss from a high point.")
    print("  *Note: Lower Worst Period Return (more negative), and Max Drawdown generally indicate higher risk.*") # Updated note

    return df

if __name__ == "__main__":
    start_date = datetime(2020, 1, 1) # Example: Extended start date
    end_date = datetime(2025, 1, 1)
    rebalance_freq = 30  # Monthly rebalancing
    annualized_risk_free_rate = 0.02 # Define risk-free rate here, e.g., 2%

    try:
        data = fetch_historical_data(start_date, end_date)
        if not data:
            print("No data fetched. Check the date range and API key.")
        else:
            # Calculate Kelly with aligned parameters, now correctly using risk-free rate
            kelly_fraction = calculate_kelly_fraction(
                data,
                rebalance_frequency_days=rebalance_freq,
                annualized_risk_free=annualized_risk_free_rate # Pass risk-free rate here
            )
            print(f"Calculated Optimal Kelly fraction (with risk-free rate): {kelly_fraction:.4f}")

            # Run comparison
            comparison_df = compare_strategies(start_date, end_date, kelly_fraction, rebalance_freq, annualized_risk_free_rate)

            # Display results, including risk metrics
            print("\nStrategy Performance and Risk Comparison:")
            print(comparison_df.to_string(index=False))

            # Sanity check - now only comparing Half and Optimal Kelly
            optimal_row = comparison_df[comparison_df["Strategy"] == "Optimal Kelly"].iloc[0]
            half_row = comparison_df[comparison_df["Strategy"] == "Half Kelly"].iloc[0]

            if (optimal_row["Return %"] >= half_row["Return %"]): # Optimal Kelly should ideally have >= return than Half Kelly
                print("\nSanity check PASSED: Optimal fraction performed at least as well as Half Kelly (in return)")
            else:
                print("\nSanity check WARNING: Optimal fraction didn't perform as well as Half Kelly (in return)")
                print("Possible reasons:")
                print("- Transaction costs not modeled")
                print("- Non-normal return distribution")
                print("- Look-ahead bias in parameter estimation (still present as discussed)")
                print("- Risk-free rate impact and backtest period")

    except Exception as e:
        print(f"Error: {e}")