from math import log

#
# Liquidity math adapted from https://github.com/Uniswap/uniswap-v3-periphery/blob/main/contracts/libraries/LiquidityAmounts.sol
#

def get_liquidity_0(x, sa, sb):
    return x * sa * sb / (sb - sa)

def get_liquidity_1(y, sa, sb):
    return y / (sb - sa)

def get_liquidity(x, y, sp, sa, sb):
    if sp <= sa:
        liquidity = get_liquidity_0(x, sa, sb)
    elif sp < sb:
        liquidity0 = get_liquidity_0(x, sp, sb)
        liquidity1 = get_liquidity_1(y, sa, sp)
        liquidity = min(liquidity0, liquidity1)
    else:
        liquidity = get_liquidity_1(y, sa, sb)
    return liquidity

#
# Calculate x and y given liquidity and price range
#
def calculate_x(L, sp, sa, sb):
    sp = max(min(sp, sb), sa)     # if the price is outside the range, use the range endpoints instead
    return L * (sb - sp) / (sp * sb)

def calculate_y(L, sp, sa, sb):
    sp = max(min(sp, sb), sa)     # if the price is outside the range, use the range endpoints instead
    return L * (sp - sa)

# Convert Uniswap v3 tick to price
def to_price(tick):
    return 1.0001 ** tick

# Convert Uniswap v3 tick to sqrt(price)
def to_sqrt_price(tick):
    return 1.0001 ** (tick // 2)

# Convert price to Uniswap v3 tick
def to_tick(price):
    return int(round(log(price, 1.0001)))



#
# Express the value of position in terms of y (the stable asset)
#
#def position_value(x, y, price):
#    return x * price + y

#
# Compute the amount of assets in a position, and value from amounts
#
#def position_value_from_liquidity(liquidity, price_current, price_low, price_high):
#    sp = sqrt(price_current)
#    sa = sqrt(price_low)
#    sb = sqrt(price_high)
#    x = calculate_x(liquidity, sp, sa, sb)
#    y = calculate_y(liquidity, sp, sa, sb)
#   return position_value(x, y, price_current)


def tick_to_range_low(tick, tick_spacing):
    return tick // tick_spacing * tick_spacing

def tick_to_range_high(tick, tick_spacing):
    return tick_to_range_low(tick, tick_spacing) + tick_spacing


def assert_lt(a, b):
    if a > b + 1e-10:
        print(a, b, abs(a-b))
    assert a <= b + 1e-10

def compute_amounts(liquidity_usd, sp, sa, sb):
    p = sp ** 2

    x_unit = (sb - sp) / (sp * sb)
    y_unit = sp - sa

    x_wallet = 0
    y_wallet = liquidity_usd

    v_wallet = x_wallet * p + y_wallet
    v_unit = x_unit * p + y_unit
    n_units = v_wallet / v_unit

    x_pos = n_units * x_unit
    y_pos = n_units * y_unit

    assert_lt(x_pos * p + y_pos, liquidity_usd)

    return x_pos, y_pos
    
