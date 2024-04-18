#!/usr/bin/env python

#
# This aims to replicate and extend Table 1 from the "LVR-with-fees" paper
# (i.e. "Automated Market Making and Arbitrage Profits in the Presence of Fees")
#

import matplotlib.pyplot as pl
import numpy as np
from dex import DEX, ETH_PRICE
from simulation_examples import estimate_mean_performance, get_price_paths

# -- the setttings are as in the paper

# corresponds to 2 sec, 12 sec, 2 min, 12 min (don't simulate the 50 msec case)
BLOCK_TIMES_SEC = [2, 12, 120, 600]
SWAP_FEE_BPS = [1, 5, 10, 30, 100]
ETH_VOLATILITY_PER_DAY = 0.05

# -- end of settings based on the paper

SEC_PER_DAY = 86400
ETH_VOLATILITY_PER_SECOND = ETH_VOLATILITY_PER_DAY / np.sqrt(SEC_PER_DAY)

NUM_SIMULATIONS = 1000

# this should be divisible by each of the block times we want to investigate
N_SECONDS = 300000

############################################################

def test_probs_uniform(block_time, fee_bps):
    fee_factor = (10_000 - fee_bps) / 10_000

    n_blocks = NUM_SIMULATIONS * N_SECONDS // block_time
    sigma = ETH_VOLATILITY_PER_SECOND * np.sqrt(block_time)
    price_factors = np.random.normal(1.0, sigma, n_blocks)

    cex_price = 1.0
    # set initial price to a random one in the non-arbitrage region
    pool_price = np.random.uniform(cex_price * fee_factor, cex_price / fee_factor)
    n_tx = 0
    for f in price_factors:
        cex_price *= f
        if cex_price > pool_price:
            target_price = cex_price * fee_factor
            if target_price < pool_price:
                continue
        else:
            target_price = cex_price / fee_factor
            if target_price > pool_price:
                continue
        n_tx += 1
        pool_price = target_price

    prob_tx = n_tx / n_blocks
    return prob_tx


def quick_sim_uniform():
    all_prob_per_block = {}
    for block_time in BLOCK_TIMES_SEC:
        all_prob_per_block[block_time] = []
        for swap_fee_bps in SWAP_FEE_BPS:
            tx_prob = test_probs_uniform(block_time, swap_fee_bps)
            all_prob_per_block[block_time].append(tx_prob)

    print_results("arb prob %", all_prob_per_block)

############################################################

def test_probs_poisson(block_time, fee_bps):
    fee_factor = (10_000 - fee_bps) / 10_000

    n_blocks = NUM_SIMULATIONS * N_SECONDS // block_time
    sigma = ETH_VOLATILITY_PER_SECOND * np.sqrt(block_time)
    price_factors = np.random.normal(1.0, sigma, n_blocks)
    # generate the block time distribution
    block_time_distr = np.random.exponential(scale=1.0, size=len(price_factors))
    # transform the price factors taking into account the non-uniform block times
    price_factors = 1.0 + np.sqrt(block_time_distr) * (price_factors - 1)

    cex_price = 1.0
    # set initial price to a random one in the non-arbitrage region
    pool_price = np.random.uniform(cex_price * fee_factor, cex_price / fee_factor)
    n_tx = 0
    for f in price_factors:
        cex_price *= f
        if cex_price > pool_price:
            target_price = cex_price * fee_factor
            if target_price < pool_price:
                continue
        else:
            target_price = cex_price / fee_factor
            if target_price > pool_price:
                continue
        n_tx += 1
        pool_price = target_price

    prob_tx = n_tx / n_blocks
    return prob_tx


def quick_sim_poisson():
    all_prob_per_block = {}
    for block_time in BLOCK_TIMES_SEC:
        all_prob_per_block[block_time] = []
        for swap_fee_bps in SWAP_FEE_BPS:
            tx_prob = test_probs_poisson(block_time, swap_fee_bps)
            all_prob_per_block[block_time].append(tx_prob)

    print_results("arb prob %", all_prob_per_block)

############################################################

def print_results(msg, data):
    print(f"swap fee:                         1bp   5bp  10bp  30bp 100bp")
    for block_time in BLOCK_TIMES_SEC[::-1]:
        print(f"block time {block_time: 5d} sec, {msg}:", end="")
        for i in range(len(SWAP_FEE_BPS)):
            #print(f"fee={swap_fee_bps[i]} bps prob={all_prob_per_block[multiplier][i]:.2f} ", end="")
            print(f"{100*data[block_time][i]: 5.1f} ", end="")
        print("")

############################################################

def full_sim_uniform(basefee_usd):
    all_prices = get_price_paths(N_SECONDS, sigma=ETH_VOLATILITY_PER_SECOND, mu=0.0, M=NUM_SIMULATIONS)
    all_prob_per_block = {}
    all_lp_loss = {} # this loss is normalized vs. LVR, i.e. 100% loss means that the LP loss == LVR

    for block_time in BLOCK_TIMES_SEC:
        if block_time > 1:
            all_prices = all_prices.reshape(N_SECONDS // block_time, block_time, NUM_SIMULATIONS)

        # fix the actual number of blocks to the same value for all simulations
        num_blocks = N_SECONDS // BLOCK_TIMES_SEC[-1]

        all_prob_per_block[block_time] = []
        all_lp_loss[block_time] = []
        for swap_fee_bps in SWAP_FEE_BPS:
            lvr, lp_fees, _, _, num_tx = estimate_mean_performance(all_prices, swap_fee_bps, basefee_usd, num_blocks)
            all_prob_per_block[block_time].append(num_tx / num_blocks)
            all_lp_loss[block_time].append((lvr - lp_fees) / lvr)

    print_results("arb prob %", all_prob_per_block)
    print_results("LP loss  %", all_lp_loss)

############################################################x
    
def main():
    np.random.seed(123456)
    # 1. first replicate the results exactly
    print("Poisson-distributed blocks, quick simulation")
    quick_sim_poisson()
    print("")
    # 2. then show how they would be different if uniform block times are used
    print("uniformly distributed blocks, quick simulation")
    quick_sim_uniform()
    print("")
    # 3. then show that the full DEX simulation with zero-cost transactions
    # produces the same results as the quick uniform simulation
    print("uniformly distributed blocks, full DEX simulation")
    full_sim_uniform(basefee_usd=0.0) #with zero-cost transactions
    print("")
    # 4. finally, show results from full DEX simulation with non-zero-cost transactions
    print("uniformly distributed blocks, full DEX simulation, $10 swap basefees")
    full_sim_uniform(basefee_usd=10.0)
    print("")
    # 5. and now the same, but with even more expensive transactions
    print("uniformly distributed blocks, full DEX simulation, $30 swap basefees")
    full_sim_uniform(basefee_usd=30.0)


if __name__ == '__main__':
    main()
    print("all done!")
