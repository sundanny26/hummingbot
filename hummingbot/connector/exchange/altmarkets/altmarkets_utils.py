import re
from hummingbot.connector.exchange.altmarkets.altmarkets_constants import Constants
from typing import (
    Optional,
    Tuple)
TRADING_PAIR_SPLITTER = re.compile(Constants.TRADING_PAIR_SPLITTER)


def split_trading_pair(trading_pair: str) -> Optional[Tuple[str, str]]:
    try:
        m = TRADING_PAIR_SPLITTER.match(trading_pair)
        return m.group(1), m.group(2)
    # Exceptions are now logged as warnings in trading pair fetcher
    except Exception:
        return None


def convert_from_exchange_trading_pair(exchange_trading_pair: str) -> Optional[str]:
    if split_trading_pair(exchange_trading_pair) is None:
        return None
    # Altmarkets uses lowercase (btcusdt)
    base_asset, quote_asset = split_trading_pair(exchange_trading_pair)
    return f"{base_asset.upper()}-{quote_asset.upper()}"


def convert_to_exchange_trading_pair(am_trading_pair: str) -> str:
    # Altmarkets uses lowercase (btcusdt)
    return am_trading_pair.replace("-", "").lower()
