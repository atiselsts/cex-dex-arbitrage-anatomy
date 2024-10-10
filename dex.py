#
# This file simulates a constant product AMM DEX
#

from math import sqrt, log
from v3_liquidity_math import *

############################################################

# Constants for the examples

ETH_PRICE = 3000

POOL_LIQUIDITY_USD = 1_000_000_000

# LP fee, in parts per million (ppm)
POOL_FEE_PPM = 500 # corresponds to 0.05%

# For simplicity, assume that each swap burns exactly $10 worth of Ether
DEFAULT_BASEFEE_USD = 10

############################################################

class DEX:
    def __init__(self, pool_liquidity_usd=POOL_LIQUIDITY_USD):

        POOL_RESERVES_USD = POOL_LIQUIDITY_USD / 2
        POOL_RESERVES_ETH = POOL_RESERVES_USD / ETH_PRICE

        # -- immutables
        self.fee_ppm = POOL_FEE_PPM
        self.fee_factor = 1_000_000 / (1_000_000 - self.fee_ppm)
        self.basefee_usd = DEFAULT_BASEFEE_USD
        self.tick_spacing = 10
        # -- pool's state
        # the price is fully determined by the reserves (real or virtual)
        self.reserve_x = POOL_RESERVES_ETH
        self.reserve_y = POOL_RESERVES_USD
        # -- position's state
        self.pos_liquidity = 0
        self.pos_liquidity_share = 0
        self.pos_tick_low = 0
        self.pos_tick_high = 0
        self.pos_fees_usd = 0
        self.pos_fees_eth = 0
        # -- cumulative metrics
        self.volume = 0
        self.lp_fees = 0
        self.lvr = 0
        self.sbp_profits = 0
        self.basefees = 0
        self.num_tx = 0
        # debugging
        self.debug_log = False
        self.preset_target_price = None


    def add_position(self, liquidity_usd, tick_low, tick_high):
        self.pos_tick_low = tick_low
        self.pos_tick_high = tick_high
        price_low = to_price(tick_low)
        price_high = to_price(tick_high)
        sp = sqrt(self.price())
        sa = sqrt(price_low)
        sb = sqrt(price_high)
        amount_eth, amount_usd = compute_amounts(liquidity_usd, sp, sa, sb)
        self.pos_liquidity = get_liquidity(amount_eth, amount_usd, sp, sa, sb)
        self.pos_liquidity_share = self.pos_liquidity / self.liquidity()
        #print(f"liquidity share of the position is {100*self.pos_liquidity_share}%")
        assert self.pos_liquidity_share < 1


    def get_position_assets(self):
        price = self.price()
        sp = sqrt(price)
        sa = to_sqrt_price(self.pos_tick_low)
        sb = to_sqrt_price(self.pos_tick_high)
        amount_eth = calculate_x(self.pos_liquidity, sp, sa, sb)
        amount_usd = calculate_y(self.pos_liquidity, sp, sa, sb)
        return amount_eth, amount_usd


    def remove_position(self, cex_price):
        amount_eth, amount_usd = self.get_position_assets()
        #print(f"  got {amount_eth} ETH {amount_usd} USD")
        liquidity_usd = amount_usd + amount_eth * cex_price
        fees_usd = self.pos_fees_usd
        fees_eth = self.pos_fees_eth
        self.pos_fees_usd = 0
        self.pos_fees_eth = 0
        self.pos_liquidity = 0
        self.pos_liquidity_share = 0
        fees_usd += fees_eth * cex_price
        return liquidity_usd + fees_usd


    def is_in_range(self, margin):
        tick = to_tick(self.price())
        return self.pos_tick_low - margin <= tick and self.pos_tick_high + margin > tick


    def is_below_range(self, margin):
        tick = to_tick(self.price())
        return self.pos_tick_low - margin > tick


    def is_above_range(self, margin):
        tick = to_tick(self.price())
        return self.pos_tick_high + margin <= tick


    def rebalance(self, cex_price, width_in_ticks, additional_usd):
        tick = to_tick(self.price())
        range_low  = tick_to_range_low(tick, self.tick_spacing)
        range_high = tick_to_range_high(tick, self.tick_spacing)
        margin = (width_in_ticks - self.tick_spacing) // 2
        if margin < 0:
            margin = 0
        low = range_low - margin
        high = range_high + margin

        #print("  price=", cex_price)
        #print("  tick =", tick, "low=", low, "high=", high, "range=", high - low)

        #old_liquidty = self.pos_liquidity
        usd = self.remove_position(cex_price)
        #print("  usd=", usd)
        self.add_position(usd + additional_usd, low, high)
        #new_liquidty = self.pos_liquidity
        #if old_liquidty:
        #    print("  factor=", new_liquidty / old_liquidty)


    def rebalance_above(self, cex_price, width_in_ticks, additional_usd):
        tick = to_tick(self.price())
        range_low  = tick_to_range_low(tick, self.tick_spacing)
        range_high = tick_to_range_high(tick, self.tick_spacing)
        margin = width_in_ticks - self.tick_spacing
        low = range_low
        high = range_high + margin

        #print("price=", cex_price)
        #print("  tick =", tick, "low=", low, "high=", high, "range=", high - low)

        #old_liquidty = self.pos_liquidity
        usd = self.remove_position(cex_price)
        #print("  usd=", usd)
        self.add_position(usd + additional_usd, low, high)
        #new_liquidty = self.pos_liquidity
        #if old_liquidty:
            #print("  factor=", new_liquidty / old_liquidty)
            #assert old_liquidty >= new_liquidty

    
    def get_fee_share(self, swap_price_start, swap_price_end):
        swap_price_low = min(swap_price_start, swap_price_end)
        swap_price_high = max(swap_price_start, swap_price_end)
        tick_start = to_tick(swap_price_low)
        tick_end = to_tick(swap_price_end)
        total_ticks = tick_end - tick_start + 1

        # this is a very approximate division, but should be good enough
        if tick_start < self.pos_tick_low:
            if tick_end < self.pos_tick_low:
                ticks_in_range = 0
            elif tick_end < self.pos_tick_high:
                ticks_in_range = tick_end - self.pos_tick_low + 1
            else:
                ticks_in_range = self.pos_tick_high - self.pos_tick_low + 1
        elif tick_start < self.pos_tick_high:
            if tick_end < self.pos_tick_high:
                ticks_in_range = total_ticks
            else:
                # don't add +1
                ticks_in_range = self.pos_tick_high - tick_start
        else:
            ticks_in_range = 0

        proportion_in_range = ticks_in_range / total_ticks
