import matplotlib.pyplot as plt
import pandas as pd
from datetime import timedelta
import numpy as np
from datetime import datetime
import time
import requests

def fetch_historical_data(start_date, end_date):
    API_KEY = "YOUR_CRYPTOCOMPARE_API_KEY"  # Replace with your actual API key
    end_timestamp = int(time.mktime(end_date.timetuple()))
    url = f"https://min-api.cryptocompare.com/data/v2/histoday?fsym=BTC&tsym=USD&limit=2000&toTs={end_timestamp}&api_key={API_KEY}"

    try:
        response = requests.get(url)
        response.raise_for_status()  # Raise HTTPError for bad responses (4xx or 5xx)
        data = response.json()["Data"]["Data"]

        filtered_data = [
            {"date": datetime.fromtimestamp(d["time"]), "price": d["close"]}
            for d in data
            if datetime.fromtimestamp(d["time"]) >= start_date
        ]

        return filtered_data
    except requests.exceptions.RequestException as e:
        raise Exception(f"Failed to fetch data due to network issue: {str(e)}")
    except KeyError as e:
        raise Exception(f"Failed to parse data, KeyError: {str(e)}. Response might not have 'Data.Data' structure.")
    except Exception as e:
        raise Exception(f"Failed to fetch data: {str(e)}")

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

def compare_strategies(start_date, end_date, kelly_fraction, rebalance_freq=30, annualized_risk_free=0.0):
    strategies = {
        "Low (0.8×Kelly)": kelly_fraction * 0.8,
        "Optimal Kelly": kelly_fraction,
        "High (1.2×Kelly)": kelly_fraction * 1.2
    }

    # Run backtests
    results = {}
    for name, frac in strategies.items():
        results[name] = run_backtest(start_date, end_date, frac, rebalance_freq)

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
        comparison.append((name, final_value, return_pct))

    # Calculate Buy & Hold BTC values over time
    buy_and_hold_btc_values = [initial_btc_buy_hold * d["price"] for d in price_data]
    btc_returns = (end_price/initial_price - 1)

    # Calculate Buy & Hold USD values over time
    buy_and_hold_usd_values = [initial_usd] * len(price_data)


    # Add benchmarks
    comparison.append(("Buy & Hold BTC", buy_and_hold_btc_values[-1], btc_returns*100))
    comparison.append(("Buy & Hold USD", initial_usd, 0.0))

    # Create DataFrame
    df = pd.DataFrame(comparison, columns=["Strategy", "Final Value", "Return %"])
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
             buy_and_hold_usd_values,
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
    print(f"  Annualized Risk-Free Rate (used in Kelly Calculation): {annualized_risk_free*100:.2f}%") # Updated print statement
    print("\nStrategy Fractions:") # Added strategy fractions print
    for name, frac in strategies.items():
        print(f"  {name}: {frac:.4f}")

    return df

if __name__ == "__main__":
    start_date = datetime(2022, 11, 1)
    end_date = datetime(2025, 1, 1)
    rebalance_freq = 1
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
            print(f"Calculated Optimal Kelly fraction (with risk-free rate): {kelly_fraction:.4f}") # Updated print statement

            # Run comparison
            comparison_df = compare_strategies(start_date, end_date, kelly_fraction, rebalance_freq, annualized_risk_free_rate) # Pass risk-free rate to compare_strategies

            # Display results
            print("\nStrategy Performance Comparison:")
            print(comparison_df.to_string(index=False))

            # Sanity check
            optimal_row = comparison_df[comparison_df["Strategy"] == "Optimal Kelly"].iloc[0]
            high_row = comparison_df[comparison_df["Strategy"] == "High (1.2×Kelly)"].iloc[0]
            low_row = comparison_df[comparison_df["Strategy"] == "Low (0.8×Kelly)"].iloc[0]

            if (optimal_row["Return %"] > high_row["Return %"] and
                optimal_row["Return %"] > low_row["Return %"]):
                print("\nSanity check PASSED: Optimal fraction performed best")
            else:
                print("\nSanity check WARNING: Optimal fraction didn't perform best")
                print("Possible reasons:")
                print("- Transaction costs not modeled")
                print("- Non-normal return distribution")
                print("- Look-ahead bias in parameter estimation (still present as discussed)")
                print("- Risk-free rate impact might be subtle over this period") # Added note about risk-free rate impact

    except Exception as e:
        print(f"Error: {e}")