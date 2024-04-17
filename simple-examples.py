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
from math import sqrt

# Constants for the examples

ETH_PRICE = 3000

POOL_LIQUIDITY_USD = 400_000_000

POOL_RESERVES_USD = POOL_LIQUIDITY_USD / 2
POOL_RESERVES_ETH = POOL_RESERVES_USD / ETH_PRICE

# LP fee, in parts per million (ppm)
POOL_FEE_PPM = 500 # corresponds to 0.05%

# For simplicity, assume that each swap burns exactly $10 worth of Ether
BASEFEE_USD = 10

############################################################

class DEX:
    def __init__(self):
        # -- immutables
        self.fee_ppm = POOL_FEE_PPM
        self.fee_factor = 1_000_000 / (1_000_000 - self.fee_ppm)
        # -- pool's state
        # the price is fully determined by the reserves (real or virtual)
        self.reserve_x = POOL_RESERVES_ETH
        self.reserve_y = POOL_RESERVES_USD
        # -- cumulative metrics
        self.volume = 0
        self.lp_fees = 0
        self.lvr = 0
        self.sbp_revenue = 0
        self.basefees = 0
        # debugging
        self.debug_log = True
        self.preset_target_price = None


    def price(self):
        return self.reserve_y / self.reserve_x


    def k(self):
        return self.reserve_x * self.reserve_y

    
    def get_amounts_to_target_price(self, target_price):
        if self.preset_target_price is not None:
            target_price = self.preset_target_price

        sqrt_target_price = sqrt(target_price)
        L = sqrt(self.reserve_x * self.reserve_y)
        delta_x = L / sqrt_target_price - self.reserve_x
        delta_y = L * sqrt_target_price - self.reserve_y
        return (delta_x, delta_y)


    def swap_x_to_y(self, amount_in_x):
        amount_in_x_without_fee = amount_in_x / self.fee_factor
        print(amount_in_x_without_fee, amount_in_x)

        #k = self.reserve_x * self.reserve_y
        price = self.reserve_y / self.reserve_x
        self.volume += amount_in_x * price
        self.lp_fees += (amount_in_x - amount_in_x_without_fee) * price
        self.reserve_x += amount_in_x_without_fee
        y_out = amount_in_x_without_fee * self.reserve_y / self.reserve_x
        self.reserve_y -= y_out
        return y_out


    def swap_y_to_x(self, amount_in_y):
        amount_in_y_without_fee = amount_in_y / self.fee_factor

        k = self.reserve_x * self.reserve_y
        self.volume += amount_in_y
        self.lp_fees += amount_in_y - amount_in_y_without_fee
        self.reserve_y += amount_in_y_without_fee
        x_out = amount_in_y_without_fee * self.reserve_x / self.reserve_y
        self.reserve_x -= x_out
        return x_out


    def get_target_price(self, cex_price):
        dex_price = self.reserve_y / self.reserve_x
        if cex_price > dex_price:
            target_price = cex_price / self.fee_factor
            if target_price < dex_price:
                return None
        else:
            target_price = cex_price * self.fee_factor
            if target_price > dex_price:
                return None
        return target_price


    def maybe_arbitrage(self, cex_price):
        target_price = self.get_target_price(cex_price)
        if target_price is None:
            # the trade does not happen because the CEX/DEX price difference is below the LP fee
            return False

        delta_x, delta_y = self.get_amounts_to_target_price(target_price)
        # compute the LP fees using CEX prices
        # the assumption here is that LPs do not accumulate or compound their fees, but withdraw and rapidly convert to USD
        if delta_x > 0:
            delta_x_with_fee = delta_x * self.fee_factor
            lp_fee = (delta_x_with_fee - delta_x) * cex_price
        else:
            delta_y_with_fee = delta_y * self.fee_factor
            lp_fee = delta_y_with_fee - delta_y

        single_transaction_lvr = -(delta_x * cex_price + delta_y)
        sbp_revenue = single_transaction_lvr - lp_fee - BASEFEE_USD
        #print(single_transaction_lvr, lp_fee, sbp_revenue)
        if sbp_revenue <= 0.0:
            # the trade does not happen due to the friction from the blockchain base fee 
            return False

        # trade happens; first update the pool's state
        if self.debug_log:
            new_reserve_x = self.reserve_x + delta_x
            new_reserve_y = self.reserve_y + delta_y
            lvr_recap = lp_fee / single_transaction_lvr
            print(f" DEX price: {self.reserve_y/self.reserve_x:.4f}->{new_reserve_y/new_reserve_x:.4f} CEX price: {cex_price:.4f} LP fee={lp_fee:.4f} LVR={single_transaction_lvr:.4f} LVR recapture: {lvr_recap*100:.2f}%")

        self.reserve_x += delta_x
        self.reserve_y += delta_y

        # then update the cumulative metrics
        self.volume += abs(delta_y) + lp_fee
        self.lp_fees += lp_fee
        self.lvr += single_transaction_lvr
        self.sbp_revenue += sbp_revenue
        self.basefees += BASEFEE_USD

        return True


