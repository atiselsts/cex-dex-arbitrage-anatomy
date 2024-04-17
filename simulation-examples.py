#!/usr/bin/env python

#
# This script builds on the based CEX/DEX arb trading examples and
# computes statistics of the DEX performanc based on a large number of simulations.

import matplotlib.pyplot as pl
import numpy as np
from dex import DEX, ETH_PRICE

# the volatility of ETH price per one year - approximately matches the recent year's data
ETH_VOLATILITY = 0.5

ETH_VOLATILITY_PER_SECOND = ETH_VOLATILITY / np.sqrt(365 * 24 * 60 * 60)

NUM_SIMULATIONS = 1000

BLOCK_TIMES_SEC = [1, 2, 3, 4, 6, 12]

LONG_BLOCK_TIME_SEC = BLOCK_TIMES_SEC[-1]

############################################################

def get_price_paths(n, sigma, mu):
    M = NUM_SIMULATIONS
    St = np.exp((mu - sigma ** 2 / 2) + sigma * np.random.normal(0, 1, size=(M, n-1)).T)

    # we want the initial prices to be randomly distributed in the pool's non-arbitrage space
    price_low, price_high = DEX().get_non_arbitrage_region()
    initial_prices = np.random.uniform(price_low / ETH_PRICE, price_high / ETH_PRICE, M)
    St = np.vstack([initial_prices, St])

    St = ETH_PRICE * St.cumprod(axis=0)
    return St

############################################################

def estimate_performance(prices):
    dex = DEX()
    for price in prices:
        dex.maybe_arbitrage(price)
    return dex.lvr, dex.lp_fees, dex.sbp_revenue, dex.basefees, dex.num_tx

############################################################

def estimate_mean_performance(all_prices):
    all_lvr = []
    all_lp_fees = []
    all_sbp_revenue = []
    all_basefees = []
    all_tx = []

    if len(all_prices.shape) > 2:
        # take the last elements from the second dimension
        all_prices = all_prices[:,-1,:]

    #last_prices = []
    for sim in range(all_prices.shape[1]):
        prices = all_prices[:,sim]
        #last_prices.append(prices[-1])
        lvr, lp_fees, spb_revenue, basefees, num_tx = estimate_performance(prices)
        all_lvr.append(lvr)
        all_lp_fees.append(lp_fees)
        all_sbp_revenue.append(spb_revenue)
        all_basefees.append(basefees)
        all_tx.append(num_tx)
    #print(last_prices)

    return np.mean(all_lvr), np.mean(all_lp_fees), np.mean(all_sbp_revenue), \
        np.mean(all_basefees), np.mean(all_tx)

############################################################

# simulate the performance of 100 12-second long intervals, depending on the block time
def simulate_single_interval():
    n = LONG_BLOCK_TIME_SEC * 100
    all_prices = get_price_paths(n, sigma=ETH_VOLATILITY_PER_SECOND, mu=0.0)
    all_lvr = []
    all_lp_fees = []
    all_basefees = []
    all_sbp_revenue = []
    all_num_tx = []
    for block_time in BLOCK_TIMES_SEC:
        if block_time > 1:
            all_prices = all_prices.reshape(n // block_time, block_time, NUM_SIMULATIONS)

        print("compute performance for block time", block_time)
        lvr, lp_fees, sbp_revenue, basefees, num_tx = estimate_mean_performance(all_prices)
        all_lvr.append(lvr)
        all_lp_fees.append(lp_fees)
        all_sbp_revenue.append(sbp_revenue)
        all_basefees.append(basefees)
        all_num_tx.append(num_tx)
    
    fig, ax = pl.subplots()
    fig.set_size_inches((6, 4))

    pl.plot(BLOCK_TIMES_SEC, all_lvr, label="LVR", marker="D", color="red")
    pl.plot(BLOCK_TIMES_SEC, all_lp_fees, label="LP fees", marker="o", color="blue")
    pl.plot(BLOCK_TIMES_SEC, all_sbp_revenue, label="SBP revenue", marker="s", color="black")
    pl.plot(BLOCK_TIMES_SEC, all_basefees, label="Basefees (burnt ETH)", marker="^", color="orange")

    pl.xlabel("Block time, sec")
    pl.ylabel("Revenue, $")
    pl.legend()
    pl.ylim(ymin=0)

    pl.show()
    pl.close()

############################################################x
    
def main():
    np.random.seed(123456)
    simulate_single_interval()


if __name__ == '__main__':
    main()
    print("all done!")
