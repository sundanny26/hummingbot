from typing import (
    List,
    Tuple,
)
from decimal import Decimal
from hummingbot.connector.exchange_base import ExchangeBase
from hummingbot.connector.exchange.paper_trade import create_paper_trade_market
from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple
from hummingbot.strategy.arbitrage.arbitrage_market_pair import ArbitrageMarketPair
from hummingbot.strategy.arbitrage import (
    ArbitrageStrategy,
    AssetPriceDelegate,
    OrderBookAssetPriceDelegate,
    APIAssetPriceDelegate
)
from hummingbot.strategy.arbitrage.arbitrage_config_map import arbitrage_config_map


def start(self):
    primary_market = arbitrage_config_map.get("primary_market").value.lower()
    secondary_market = arbitrage_config_map.get("secondary_market").value.lower()
    raw_primary_trading_pair = arbitrage_config_map.get("primary_market_trading_pair").value
    raw_secondary_trading_pair = arbitrage_config_map.get("secondary_market_trading_pair").value
    min_profitability = arbitrage_config_map.get("min_profitability").value / Decimal("100")
    secondary_to_primary_base_conversion_rate = arbitrage_config_map["secondary_to_primary_base_conversion_rate"].value
    secondary_to_primary_quote_conversion_rate = arbitrage_config_map["secondary_to_primary_quote_conversion_rate"].value
    base_price_source_type = arbitrage_config_map.get("base_price_source_type").value
    quote_price_source_type = arbitrage_config_map.get("quote_price_source_type").value
    base_price_source = arbitrage_config_map.get("base_price_source").value
    quote_price_source = arbitrage_config_map.get("quote_price_source").value
    base_price_source_market = arbitrage_config_map.get("base_price_source_market").value
    quote_price_source_market = arbitrage_config_map.get("quote_price_source_market").value
    base_price_source_exchange = arbitrage_config_map.get("base_price_source_exchange").value
    quote_price_source_exchange = arbitrage_config_map.get("quote_price_source_exchange").value
    base_price_source_custom_api = arbitrage_config_map.get("base_price_source_custom_api").value
    quote_price_source_custom_api = arbitrage_config_map.get("quote_price_source_custom_api").value

    try:
        primary_trading_pair: str = raw_primary_trading_pair
        secondary_trading_pair: str = raw_secondary_trading_pair
        primary_assets: Tuple[str, str] = self._initialize_market_assets(primary_market, [primary_trading_pair])[0]
        secondary_assets: Tuple[str, str] = self._initialize_market_assets(secondary_market,
                                                                           [secondary_trading_pair])[0]
    except ValueError as e:
        self._notify(str(e))
        return

    market_names: List[Tuple[str, List[str]]] = [(primary_market, [primary_trading_pair]),
                                                 (secondary_market, [secondary_trading_pair])]
    self._initialize_wallet(token_trading_pairs=list(set(primary_assets + secondary_assets)))
    self._initialize_markets(market_names)
    self.assets = set(primary_assets + secondary_assets)

    primary_data = [self.markets[primary_market], primary_trading_pair] + list(primary_assets)
    secondary_data = [self.markets[secondary_market], secondary_trading_pair] + list(secondary_assets)
    self.market_trading_pair_tuples = [MarketTradingPairTuple(*primary_data), MarketTradingPairTuple(*secondary_data)]
    self.market_pair = ArbitrageMarketPair(*self.market_trading_pair_tuples)

    # Asset Price Feed Delegates
    shared_ext_mkt = None
    price_delegates = {'base': None, 'quote': None}
    # Use shared paper trade market if both price feeds are on the same exchange.
    if quote_price_source == base_price_source and quote_price_source_exchange == base_price_source_exchange:
        shared_ext_mkt = create_paper_trade_market(base_price_source_exchange,
                                                   [base_price_source_market, quote_price_source_market])
    # Initialize price delegates as needed for defined price sources.
    for asset_type in ['base', 'quote']:
        price_source: str = locals()[f"{asset_type}_price_source"]
        if price_source == "external_market":
            # For price feeds using other connectors
            ext_exchange: str = locals()[f"{asset_type}_price_source_exchange"]
            asset_pair: str = locals()[f"{asset_type}_price_source_market"]
            # Make separate paper trade markets if not shared.
            ext_market = create_paper_trade_market(ext_exchange, [asset_pair]) if shared_ext_mkt is None else shared_ext_mkt
            # Add paper trade market to markets if not conflicting - this is blocked by the Config helper.
            if ext_exchange not in list(self.markets.keys()):
                self.markets[ext_exchange]: ExchangeBase = ext_market
            price_delegates[asset_type]: AssetPriceDelegate = OrderBookAssetPriceDelegate(ext_market, asset_pair)
        elif price_source == "custom_api":
            # For price feeds using custom APIs
            custom_api: str = locals()[f"{asset_type}_price_source_custom_api"]
            price_delegates[asset_type]: AssetPriceDelegate = APIAssetPriceDelegate(custom_api)

    self.strategy = ArbitrageStrategy(market_pairs=[self.market_pair],
                                      min_profitability=min_profitability,
                                      logging_options=ArbitrageStrategy.OPTION_LOG_ALL,
                                      secondary_to_primary_base_conversion_rate=secondary_to_primary_base_conversion_rate,
                                      secondary_to_primary_quote_conversion_rate=secondary_to_primary_quote_conversion_rate,
                                      base_asset_price_delegate=price_delegates['base'],
                                      quote_asset_price_delegate=price_delegates['quote'],
                                      base_price_source_type=base_price_source_type,
                                      quote_price_source_type=quote_price_source_type,
                                      hb_app_notification=True)
