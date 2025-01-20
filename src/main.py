import requests
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime
import time


def fetch_historical_data(start_date, end_date):
    API_KEY = "YOUR_CRYPTOCOMPARE_API_KEY"
    end_timestamp = int(time.mktime(end_date.timetuple()))
    url = f"https://min-api.cryptocompare.com/data/v2/histoday?fsym=BTC&tsym=USD&limit=2000&toTs={end_timestamp}&api_key={API_KEY}"

    try:
        response = requests.get(url)
        data = response.json()["Data"]["Data"]

        filtered_data = [
            {"date": datetime.fromtimestamp(d["time"]), "price": d["close"]}
            for d in data
            if datetime.fromtimestamp(d["time"]) >= start_date
        ]

        return filtered_data
    except Exception as e:
        raise Exception(f"Failed to fetch data: {str(e)}")


def rebalance_portfolio(btc_amount, usd_amount, btc_price, target_ratio):
    total_value = btc_amount * btc_price + usd_amount
    target_btc_value = total_value * target_ratio
    target_btc_amount = target_btc_value / btc_price

    return {
        "btc_amount": target_btc_amount,
        "usd_amount": total_value - target_btc_value,
    }


def run_backtest(
    start_date, end_date, target_ratio, rebalance_frequency_days, initial_usd=10000
):
    price_data = fetch_historical_data(start_date, end_date)
    portfolio = {
        "btc_amount": (initial_usd * target_ratio) / price_data[0]["price"],
        "usd_amount": initial_usd * (1 - target_ratio),
    }

    results = [
        {
            "date": price_data[0]["date"],
            "total_value_usd": initial_usd,
            "btc_amount": portfolio["btc_amount"],
            "usd_amount": portfolio["usd_amount"],
            "btc_price": price_data[0]["price"],
        }
    ]

    for i in range(1, len(price_data)):
        days_since_start = (price_data[i]["date"] - price_data[0]["date"]).days

        if days_since_start % rebalance_frequency_days == 0:
            portfolio = rebalance_portfolio(
                portfolio["btc_amount"],
                portfolio["usd_amount"],
                price_data[i]["price"],
                target_ratio,
            )

        total_value = (
            portfolio["btc_amount"] * price_data[i]["price"] + portfolio["usd_amount"]
        )

        results.append(
            {
                "date": price_data[i]["date"],
                "total_value_usd": total_value,
                "btc_amount": portfolio["btc_amount"],
                "usd_amount": portfolio["usd_amount"],
                "btc_price": price_data[i]["price"],
            }
        )

    return results


def analyze_and_plot(start_date, end_date, target_ratio, rebalance_frequency_days):
    results = run_backtest(start_date, end_date, target_ratio, rebalance_frequency_days)
    df = pd.DataFrame(results)

    initial_value = results[0]["total_value_usd"]
    final_value = results[-1]["total_value_usd"]
    total_return = ((final_value - initial_value) / initial_value) * 100

    buy_and_hold_btc = initial_value / results[0]["btc_price"]
    buy_and_hold_value = buy_and_hold_btc * results[-1]["btc_price"]
    buy_and_hold_return = ((buy_and_hold_value - initial_value) / initial_value) * 100

    # Create the plot
    plt.figure(figsize=(12, 6))

    # Plot portfolio value
    plt.plot(df["date"], df["total_value_usd"], label="Portfolio Value", color="blue")

    # Plot buy and hold value
    buy_and_hold_values = df["btc_price"] * buy_and_hold_btc
    plt.plot(df["date"], buy_and_hold_values, label="Buy & Hold Value", color="green")

    # Plot BTC price (scaled to match initial investment)
    btc_price_scaled = df["btc_price"] * (initial_value / results[0]["btc_price"])
    plt.plot(
        df["date"], btc_price_scaled, label="BTC Price (Scaled)", color="red", alpha=0.5
    )

    plt.title("Portfolio Performance Comparison")
    plt.xlabel("Date")
    plt.ylabel("Value (USD)")
    plt.legend()
    plt.grid(True)
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.show()

    return {
        "start_date": start_date,
        "end_date": end_date,
        "target_ratio": target_ratio,
        "rebalance_frequency_days": rebalance_frequency_days,
        "initial_value": initial_value,
        "final_value": final_value,
        "total_return": total_return,
        "buy_and_hold_return": buy_and_hold_return,
    }


# Example usage
try:
    analysis = analyze_and_plot(
        datetime(2021, 1, 1), datetime(2024, 12, 31), 0.85, 0.25
    )

    print("Backtest Parameters:")
    print(f"Start Date: {analysis['start_date'].strftime('%Y-%m-%d')}")
    print(f"End Date: {analysis['end_date'].strftime('%Y-%m-%d')}")
    print(f"Target BTC Ratio: {(analysis['target_ratio'] * 100):.1f}%")
    print(f"Rebalance Frequency: Every {analysis['rebalance_frequency_days']} days")
    print("\nResults:")
    print(f"Initial Value: ${analysis['initial_value']:.2f}")
    print(f"Final Value: ${analysis['final_value']:.2f}")
    print(f"Strategy Return: {analysis['total_return']:.2f}%")
    print(f"Buy and Hold Return: {analysis['buy_and_hold_return']:.2f}%")

except Exception as e:
    print(f"Error: {str(e)}")
