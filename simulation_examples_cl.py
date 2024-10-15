#!/usr/bin/env python

#
# This simulates a CL DEX with rebalancing and only arb traffic.
#

import matplotlib.pyplot as pl
import numpy as np
from ing_theme_matplotlib import mpl_style
from dex import DEX, ETH_PRICE
from concurrent.futures import ThreadPoolExecutor

# Constants for plotting
pl.rcParams["savefig.dpi"] = 200

# the volatility of ETH price (in a bear market)
ETH_VOLATILITY = 0.3

SECONDS_PER_YEAR = 365 * 24 * 60 * 60

ETH_VOLATILITY_PER_SECOND = ETH_VOLATILITY / np.sqrt(SECONDS_PER_YEAR)

SIMULATION_DURATION_SEC = 50 * 86400

NUM_SIMULATIONS = 500

BLOCK_TIME = 12

############################################################

def get_price_paths(n, sigma, mu, M=NUM_SIMULATIONS):
    St = np.exp((mu - sigma ** 2 / 2) + sigma * np.random.normal(0, 1, size=(M, n-1)).T)
    St = np.vstack([np.ones(M), St])
    St = ETH_PRICE * St.cumprod(axis=0)
    return St

############################################################

def estimate_performance(prices, swap_fee_bps, basefee_usd, range_width):
    dex = DEX()
    dex.set_fee_bps(swap_fee_bps)
    if basefee_usd is not None:
        dex.set_basefee_usd(basefee_usd)
    margin = 1
    initial_liquidity_usd = 100
    dex.rebalance(ETH_PRICE, range_width, initial_liquidity_usd)
    initial_eth, initial_usd = dex.get_position_assets()
    for price in prices:
        dex.maybe_arbitrage(price)
        if dex.is_above_range(margin):
            dex.rebalance_above(price, range_width, 0)
        #break

    final_liquidity_usd = dex.remove_position(prices[-1])
    returns = final_liquidity_usd / initial_liquidity_usd - 1.0

    final_hodl_liquidity_usd = initial_eth * prices[-1] + initial_usd
    hodl_returns = final_hodl_liquidity_usd / initial_liquidity_usd - 1.0

    return dex.lvr, dex.lp_fees, dex.sbp_profits, dex.basefees, dex.num_tx, returns, hodl_returns

############################################################

def estimate_mean_performance(all_prices, swap_fee_bps, basefee_usd=None, range_width=100):
    all_lvr = []
    all_lp_fees = []
    all_sbp_profits = []
    all_basefees = []
    all_tx = []
    all_returns = []
    all_hodl_returns = []

    num_blocks = None

    if len(all_prices.shape) > 2:
        # take the last elements from the second dimension
        all_prices = all_prices[:,-1,:]

    for sim in range(all_prices.shape[1]):
        prices = all_prices[:,sim]
        if num_blocks is not None:
            prices = prices[:num_blocks]
        lvr, lp_fees, spb_revenue, basefees, num_tx, returns, hodl_returns = \
            estimate_performance(prices, swap_fee_bps, basefee_usd, range_width)
        all_lvr.append(lvr)
        all_lp_fees.append(lp_fees)
        all_sbp_profits.append(spb_revenue)
        all_basefees.append(basefees)
        all_tx.append(num_tx)
        all_returns.append(returns)
        all_hodl_returns.append(hodl_returns)

    return np.mean(all_lvr), np.mean(all_lp_fees), np.mean(all_sbp_profits), \
        np.mean(all_basefees), np.mean(all_tx), np.mean(all_returns), np.mean(all_hodl_returns)

############################################################

# simulate the performance of some intervals
def simulate_some_periods():

    all_lvr = []
    all_lp_fees = []
    all_lp_losses = []
    all_basefees = []
    all_sbp_profits = []
    all_num_tx = []
    all_returns = []
    all_hodl_returns = []

    DRIFTS = [0.0, 0.1, 0.2, 0.3]
    for drift_per_year in DRIFTS:
        exp_returns = np.exp(drift_per_year) - 1
        print(f"drift per year: {drift_per_year:.2f}, expected returns: {100*exp_returns:.1f}%")
        n = SIMULATION_DURATION_SEC // BLOCK_TIME
        sigma = ETH_VOLATILITY_PER_SECOND * np.sqrt(BLOCK_TIME)
        mu = drift_per_year / SECONDS_PER_YEAR * BLOCK_TIME
        all_prices = get_price_paths(n, sigma, mu)

        lvr, lp_fees, sbp_profits, basefees, num_tx, returns, hodl_returns = \
            estimate_mean_performance(all_prices, swap_fee_bps=5, basefee_usd=None, range_width=100)
        all_lvr.append(lvr)
        all_lp_fees.append(lp_fees)
        all_lp_losses.append(lvr - lp_fees)
        all_sbp_profits.append(sbp_profits)
        all_basefees.append(basefees)
        all_num_tx.append(num_tx)
        returns *= SECONDS_PER_YEAR / SIMULATION_DURATION_SEC
        hodl_returns *= SECONDS_PER_YEAR / SIMULATION_DURATION_SEC
        all_returns.append(100 * returns)
        all_hodl_returns.append(100 * hodl_returns)

    fig, ax = pl.subplots()
    fig.set_size_inches((7, 4.5))

    pl.plot(DRIFTS, all_returns, label="LP returns, year", marker="D", color="green")
    pl.plot(DRIFTS, all_hodl_returns, label="HODL returns, year", marker="o", color="black")

    pl.xlabel("$\\mu$")
    pl.ylabel("Returns, %")
    pl.legend()
    pl.ylim(ymin=min(0, min(all_returns) - 1), ymax=max(5, max(all_returns) + 1))

    pl.savefig(f"cex_dex_returns_with_drift.png", bbox_inches='tight')
    pl.close()

    return all_lp_losses

############################################################x
    
def main():
    mpl_style(False)
    np.random.seed(123456)
    simulate_some_periods()

if __name__ == '__main__':
    main()
    print("all done!")
