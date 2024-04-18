#!/usr/bin/env python

#
# This script shows somes examples of CEX/DEX arb trades including:
# - LP losses
# - cost versus rebalancing
# - trade friction
#
# Warning! This assumes that LPs do not accumulate or compound their fees, but withdraw and rapidly convert to USD.
# This is more similar to Uniswap v3 rather than to Uniswap v2 (compounding fees).
# The single-direction swaps are also path-independent (since the pool's reserves do not grow with the fees).

import matplotlib.pyplot as pl
import numpy as np
from dex import DEX, ETH_PRICE

############################################################

# this verifies that the pool accurately computes the target price to maximize the arbitrager revenues
def plot_profits_on_target_price():
    fig, ax = pl.subplots()
    fig.set_size_inches((6, 4))

    # assume +1% price delta
    cex_price = ETH_PRICE * 1.01
    if cex_price > ETH_PRICE:
        prices = np.linspace(cex_price / 1.01, cex_price, 100000)
    else:
        prices = np.linspace(cex_price, cex_price * 1.01, 100000)
    #print(prices)
    profits = []
    for target_price in prices:
        dex = DEX()
        dex.preset_target_price = target_price
        dex.maybe_arbitrage(cex_price)
        profits.append(dex.sbp_profits)

    m = np.argmax(profits)
    print("best price=", prices[m])
    print("dex target=", DEX().get_target_price(cex_price))
    pl.plot(prices, profits)
    pl.xlabel("Target price, $")
    pl.ylabel("SBP profit")
    pl.ylim(ymin=0)
    pl.title("Arbitrager profit depending on target price")

    pl.show()
    pl.close()

############################################################

def simulate_arbitrage_trade(dex, message, cex_price):
    if message:
        print(f"simulating trade after {message}")
    dex.maybe_arbitrage(cex_price)

############################################################

#
# This example shows the CEX/DEX trade anatomy for a single trade based on 0.1% price divergence between CEX and DEX
#
def example_1():
    print("Example 1: +0.1%")
    dex = DEX()
    dex.debug_log = True
    simulate_arbitrage_trade(dex, "+0.1% change", ETH_PRICE * 100.1 / 100)
    print("")

############################################################
    
#
# This example shows the CEX/DEX trade anatomy for a single trade based on 1% price divergence between CEX and DEX
#
def example_2():
    print("Example 2: +1%")
    dex = DEX()
    dex.debug_log = True
    simulate_arbitrage_trade(dex, "+1.0% change", ETH_PRICE * 101 / 100)
    print("")

############################################################
    
#
# This example shows the CEX/DEX trade anatomy for two price changes with +0.1% and +0.2% price divergence
#
def example_3():
    print("Example 3: +0.1% then +0.2%")
    short_block_dex = DEX()
    short_block_dex.debug_log = True
    simulate_arbitrage_trade(short_block_dex, None, ETH_PRICE * 100.1 / 100)
    simulate_arbitrage_trade(short_block_dex, None, ETH_PRICE * 100.2 / 100)
    short_block_lp_loss = (short_block_dex.lvr - short_block_dex.lp_fees) / short_block_dex.lvr

    long_block_dex = DEX()
    long_block_dex.debug_log = True
    simulate_arbitrage_trade(long_block_dex, None, ETH_PRICE * 100.2 / 100)
    long_block_lp_loss = (long_block_dex.lvr - long_block_dex.lp_fees) / long_block_dex.lvr

    print(f"short blocks: LVR={short_block_dex.lvr:.6f} lp_fee={short_block_dex.lp_fees:.6f} loss={100*short_block_lp_loss:.1f}%")
    print(f"long blocks:  LVR={long_block_dex.lvr:.6f} lp_fee={long_block_dex.lp_fees:.6f} loss={100*long_block_lp_loss:.1f}%")
    print("")


############################################################

#
# This example shows the CEX/DEX trade anatomy for two price changes with -0.1% and +0.2% price divergence
#
def example_4():
    print("Example 4: -0.1% then +0.2%")
    short_block_dex = DEX()
    short_block_dex.debug_log = True
    simulate_arbitrage_trade(short_block_dex, None, ETH_PRICE * 99.9 / 100)
    simulate_arbitrage_trade(short_block_dex, None, ETH_PRICE * 100.2 / 100)
    short_block_lp_loss = (short_block_dex.lvr - short_block_dex.lp_fees) / short_block_dex.lvr

    long_block_dex = DEX()
    long_block_dex.debug_log = True
    simulate_arbitrage_trade(long_block_dex, None, ETH_PRICE * 100.2 / 100)
    long_block_lp_loss = (long_block_dex.lvr - long_block_dex.lp_fees) / long_block_dex.lvr

    print(f"short blocks: LVR={short_block_dex.lvr:.6f} lp_fee={short_block_dex.lp_fees:.6f} loss={100*short_block_lp_loss:.1f}%")
    print(f"long blocks:  LVR={long_block_dex.lvr:.6f} lp_fee={long_block_dex.lp_fees:.6f} loss={100*long_block_lp_loss:.1f}%")
    print("")

############################################################x

#
# Check price (in)dependence of the swap paths
#
def example_0():
    dex1 = DEX()
    dex1.swap_x_to_y(10.0)
    dex1.swap_y_to_x(10000)
    print(f"dex1.price = {dex1.price()}")

    dex1a = DEX()
    dex1a.swap_x_to_y(1.0)
    dex1a.swap_x_to_y(1.0)
    dex1a.swap_x_to_y(1.0)
    dex1a.swap_x_to_y(1.0)
    dex1a.swap_x_to_y(1.0)

    dex1a.swap_x_to_y(1.0)
    dex1a.swap_x_to_y(1.0)
    dex1a.swap_x_to_y(1.0)
    dex1a.swap_x_to_y(1.0)
    dex1a.swap_x_to_y(1.0)
    dex1a.swap_y_to_x(10000)
    print(f"dex1a.price = {dex1.price()}")

    dex2 = DEX()
    dex2.swap_y_to_x(10000)
    dex2.swap_x_to_y(10.0)
    print(f"dex2.price = {dex2.price()}")

############################################################x
    
def main():
    example_1()
    example_2()
    example_3()
    example_4()
    plot_profits_on_target_price()


if __name__ == '__main__':
    main()
    print("all done!")
