#!/usr/bin/env python

#
# This script simulates LVR, arb profits, and other metrics when a dynamic fee is used
#


import matplotlib.pyplot as pl
import numpy as np
from ing_theme_matplotlib import mpl_style
from dex import DEX, ETH_PRICE
# Constants for plotting
pl.rcParams["savefig.dpi"] = 200

SIMULATION_DURATION_SEC = 36000

NUM_SIMULATIONS = 300

############################################################

def get_price_paths(n, sigma, mu, M=NUM_SIMULATIONS):
    St = np.exp((mu - sigma ** 2 / 2) + sigma * np.random.normal(0, 1, size=(M, n-1)).T)

    # we want the initial prices to be randomly distributed in the pool's non-arbitrage space
    price_low, price_high = DEX().get_non_arbitrage_region()
    initial_prices = np.random.uniform(price_low / ETH_PRICE, price_high / ETH_PRICE, M)
    St = np.vstack([initial_prices, St])

    St = ETH_PRICE * St.cumprod(axis=0)
    return St

############################################################

def estimate_performance(prices, dynamic_fee_proportion):
    dex = DEX()
    dex.is_dynamic_fee = True
    dex.dynamic_fee_proportion = dynamic_fee_proportion
    dex.set_basefee_usd(0)
    for price in prices:
        dex.maybe_arbitrage(price)
    return dex.lvr, dex.lp_fees, dex.sbp_profits, dex.basefees, dex.num_tx

############################################################

def estimate_mean_performance(all_prices, dynamic_fee_proportion):
    all_lvr = []
    all_lp_fees = []
    all_sbp_profits = []
    all_basefees = []
    all_tx = []

    if len(all_prices.shape) > 2:
        # take the last elements from the second dimension
        all_prices = all_prices[:,-1,:]

    for sim in range(all_prices.shape[1]):
        prices = all_prices[:,sim]
        #if num_blocks is not None:
        #    prices = prices[:num_blocks]
        lvr, lp_fees, spb_revenue, basefees, num_tx = \
            estimate_performance(prices, dynamic_fee_proportion)
        all_lvr.append(lvr)
        all_lp_fees.append(lp_fees)
        all_sbp_profits.append(spb_revenue)
        all_basefees.append(basefees)
        all_tx.append(num_tx)

    return np.mean(all_lvr), np.mean(all_lp_fees), np.mean(all_sbp_profits), \
        np.mean(all_basefees), np.mean(all_tx)

############################################################

def simulate_some_blocks(dynamic_fee_proportion):
    n = SIMULATION_DURATION_SEC
    all_lvr = []
    all_lp_fees = []
    all_lp_losses = []
    all_basefees = []
    all_sbp_profits = []
    all_num_tx = []

    sigmas = [0.2, 0.4, 0.6, 0.8]

    for sigma in sigmas:
        sigma_per_second = sigma / np.sqrt(365 * 24 * 60 * 60)
        all_prices = get_price_paths(n, sigma_per_second, mu=0.0)

        block_time = 12
        if block_time > 1:
            all_prices = all_prices.reshape(n // block_time, block_time, NUM_SIMULATIONS)

        print("compute performance for block time", block_time)
        lvr, lp_fees, sbp_profits, basefees, num_tx = \
            estimate_mean_performance(all_prices, dynamic_fee_proportion)
        all_lvr.append(lvr)
        all_lp_fees.append(lp_fees)
        all_lp_losses.append(lvr - lp_fees)
        all_sbp_profits.append(sbp_profits)
        all_basefees.append(basefees)
        all_num_tx.append(num_tx)
    
    fig, ax = pl.subplots()
    fig.set_size_inches((7, 4.5))

    x = sigmas
    pl.plot(x, all_lvr, label="LVR", marker="D", color="black")
    pl.plot(x, all_lp_fees, label="LP fees", marker="o", color="green")
    pl.plot(x, all_sbp_profits, label="SBP profits", marker="s", color="blue")
    #pl.plot(x, all_lp_losses, label="LP losses", marker="x", color="red")
    #pl.plot(x, all_basefees, label="Basefees (burnt ETH)", marker="^", color="orange")

    pl.title(f"AMM performance with fee={dynamic_fee_proportion}$\\cdot\\alpha$")
    pl.xlabel("$\\sigma$")
    pl.ylabel("Profits / losses, $")
    pl.legend()
    pl.ylim([0, 100000])

    pl.savefig(f"cex_dex_arbitrage_metrics_dynamic_fee_{dynamic_fee_proportion}.png", bbox_inches='tight')
    #pl.show()
    pl.close()

############################################################x
    
def main():
    mpl_style(False)
    np.random.seed(123456)
    simulate_some_blocks(0.1)
    simulate_some_blocks(0.5)
    simulate_some_blocks(0.9)


if __name__ == '__main__':
    main()
    print("all done!")