############################################################

# this verifies that the pool accurately computes the target price to maximize the arbitrager revenues
def plot_revenue_on_target_price():
    fig, ax = pl.subplots()
    fig.set_size_inches((6, 4))

    # assume +1% price delta
    cex_price = ETH_PRICE * 1.01
    if cex_price > ETH_PRICE:
        prices = np.linspace(cex_price / 1.01, cex_price, 100000)
    else:
        prices = np.linspace(cex_price, cex_price * 1.01, 100000)
    #print(prices)
    revenues = []
    for target_price in prices:
        dex = DEX()
        dex.debug_log = False
        dex.preset_target_price = target_price
        dex.maybe_arbitrage(cex_price)
        revenues.append(dex.sbp_revenue)

    m = np.argmax(revenues)
    print("best price=", prices[m])
    print("dex target=", DEX().get_target_price(cex_price))
    pl.plot(prices, revenues, label="SBP revenue")
    pl.xlabel("Target price, $")
    pl.ylabel("SBP revenue")
    pl.ylim(ymin=0)

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
    simulate_arbitrage_trade(dex, "+0.1% change", ETH_PRICE * 100.1 / 100)
    print("")

############################################################
    
#
# This example shows the CEX/DEX trade anatomy for a single trade based on 1% price divergence between CEX and DEX
#
def example_2():
    print("Example 2: +1%")
    dex = DEX()
    simulate_arbitrage_trade(dex, "+1.0% change", ETH_PRICE * 101 / 100)
    print("")

############################################################
    
#
# This example shows the CEX/DEX trade anatomy for two price changes with +0.1% and +0.2% price divergence
#
def example_3():
    print("Example 3: +0.1% then +0.2%")
    short_block_dex = DEX()
    simulate_arbitrage_trade(short_block_dex, None, ETH_PRICE * 100.1 / 100)
    simulate_arbitrage_trade(short_block_dex, None, ETH_PRICE * 100.2 / 100)

    long_block_dex = DEX()
    simulate_arbitrage_trade(long_block_dex, None, ETH_PRICE * 100.2 / 100)

    print(f"short blocks: LVR={short_block_dex.lvr:.6f} lp_fee={short_block_dex.lp_fees:.6f}")
    print(f"long blocks:  LVR={long_block_dex.lvr:.6f} lp_fee={long_block_dex.lp_fees:.6f}")
    print("")


############################################################

#
# This example shows the CEX/DEX trade anatomy for two price changes with -0.1% and +0.2% price divergence
#
def example_4():
    print("Example 4: -0.1% then +0.2%")
    short_block_dex = DEX()
    simulate_arbitrage_trade(short_block_dex, None, ETH_PRICE * 99.9 / 100)
    simulate_arbitrage_trade(short_block_dex, None, ETH_PRICE * 100.2 / 100)

    long_block_dex = DEX()
    simulate_arbitrage_trade(long_block_dex, None, ETH_PRICE * 100.2 / 100)

    print(f"short blocks: LVR={short_block_dex.lvr:.6f} lp_fee={short_block_dex.lp_fees:.6f}")
    print(f"long blocks:  LVR={long_block_dex.lvr:.6f} lp_fee={long_block_dex.lp_fees:.6f}")
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
    plot_revenue_on_target_price()


if __name__ == '__main__':
    main()
    print("all done!")
