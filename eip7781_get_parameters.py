#!/usr/bin/env python3

import os
from abi import v3_pool_abi
from web3 import Web3
import yfinance as yf
import numpy as np

OLD_BLOCKTIME_SEC = 12
NEW_BLOCKTIME_SEC = 8

# Assume that users are willing to pay constant amount of fees per second
EIP_7781_COST_REDUCTION_FACTOR = OLD_BLOCKTIME_SEC / NEW_BLOCKTIME_SEC

PROVIDER_URL = os.getenv("PROVIDER_URL")

if "wss://" in PROVIDER_URL:
    web3 = Web3(Web3.WebsocketProvider(PROVIDER_URL))
else:
    web3 = Web3(Web3.HTTPProvider(PROVIDER_URL))

# WETH/USDC pool, 0.05%
pool_address = Web3.to_checksum_address("0x88e6a0c2ddd26feeb64f039a2c41296fcb3f5640")

def get_eth_volatility():
    PERIOD_START = "2023-09-30"
    PERIOD_END = "2024-09-30"
    data = yf.download("ETH-USD", start=PERIOD_START, end=PERIOD_END)
    data['Log Returns'] = np.log(data['Close'] / data['Close'].shift())
    daily_std = data['Log Returns'].std()
    result = daily_std * np.sqrt(365.25)
    print(f"volatility: {result:.4f}")


def get_virtual_reserves():
    # get the liquidity and sqrt of price 
    pool_contract = web3.eth.contract(address=pool_address, abi=v3_pool_abi)
    slot0 = pool_contract.functions.slot0().call()
    sqrt_price_x96 = slot0[0]
    liquidity = pool_contract.functions.liquidity().call()

    # compute the virtual reserves
    Q96 = 2 ** 96
    Q192 = 2 ** 192
    reserve0_x96 = liquidity * Q192 / sqrt_price_x96
    reserve1_x96 = liquidity * sqrt_price_x96

    reserve_usd = reserve0_x96 / Q96 / 10 ** 6
    reserve_eth = reserve1_x96 / Q96 / 10 ** 18

    price = (sqrt_price_x96 ** 2) / Q192
    eth_price = 1 / (price * (10 ** -12))
    print("price:", eth_price)

    total_reserve_usd = reserve_usd + reserve_eth * eth_price
    print(f"total virtual reserves: {total_reserve_usd:.0f}")

    return eth_price


def get_swap_cost_usd(eth_price):
    swap_gas = 150000
    num_blocks = 100
    basefees = web3.eth.fee_history(num_blocks, 'latest', [10, 90])["baseFeePerGas"]
    avg_basefee = sum(basefees) / len(basefees)
    result = swap_gas * avg_basefee * eth_price * 1e-18
    print(f"swap cost : ${result:.2f}")
    print(f"with EIP7781: ${result / EIP_7781_COST_REDUCTION_FACTOR:.2f}")


def main():
    get_eth_volatility()
    eth_price = get_virtual_reserves()
    get_swap_cost_usd(eth_price)


if __name__ == "__main__":
    main()
