# Code for the "CEX/DEX arbitrage anatomy" simulations

This repository contains Python code for the artice [""CEX/DEX arbitrage anatomy""](https://atise.medium.com/anatomy-of-cex-dex-arbitrage-481936c83831).

The code is used to produce the graphs in the published article.

For visualization, it uses Matplotlib in combination with the [ING theme](https://pypi.org/project/ing-theme-matplotlib/).

# Assumptions

It assumes:
* A DEX with deep liquidity of $1 billion. This is large, but not unrealistic, as the ETH/USDC 0.05% pool on Uniswap v3 mainnet has a comparable *virtual* liquidity depth.
* The DEX has a `xy=k` pool with a stable / volatile asset pair.
* The volatility of the volatile asset is either 50% per year, or 5% per day (~90% per year) depending on the simulation. This matches the performance of ETH is less or more volatile periods.
* The base fee of arbitrage transactions is constant and does not depend on the price action
* The swap fees are not compounding.

It also makes the standard (not fully realistic) assumptions behing the LVR model.
* There is a CEX which trades the volatile asset
* The traders are not required to pay any trading fees on the CEX.
* The liquidity on the CEX is infinitely deep.
* There is a CEX/DEX arbitrager that has unlimited amount of stable assets, fast connections to both CEX and DEX, and will take all profitable trades at their maximum volume.

# Contents

* `simple_examples.py` - intuition-building examples directly discussed in the article.
* `simulation_examples.py` - examples on which the article's graphs are based.
* `replication.py` - code that aims to replicate and extend the Table 1 from the paper"Automated Market Making and Arbitrage Profits in the Presence of Fees".

# Simulations

The current implementation of price path simulations has significant RAM usage
and may require several minutes to complete. They could be improved by using the JIT
decorator, or by rewriting the code to a faster programming language.
