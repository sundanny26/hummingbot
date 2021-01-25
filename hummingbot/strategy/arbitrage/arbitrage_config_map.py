from hummingbot.client.config.config_var import ConfigVar
from hummingbot.client.config.config_validators import (
    validate_exchange,
    validate_market_trading_pair,
    validate_decimal
)
from hummingbot.client.settings import (
    required_exchanges,
    EXAMPLE_PAIRS,
)
from decimal import Decimal
from typing import Optional


def validate_primary_market_trading_pair(value: str) -> Optional[str]:
    primary_market = arbitrage_config_map.get("primary_market").value
    return validate_market_trading_pair(primary_market, value)


def validate_secondary_market_trading_pair(value: str) -> Optional[str]:
    secondary_market = arbitrage_config_map.get("secondary_market").value
    return validate_market_trading_pair(secondary_market, value)


def primary_trading_pair_prompt():
    primary_market = arbitrage_config_map.get("primary_market").value
    example = EXAMPLE_PAIRS.get(primary_market)
    return "Enter the token trading pair you would like to trade on %s%s >>> " \
           % (primary_market, f" (e.g. {example})" if example else "")


def secondary_trading_pair_prompt():
    secondary_market = arbitrage_config_map.get("secondary_market").value
    example = EXAMPLE_PAIRS.get(secondary_market)
    return "Enter the token trading pair you would like to trade on %s%s >>> " \
           % (secondary_market, f" (e.g. {example})" if example else "")


def secondary_market_on_validated(value: str):
    required_exchanges.append(value)


def validate_price_source(value: str) -> Optional[str]:
    if value not in {"config_rate", "external_market", "custom_api"}:
        return "Invalid price source type."


def validate_price_source_exchange(value: str) -> Optional[str]:
    ActiveExchanges = [
        arbitrage_config_map.get("primary_market").value,
        arbitrage_config_map.get("secondary_market").value,
    ]
    if value in ActiveExchanges:
        return "Price source exchange cannot be the same as one of the active exchanges."
    return validate_exchange(value)


def on_validate_base_price_source(value: str):
    if value != "external_market":
        arbitrage_config_map["base_price_source_exchange"].value = None
        arbitrage_config_map["base_price_source_market"].value = None
    if value != "custom_api":
        arbitrage_config_map["base_price_source_custom_api"].value = None
    else:
        arbitrage_config_map["base_price_source_type"].value = None


def base_price_source_market_prompt() -> str:
    external_market = arbitrage_config_map.get("base_price_source_exchange").value
    return f'Enter the base token trading pair on {external_market} >>> '


def on_validated_base_price_source_exchange(value: str):
    if value is None:
        arbitrage_config_map["base_price_source_exchange"].value = None


def validate_base_price_source_market(value: str) -> Optional[str]:
    market = arbitrage_config_map.get("base_price_source_exchange").value
    return validate_market_trading_pair(market, value)


def on_validate_quote_price_source(value: str):
    if value != "external_market":
        arbitrage_config_map["quote_price_source_exchange"].value = None
        arbitrage_config_map["quote_price_source_market"].value = None
    if value != "custom_api":
        arbitrage_config_map["quote_price_source_custom_api"].value = None
    else:
        arbitrage_config_map["quote_price_source_type"].value = None


def quote_price_source_market_prompt() -> str:
    external_market = arbitrage_config_map.get("quote_price_source_exchange").value
    return f'Enter the quote token trading pair on {external_market} >>> '


def on_validated_quote_price_source_exchange(value: str):
    if value is None:
        arbitrage_config_map["quote_price_source_exchange"].value = None


def validate_quote_price_source_market(value: str) -> Optional[str]:
    market = arbitrage_config_map.get("quote_price_source_exchange").value
    return validate_market_trading_pair(market, value)