#        if ticks_in_range != total_ticks:
#            print(swap_price_low, tick_start)
#            print(swap_price_low, tick_end)
#            print(ticks_in_range, total_ticks)
        assert proportion_in_range <= 1

        return proportion_in_range * self.pos_liquidity_share


    def set_fee_bps(self, fee_bps):
        self.fee_ppm = fee_bps * 100
        self.fee_factor = 1_000_000 / (1_000_000 - self.fee_ppm)


    def set_basefee_usd(self, basefee_usd):
        self.basefee_usd = basefee_usd


    def price(self):
        return self.reserve_y / self.reserve_x


    def liquidity(self):
        return sqrt(self.reserve_x * self.reserve_y)

    
    def get_amounts_to_target_price(self, target_price):
        if self.preset_target_price is not None:
            target_price = self.preset_target_price

        sqrt_target_price = sqrt(target_price)
        L = self.liquidity()
        delta_x = L / sqrt_target_price - self.reserve_x
        delta_y = L * sqrt_target_price - self.reserve_y
        return (delta_x, delta_y)


    def swap_x_to_y(self, amount_in_x):
        amount_in_x_without_fee = amount_in_x / self.fee_factor
        print(amount_in_x_without_fee, amount_in_x)

        price = self.price()
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

        self.lp_fees += amount_in_y - amount_in_y_without_fee
        self.reserve_y += amount_in_y_without_fee
        x_out = amount_in_y_without_fee * self.reserve_x / self.reserve_y
        self.reserve_x -= x_out

        self.volume += amount_in_y
        self.num_tx += 1
        self.basefees += self.basefee_usd
        return x_out


    def get_target_price(self, cex_price):
        dex_price = self.price()
        if cex_price > dex_price:
            target_price = cex_price / self.fee_factor
            if target_price < dex_price:
                return None
        else:
            target_price = cex_price * self.fee_factor
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
            lp_fee_eth = (delta_x_with_fee - delta_x)
            lp_fee_usd = 0
            lp_fee = lp_fee_eth * cex_price
        else:
            delta_y_with_fee = delta_y * self.fee_factor
            lp_fee_usd = delta_y_with_fee - delta_y
            lp_fee_eth = 0
            lp_fee = lp_fee_usd

        single_transaction_lvr = -(delta_x * cex_price + delta_y)
        sbp_profit = single_transaction_lvr - lp_fee - self.basefee_usd
        if sbp_profit <= 0.0:
            # the trade does not happen due to the friction from the blockchain base fee 
            if self.debug_log:
                print("sbp_profit <= 0.0:", single_transaction_lvr, lp_fee, sbp_profit)
            return False

        # trade happens; first update the pool's state
        if self.debug_log:
            new_reserve_x = self.reserve_x + delta_x
            new_reserve_y = self.reserve_y + delta_y
            lp_loss_vs_lvr = (single_transaction_lvr - lp_fee) / single_transaction_lvr
            print(f" DEX price: {self.reserve_y/self.reserve_x:.4f}->{new_reserve_y/new_reserve_x:.4f} CEX price: {cex_price:.4f} LP fee={lp_fee:.2f} LVR={single_transaction_lvr:.2f} loss: {100*lp_loss_vs_lvr:.1f}%")

        price_start = self.price()
        self.reserve_x += delta_x
        self.reserve_y += delta_y
        price_end = self.price()

        share = self.get_fee_share(price_start, price_end)
        if lp_fee_usd != 0:
            self.pos_fees_usd += share * lp_fee_usd
            #print(f"earn {share * lp_fee_usd} usd")
        else:
            self.pos_fees_eth += share * lp_fee_eth
            #print(f"earn {share * lp_fee_eth} eth")

        # then update the cumulative metrics
        self.volume += abs(delta_y) + lp_fee
        self.lp_fees += lp_fee
        self.lvr += single_transaction_lvr
        self.sbp_profits += sbp_profit
        self.basefees += self.basefee_usd
        self.num_tx += 1

        return True
