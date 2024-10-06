#!/usr/bin/env python

#
# This script computes statistics of the DEX performance based
# on the proposed reduction of block times in EIP 7781
# (keeping 30M gas per block)
#

import matplotlib.pyplot as pl
import numpy as np
from ing_theme_matplotlib import mpl_style
from dex import DEX, ETH_PRICE
# Constants for plotting
pl.rcParams["savefig.dpi"] = 200

# the volatility of ETH price per one year - approximately matches the recent year's data
ETH_VOLATILITY = 0.6072

ETH_VOLATILITY_PER_SECOND = ETH_VOLATILITY / np.sqrt(365 * 24 * 60 * 60)

BLOCK_TIMES_SEC = [8, 12]

SIMULATION_DURATION_SEC = 3600

NUM_SIMULATIONS = 10000

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

def estimate_performance(prices, swap_fee_bps, basefee_usd):
    dex = DEX()
    dex.set_fee_bps(swap_fee_bps)
    if basefee_usd is not None:
        dex.set_basefee_usd(basefee_usd)
    for price in prices:
        dex.maybe_arbitrage(price)
    return dex.lvr, dex.lp_fees, dex.sbp_profits, dex.basefees, dex.num_tx

############################################################

def estimate_mean_performance(all_prices, swap_fee_bps, basefee_usd=None, num_blocks=None):
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
        if num_blocks is not None:
            prices = prices[:num_blocks]
        lvr, lp_fees, spb_revenue, basefees, num_tx = \
            estimate_performance(prices, swap_fee_bps, basefee_usd)
        all_lvr.append(lvr)
        all_lp_fees.append(lp_fees)
        all_sbp_profits.append(spb_revenue)
        all_basefees.append(basefees)
        all_tx.append(num_tx)

    return np.mean(all_lvr), np.mean(all_lp_fees), np.mean(all_sbp_profits), \
        np.mean(all_basefees), np.mean(all_tx)

############################################################

# simulate the performance of some 12-second long intervals, depending on the block time
def simulate_some_blocks(basefee_usd):
    n = SIMULATION_DURATION_SEC
    all_prices = get_price_paths(n, sigma=ETH_VOLATILITY_PER_SECOND, mu=0.0)
    all_lvr = []
    all_lp_fees = []
    all_lp_losses = []
    all_basefees = []
    all_sbp_profits = []
    all_num_tx = []
    for block_time in BLOCK_TIMES_SEC:
        if block_time > 1:
            all_prices = all_prices.reshape(n // block_time, block_time, NUM_SIMULATIONS)

        print("compute performance for block time", block_time)
        lvr, lp_fees, sbp_profits, basefees, num_tx = \
            estimate_mean_performance(all_prices, swap_fee_bps=5, basefee_usd=basefee_usd)
        all_lvr.append(lvr)
        all_lp_fees.append(lp_fees)
        all_lp_losses.append(lvr - lp_fees)
        all_sbp_profits.append(sbp_profits)
        all_basefees.append(basefees)
        all_num_tx.append(num_tx)
    
    fig, ax = pl.subplots()
    fig.set_size_inches((7, 4.5))

    print("burnt basefees:", all_basefees)

    pl.plot(BLOCK_TIMES_SEC, all_lvr, label="LVR", marker="D", color="black")
    pl.plot(BLOCK_TIMES_SEC, all_lp_fees, label="LP fees", marker="o", color="green")
    pl.plot(BLOCK_TIMES_SEC, all_sbp_profits, label="SBP profits", marker="s", color="blue")
    pl.plot(BLOCK_TIMES_SEC, all_lp_losses, label="LP losses", marker="x", color="red")
    pl.plot(BLOCK_TIMES_SEC, all_basefees, label="Basefees (burnt ETH)", marker="^", color="orange")

    pl.title(f"Results with ${basefee_usd} basefee")
    pl.xlabel("Block time, sec")
    pl.ylabel("Profits / losses, $")
    pl.legend()
    pl.ylim(ymin=0)

    pl.savefig(f"eip7781_cex_dex_arbitrage_metrics_{basefee_usd}_basefee.png", bbox_inches='tight')
    #pl.show()
    pl.close()

    return all_lp_losses

############################################################x
    
def main():
    mpl_style(False)
    np.random.seed(123456)

    basefees_usd = [0, 2, 4]

    lp_losses = {}
    for basefee in basefees_usd:
        lp_losses[basefee] = simulate_some_blocks(basefee)

    fig, ax = pl.subplots()
    fig.set_size_inches((5, 3.5))

    markers = {0: "x", 2: "+", 4: "D"}
    for basefee in basefees_usd:
        factor = lp_losses[basefee][-1] / lp_losses[basefee][0]
        print(f"basefee=${basefee} improvement={100 * (factor - 1):.2f}%")
        pl.plot(BLOCK_TIMES_SEC, lp_losses[basefee], label=f"Basefee=${basefee}",
                marker=markers[basefee], color="red")

    n = 1000
    min_block = BLOCK_TIMES_SEC[0]
    max_block = BLOCK_TIMES_SEC[-1]
    half_block_index = -2
    x = np.linspace(min_block, max_block, n)
    sqrt_x = [np.sqrt(u) for u in x]

    # could do a more accurate fit for the models if wanted,
    # but at the end it doesn't matter that much
    k = lp_losses[0][half_block_index] / sqrt_x[n // 2]
    sqrt_model = [k * u for u in sqrt_x]

    const = lp_losses[basefees_usd[-1]][-2] - lp_losses[basefees_usd[0]][-2]
    sqrt_plus_const_model = [k * u + const for u in sqrt_x]

    pl.plot(x, sqrt_model, label="Model: $\\sqrt{BT}$", color="black")
    pl.plot(x, sqrt_plus_const_model, label="Model: $\\sqrt{BT} + const$", color="brown")

    pl.xlabel("Block time, sec")
    pl.ylabel("LP losses, $")
    pl.legend()
    pl.ylim(ymin=0)

    pl.savefig(f"eip7781_cex_dex_arbitrage_lp_losses_basefee.png", bbox_inches='tight')
    pl.close()




if __name__ == '__main__':
    main()
    print("all done!")
