#
# This file simulates a constant product AMM DEX
#

from math import sqrt

############################################################

# Constants for the examples

ETH_PRICE = 3000

POOL_LIQUIDITY_USD = 1_000_000_000

POOL_RESERVES_USD = POOL_LIQUIDITY_USD / 2
POOL_RESERVES_ETH = POOL_RESERVES_USD / ETH_PRICE

# LP fee, in parts per million (ppm)
POOL_FEE_PPM = 500 # corresponds to 0.05%

# For simplicity, assume that each swap burns exactly $10 worth of Ether
DEFAULT_BASEFEE_USD = 10

############################################################

class DEX:
    def __init__(self):
        # -- immutables
        self.fee_ppm = POOL_FEE_PPM
        self.fee_factor = 1_000_000 / (1_000_000 - self.fee_ppm)
        self.basefee_usd = DEFAULT_BASEFEE_USD
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
        self.num_tx = 0
        # debugging
        self.debug_log = False
        self.preset_target_price = None


    def set_fee_bps(self, fee_bps):
        self.fee_ppm = fee_bps * 100
        self.fee_factor = 1_000_000 / (1_000_000 - self.fee_ppm)


    def set_basefee_usd(self, basefee_usd):
        self.basefee_usd = basefee_usd

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
        self.lp_fees += (amount_in_x - amount_in_x_without_fee) * price
        self.reserve_x += amount_in_x_without_fee
        y_out = amount_in_x_without_fee * self.reserve_y / self.reserve_x
        self.reserve_y -= y_out

        self.volume += amount_in_x * price
        self.num_tx += 1
        self.basefees += self.basefee_usd
        return y_out


    def swap_y_to_x(self, amount_in_y):
        amount_in_y_without_fee = amount_in_y / self.fee_factor

        k = self.reserve_x * self.reserve_y
        self.lp_fees += amount_in_y - amount_in_y_without_fee
        self.reserve_y += amount_in_y_without_fee
        x_out = amount_in_y_without_fee * self.reserve_x / self.reserve_y
        self.reserve_x -= x_out

        self.volume += amount_in_y
        self.num_tx += 1
        self.basefees += self.basefee_usd
        return x_out


    def get_target_price(self, cex_price):
        dex_price = self.reserve_y / self.reserve_x
        if cex_price > dex_price:
            target_price = cex_price / self.fee_factor
            #print(dex_price, target_price, cex_price)
            if target_price < dex_price:
                return None
        else:
            target_price = cex_price * self.fee_factor
            #print(dex_price, target_price, cex_price)
            if target_price > dex_price:
                return None
        return target_price


    # this numerically computes the price boundaries where arbitrage does not happen
    def get_non_arbitrage_region(self):
        import numpy as np
        n = 100_000
        # this should be selected large enough for both non-arbitrage endpoints to be in the region
        prices = np.linspace(ETH_PRICE / 1.03, ETH_PRICE * 1.03, n)
        target_prices = [self.get_target_price(p) for p in prices]
        first = prices[0]
        last = prices[0]
        for i in range(n):
            if target_prices[i] is None:
                first = prices[i]
                break
        for i in range(n):
            index = -(i + 1)
            if target_prices[index] is None:
                last = prices[index]
                break
        return first, last


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
        sbp_revenue = single_transaction_lvr - lp_fee - self.basefee_usd
        if sbp_revenue <= 0.0:
            # the trade does not happen due to the friction from the blockchain base fee 
            if self.debug_log:
                print("sbp_revenue <= 0.0:", single_transaction_lvr, lp_fee, sbp_revenue)
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
        self.basefees += self.basefee_usd
        self.num_tx += 1

        return True
