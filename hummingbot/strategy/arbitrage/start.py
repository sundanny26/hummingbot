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
    price_source_types = {
        'base': arbitrage_config_map.get("base_price_source_type").value,
        'quote': arbitrage_config_map.get("quote_price_source_type").value,
    }
    price_sources = {
        'base': arbitrage_config_map.get("base_price_source").value,
        'quote': arbitrage_config_map.get("quote_price_source").value,
    }
    price_source_markets = {
        'base': arbitrage_config_map.get("base_price_source_market").value,
        'quote': arbitrage_config_map.get("quote_price_source_market").value,
    }
    price_source_exchanges = {
        'base': arbitrage_config_map.get("base_price_source_exchange").value,
        'quote': arbitrage_config_map.get("quote_price_source_exchange").value,
    }
    price_source_custom_apis = {
        'base': arbitrage_config_map.get("base_price_source_custom_api").value,
        'quote': arbitrage_config_map.get("quote_price_source_custom_api").value,
    }

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
    # Add Asset Price Delegate markets to main markets if already using the exchange.
    for asset_type in ['base', 'quote']:
        if price_sources[asset_type] == "external_market":
            ext_exchange: str = price_source_exchanges[asset_type]
            if ext_exchange in [primary_market, secondary_market]:
                asset_pair: str = price_source_markets[asset_type]
                market_names.append((ext_exchange, [asset_pair]))

    self._initialize_wallet(token_trading_pairs=list(set(primary_assets + secondary_assets)))
    self._initialize_markets(market_names)
    self.assets = set(primary_assets + secondary_assets)

    primary_data = [self.markets[primary_market], primary_trading_pair] + list(primary_assets)
    secondary_data = [self.markets[secondary_market], secondary_trading_pair] + list(secondary_assets)
    self.market_trading_pair_tuples = [MarketTradingPairTuple(*primary_data), MarketTradingPairTuple(*secondary_data)]
    self.market_pair = ArbitrageMarketPair(*self.market_trading_pair_tuples)

    # Asset Price Feed Delegates
    price_delegates = {'base': None, 'quote': None}
    shared_ext_mkt = None
    # Initialize price delegates as needed for defined price sources.
    for asset_type in ['base', 'quote']:
        price_source: str = price_sources[asset_type]
        if price_source == "external_market":
            # For price feeds using other connectors
            ext_exchange: str = price_source_exchanges[asset_type]
            asset_pair: str = price_source_markets[asset_type]
            if ext_exchange in list(self.markets.keys()):
                # Use existing market if Exchange is already in markets
                ext_market = self.markets[ext_exchange]
            else:
                # Create markets otherwise
                UseSharedSource = (price_sources['quote'] == price_sources['base'] and
                                   price_source_exchanges['quote'] == price_source_exchanges['base'])
                # Use shared paper trade market if both price feeds are on the same exchange.
                if UseSharedSource and shared_ext_mkt is None and asset_type == 'base':
                    # Create Shared paper trade if not existing
                    shared_ext_mkt = create_paper_trade_market(price_source_exchanges['base'],
                                                               [price_source_markets['base'], price_source_markets['quote']])
                ext_market = shared_ext_mkt if UseSharedSource else create_paper_trade_market(ext_exchange, [asset_pair])
                if ext_exchange not in list(self.markets.keys()):
                    self.markets[ext_exchange]: ExchangeBase = ext_market
            price_delegates[asset_type]: AssetPriceDelegate = OrderBookAssetPriceDelegate(ext_market, asset_pair)
        elif price_source == "custom_api":
            # For price feeds using custom APIs
            custom_api: str = price_source_custom_apis[asset_type]
            price_delegates[asset_type]: AssetPriceDelegate = APIAssetPriceDelegate(custom_api)

    self.strategy = ArbitrageStrategy(market_pairs=[self.market_pair],
                                      min_profitability=min_profitability,
                                      logging_options=ArbitrageStrategy.OPTION_LOG_ALL,
                                      secondary_to_primary_base_conversion_rate=secondary_to_primary_base_conversion_rate,
                                      secondary_to_primary_quote_conversion_rate=secondary_to_primary_quote_conversion_rate,
                                      base_asset_price_delegate=price_delegates['base'],
                                      quote_asset_price_delegate=price_delegates['quote'],
                                      base_price_source_type=price_source_types['base'],
                                      quote_price_source_type=price_source_types['quote'],
                                      hb_app_notification=True)
