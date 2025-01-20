import axios from 'axios';

async function fetchHistoricalData(startDate, endDate) {
    const API_KEY = 'YOUR_CRYPTOCOMPARE_API_KEY';
    const url = `https://min-api.cryptocompare.com/data/v2/histoday?fsym=BTC&tsym=USD&limit=2000&toTs=${Math.floor(endDate.getTime() / 1000)}&api_key=${API_KEY}`;

    try {
        const response = await axios.get(url);
        return response.data.Data.Data.filter(data =>
            new Date(data.time * 1000) >= startDate
        ).map(data => ({
            date: new Date(data.time * 1000),
            price: data.close
        }));
    } catch (error) {
        throw new Error(`Failed to fetch data: ${error.message}`);
    }
}

function rebalancePortfolio(btcAmount, usdAmount, btcPrice, targetRatio) {
    const totalValue = btcAmount * btcPrice + usdAmount;
    const targetBtcValue = totalValue * targetRatio;
    const targetBtcAmount = targetBtcValue / btcPrice;

    return {
        btcAmount: targetBtcAmount,
        usdAmount: totalValue - targetBtcValue
    };
}

async function runBacktest(startDate, endDate, targetRatio, rebalanceFrequencyDays, initialUsd = 10000) {
    const priceData = await fetchHistoricalData(startDate, endDate);
    let portfolio = {
        btcAmount: (initialUsd * targetRatio) / priceData[0].price,
        usdAmount: initialUsd * (1 - targetRatio)
    };

    const results = [{
        date: priceData[0].date,
        totalValueUsd: initialUsd,
        btcAmount: portfolio.btcAmount,
        usdAmount: portfolio.usdAmount,
        btcPrice: priceData[0].price
    }];

    for (let i = 1; i < priceData.length; i++) {
        const daysSinceStart = Math.floor((priceData[i].date - priceData[0].date) / (1000 * 60 * 60 * 24));

        if (daysSinceStart % rebalanceFrequencyDays === 0) {
            portfolio = rebalancePortfolio(
                portfolio.btcAmount,
                portfolio.usdAmount,
                priceData[i].price,
                targetRatio
            );
        }

        const totalValue = portfolio.btcAmount * priceData[i].price + portfolio.usdAmount;

        results.push({
            date: priceData[i].date,
            totalValueUsd: totalValue,
            btcAmount: portfolio.btcAmount,
            usdAmount: portfolio.usdAmount,
            btcPrice: priceData[i].price
        });
    }

    return results;
}

async function analyze(startDate, endDate, targetRatio, rebalanceFrequencyDays) {
    const results = await runBacktest(startDate, endDate, targetRatio, rebalanceFrequencyDays);

    const initialValue = results[0].totalValueUsd;
    const finalValue = results[results.length - 1].totalValueUsd;
    const totalReturn = ((finalValue - initialValue) / initialValue) * 100;

    const buyAndHoldBtc = initialValue / results[0].btcPrice;
    const buyAndHoldValue = buyAndHoldBtc * results[results.length - 1].btcPrice;
    const buyAndHoldReturn = ((buyAndHoldValue - initialValue) / initialValue) * 100;

    return {
        startDate,
        endDate,
        targetRatio,
        rebalanceFrequencyDays,
        initialValue,
        finalValue,
        totalReturn,
        buyAndHoldReturn,
        results
    };
}

// Example usage
try {
    const analysis = await analyze(
        new Date('2020-01-01'),
        new Date('2023-12-31'),
        0.5,
        30
    );

    console.log('Backtest Parameters:');
    console.log(`Start Date: ${analysis.startDate.toISOString().split('T')[0]}`);
    console.log(`End Date: ${analysis.endDate.toISOString().split('T')[0]}`);
    console.log(`Target BTC Ratio: ${(analysis.targetRatio * 100).toFixed(1)}%`);
    console.log(`Rebalance Frequency: Every ${analysis.rebalanceFrequencyDays} days`);
    console.log('\nResults:');
    console.log(`Initial Value: $${analysis.initialValue.toFixed(2)}`);
    console.log(`Final Value: $${analysis.finalValue.toFixed(2)}`);
    console.log(`Strategy Return: ${analysis.totalReturn.toFixed(2)}%`);
    console.log(`Buy and Hold Return: ${analysis.buyAndHoldReturn.toFixed(2)}%`);
} catch (error) {
    console.error(error);
}