arbitrage_config_map = {
    "strategy":
        ConfigVar(key="strategy",
                  prompt="",
                  default="arbitrage"),
    "primary_market": ConfigVar(
        key="primary_market",
        prompt="Enter your primary exchange name >>> ",
        prompt_on_new=True,
        validator=validate_exchange,
        on_validated=lambda value: required_exchanges.append(value)),
    "secondary_market": ConfigVar(
        key="secondary_market",
        prompt="Enter your secondary exchange name >>> ",
        prompt_on_new=True,
        validator=validate_exchange,
        on_validated=secondary_market_on_validated),
    "primary_market_trading_pair": ConfigVar(
        key="primary_market_trading_pair",
        prompt=primary_trading_pair_prompt,
        prompt_on_new=True,
        validator=validate_primary_market_trading_pair),
    "secondary_market_trading_pair": ConfigVar(
        key="secondary_market_trading_pair",
        prompt=secondary_trading_pair_prompt,
        prompt_on_new=True,
        validator=validate_secondary_market_trading_pair),
    "min_profitability": ConfigVar(
        key="min_profitability",
        prompt="What is the minimum profitability for you to make a trade? (Enter 1 to indicate 1%) >>> ",
        prompt_on_new=True,
        default=Decimal("0.3"),
        validator=lambda v: validate_decimal(v, Decimal(-100), Decimal("100"), inclusive=True),
        type_str="decimal"),
    "base_price_source":
        ConfigVar(key="base_price_source",
                  prompt="Which base price source to use? (config_rate/external_market/custom_api) >>> ",
                  prompt_on_new=True,
                  type_str="str",
                  default="config_rate",
                  validator=validate_price_source,
                  on_validated=on_validate_base_price_source),
    "quote_price_source":
        ConfigVar(key="quote_price_source",
                  prompt="Which quote price source to use? (config_rate/external_market/custom_api) >>> ",
                  prompt_on_new=True,
                  type_str="str",
                  default="config_rate",
                  validator=validate_price_source,
                  on_validated=on_validate_quote_price_source),
    "secondary_to_primary_base_conversion_rate": ConfigVar(
        key="secondary_to_primary_base_conversion_rate",
        prompt="Enter conversion rate for secondary base asset value to primary base asset value, e.g. "
               "if primary base asset is USD, secondary is DAI and 1 USD is worth 1.25 DAI, "
               "the conversion rate is 0.8 (1 / 1.25) >>> ",
        prompt_on_new=True,
        required_if=lambda: arbitrage_config_map.get("base_price_source").value == "config_rate",
        default=Decimal("1"),
        validator=lambda v: validate_decimal(v, Decimal(0), Decimal("100"), inclusive=False),
        type_str="decimal"),
    "secondary_to_primary_quote_conversion_rate": ConfigVar(
        key="secondary_to_primary_quote_conversion_rate",
        prompt="Enter conversion rate for secondary quote asset value to primary quote asset value, e.g. "
               "if primary quote asset is USD, secondary is DAI and 1 USD is worth 1.25 DAI, "
               "the conversion rate is 0.8 (1 / 1.25) >>> ",
        prompt_on_new=True,
        required_if=lambda: arbitrage_config_map.get("quote_price_source").value == "config_rate",
        default=Decimal("1"),
        validator=lambda v: validate_decimal(v, Decimal(0), Decimal("100"), inclusive=False),
        type_str="decimal"),
    "base_price_source_exchange":
        ConfigVar(key="base_price_source_exchange",
                  prompt="Enter external base price source exchange name >>> ",
                  prompt_on_new=True,
                  required_if=lambda: arbitrage_config_map.get("base_price_source").value == "external_market",
                  type_str="str",
                  validator=validate_price_source_exchange,
                  on_validated=on_validated_base_price_source_exchange),
    "base_price_source_market":
        ConfigVar(key="base_price_source_market",
                  prompt=base_price_source_market_prompt,
                  prompt_on_new=True,
                  required_if=lambda: arbitrage_config_map.get("base_price_source").value == "external_market",
                  type_str="str",
                  validator=validate_base_price_source_market),
    "base_price_source_custom_api":
        ConfigVar(key="base_price_source_custom_api",
                  prompt="Enter base pricing API URL >>> ",
                  prompt_on_new=True,
                  required_if=lambda: arbitrage_config_map.get("base_price_source").value == "custom_api",
                  type_str="str"),
    "base_price_source_type":
        ConfigVar(key="base_price_source_type",
                  prompt="Which base price type to use? (mid_price/last_price/best_bid/best_ask) >>> ",
                  type_str="str",
                  required_if=lambda: arbitrage_config_map.get("base_price_source").value != "custom_api",
                  default="mid_price",
                  validator=lambda s: None if s in {"mid_price",
                                                    "last_price",
                                                    "best_bid",
                                                    "best_ask"} else
                  "Invalid price type."),
    "quote_price_source_exchange":
        ConfigVar(key="quote_price_source_exchange",
                  prompt="Enter quote external price source exchange name >>> ",
                  prompt_on_new=True,
                  required_if=lambda: arbitrage_config_map.get("quote_price_source").value == "external_market",
                  type_str="str",
                  validator=validate_price_source_exchange,
                  on_validated=on_validated_quote_price_source_exchange),
    "quote_price_source_market":
        ConfigVar(key="quote_price_source_market",
                  prompt=quote_price_source_market_prompt,
                  prompt_on_new=True,
                  required_if=lambda: arbitrage_config_map.get("quote_price_source").value == "external_market",
                  type_str="str",
                  validator=validate_quote_price_source_market),
    "quote_price_source_custom_api":
        ConfigVar(key="quote_price_source_custom_api",
                  prompt="Enter quote pricing API URL >>> ",
                  prompt_on_new=True,
                  required_if=lambda: arbitrage_config_map.get("quote_price_source").value == "custom_api",
                  type_str="str"),
    "quote_price_source_type":
        ConfigVar(key="quote_price_source_type",
                  prompt="Which quote price type to use? (mid_price/last_price/best_bid/best_ask) >>> ",
                  type_str="str",
                  required_if=lambda: arbitrage_config_map.get("quote_price_source").value != "custom_api",
                  default="mid_price",
                  validator=lambda s: None if s in {"mid_price",
                                                    "last_price",
                                                    "best_bid",
                                                    "best_ask"} else
                  "Invalid price type."),
}
