#!/usr/bin/env python

#
# This script analyzes arb and LP revenue based on the fee relative to the price difference between the CEX and DEX
#

import matplotlib.pyplot as pl
import numpy as np
from ing_theme_matplotlib import mpl_style
from dex import DEX, ETH_PRICE
# Constants for plotting
pl.rcParams["savefig.dpi"] = 200


############################################################

def estimate_performance(prices, swap_fee_bps):
    dex = DEX()
    dex.set_fee_bps(swap_fee_bps)
    # assume the tx costs zero gas
    dex.set_basefee_usd(0)

    for price in prices:
        dex.maybe_arbitrage(price)

    return dex.lvr, dex.lp_fees, dex.sbp_profits, dex.basefees

############################################################

def simulate_revenue(alpha):
    all_lvr = []
    all_lp_fees = []
    all_sbp_profits = []
    all_lp_losses = []
    all_basefees = []
        
    new_eth_price = ETH_PRICE * alpha
    # the price array has a single entry with the new CEX price
    prices = [new_eth_price]
    
    sqrt_alpha = np.sqrt(alpha)

    # change the fee from zero up to alpha
    dynamic_fees_bps = np.linspace(0.0, (alpha - 1) * 10000, 30)
    for swap_fee_bps in dynamic_fees_bps:
        lvr, lp_fees, sbp_profits, basefees = \
            estimate_performance(prices, swap_fee_bps)
        all_lvr.append(lvr)
        all_lp_fees.append(lp_fees)
        all_lp_losses.append(lvr - lp_fees)
        all_sbp_profits.append(sbp_profits)
        all_basefees.append(basefees)

    fig, ax = pl.subplots()
    fig.set_size_inches((7, 4.5))

    x = dynamic_fees_bps
    pl.plot(x, all_lvr, label="LVR", marker="D", color="black")
    pl.plot(x, all_lp_fees, label="LP fees", marker="o", color="green")
    pl.plot(x, all_sbp_profits, label="SBP profits", marker="s", color="blue")
    #pl.plot(x, all_lp_losses, label="LP losses", marker="x", color="red")

    pl.vlines((sqrt_alpha - 1) * 10000, 0, max(all_lvr), label="$\\sqrt{\\alpha}$")


    pl.title(f"Results with $\\alpha$={alpha}")
    pl.xlabel("Dynamic fee, bps")
    pl.ylabel("Profits / losses, $")
    pl.legend()
    pl.ylim(ymin=0)

    pl.savefig(f"cex_dex_revenue_with_dynamic_fee_alpha{alpha}.png", bbox_inches='tight')
    pl.close()


############################################################x
    
def main():
    mpl_style(False)
    np.random.seed(123456)
    simulate_revenue(alpha=1.01)
    simulate_revenue(alpha=1.1)


if __name__ == '__main__':
    main()
    print("all done!")

