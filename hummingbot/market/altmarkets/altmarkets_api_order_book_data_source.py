#!/usr/bin/env python

import aiohttp
import asyncio
import json
import random
import logging
import pandas as pd
import time
from typing import (
    Any,
    AsyncIterable,
    Dict,
    List,
    Optional,
)
import websockets
from websockets.exceptions import ConnectionClosed

from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.order_book_message import OrderBookMessage
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.data_type.order_book_tracker_entry import OrderBookTrackerEntry
from hummingbot.core.utils import async_ttl_cache
from hummingbot.core.utils.async_utils import safe_gather
from hummingbot.logger import HummingbotLogger
from hummingbot.market.altmarkets.altmarkets_order_book import AltmarketsOrderBook
from hummingbot.market.altmarkets.altmarkets_constants import Constants


class AltmarketsAPIOrderBookDataSource(OrderBookTrackerDataSource):

    _haobds_logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._haobds_logger is None:
            cls._haobds_logger = logging.getLogger(__name__)
        return cls._haobds_logger

    def __init__(self, trading_pairs: Optional[List[str]] = None):
        super().__init__()
        self._trading_pairs: Optional[List[str]] = trading_pairs

    @classmethod
    async def get_last_traded_prices(cls, trading_pairs: List[str]) -> Dict[str, float]:
        results = dict()
        # Altmarkets rate limit is 100 https requests per 10 seconds
        random.seed()
        randSleep = (random.randint(1, 9) + random.randint(1, 9)) / 10
        await asyncio.sleep(0.5 + randSleep)
        async with aiohttp.ClientSession() as client:
            resp = await client.get(Constants.EXCHANGE_ROOT_API + Constants.TICKER_URI)
            resp_json = await resp.json()
            for trading_pair in trading_pairs:
                resp_record = [resp_json[symbol] for symbol in list(resp_json.keys()) if symbol == trading_pair][0]['ticker']
                results[trading_pair] = float(resp_record["last"])
        return results

    @classmethod
    @async_ttl_cache(ttl=60 * 30, maxsize=1)
    async def get_active_exchange_markets(cls) -> pd.DataFrame:
        """
        Returned data frame should have trading pair as index and include usd volume, baseAsset and quoteAsset
        """
        # Altmarkets rate limit is 100 https requests per 10 seconds
        random.seed()
        randSleep = (random.randint(1, 9) + random.randint(1, 9)) / 10
        await asyncio.sleep(0.5 + randSleep)
        async with aiohttp.ClientSession() as client:

            market_response, exchange_response = await safe_gather(
                client.get(Constants.EXCHANGE_ROOT_API + Constants.TICKER_URI),
                client.get(Constants.EXCHANGE_ROOT_API + Constants.SYMBOLS_URI)
            )
            market_response: aiohttp.ClientResponse = market_response
            exchange_response: aiohttp.ClientResponse = exchange_response

            if market_response.status != 200:
                raise IOError(f"Error fetching Altmarkets markets information. "
                              f"HTTP status is {market_response.status}.")
            if exchange_response.status != 200:
                raise IOError(f"Error fetching Altmarkets exchange information. "
                              f"HTTP status is {exchange_response.status}.")

            market_data = await market_response.json()
            exchange_data = await exchange_response.json()

            attr_name_map = {"base_unit": "baseAsset", "quote_unit": "quoteAsset"}

            trading_pairs: Dict[str, Any] = {
                item["id"]: {attr_name_map[k]: item[k] for k in ["base_unit", "quote_unit"]}
                for item in exchange_data
                if item["state"] == "enabled"
            }

            market_data: List[Dict[str, Any]] = [
                {**market_data[symbol], **trading_pairs[symbol]}
                for symbol in list(market_data.keys())
                if symbol in trading_pairs
            ]

            # Build the data frame.
            all_markets: pd.DataFrame = pd.DataFrame.from_records(data=market_data, index="symbol")
            all_markets.loc[:, "USDVolume"] = all_markets.amount
            all_markets.loc[:, "volume"] = all_markets.vol

            return all_markets.sort_values("USDVolume", ascending=False)

    async def get_trading_pairs(self) -> List[str]:
        if not self._trading_pairs:
            try:
                active_markets: pd.DataFrame = await self.get_active_exchange_markets()
                self._trading_pairs = active_markets.index.tolist()
            except Exception:
                self._trading_pairs = []
                self.logger().network(
                    "Error getting active exchange information.",
                    exc_info=True,
                    app_warning_msg="Error getting active exchange information. Check network connection."
                )
        return self._trading_pairs

    @staticmethod
    async def get_snapshot(client: aiohttp.ClientSession, trading_pair: str) -> Dict[str, Any]:
        # when type is set to "step0", the default value of "depth" is 150
        # params: Dict = {"symbol": trading_pair, "type": "step0"}
        # Altmarkets rate limit is 100 https requests per 10 seconds
        random.seed()
        randSleep = (random.randint(1, 9) + random.randint(1, 9)) / 10
        await asyncio.sleep(0.5 + randSleep)
        async with client.get(Constants.EXCHANGE_ROOT_API + Constants.DEPTH_URI.format(trading_pair=trading_pair)) as response:
            response: aiohttp.ClientResponse = response
            if response.status != 200:
                raise IOError(f"Error fetching Altmarkets market snapshot for {trading_pair}. "
                              f"HTTP status is {response.status}.")
            api_data = await response.read()
            data: Dict[str, Any] = json.loads(api_data)
            return data

    async def get_tracking_pairs(self) -> Dict[str, OrderBookTrackerEntry]:
        # Get the currently active markets
        async with aiohttp.ClientSession() as client:
            trading_pairs: List[str] = await self.get_trading_pairs()
            retval: Dict[str, OrderBookTrackerEntry] = {}

            number_of_pairs: int = len(trading_pairs)
            for index, trading_pair in enumerate(trading_pairs):
                try:
                    snapshot: Dict[str, Any] = await self.get_snapshot(client, trading_pair)
                    snapshot_msg: OrderBookMessage = AltmarketsOrderBook.snapshot_message_from_exchange(
                        snapshot,
                        metadata={"trading_pair": trading_pair}
                    )
                    order_book: OrderBook = self.order_book_create_function()
                    order_book.apply_snapshot(snapshot_msg.bids, snapshot_msg.asks, snapshot_msg.update_id)
                    retval[trading_pair] = OrderBookTrackerEntry(trading_pair, snapshot_msg.timestamp, order_book)
                    self.logger().info(f"Initialized order book for {trading_pair}. "
                                       f"{index + 1}/{number_of_pairs} completed.")
                except Exception:
                    self.logger().error(f"Error getting snapshot for {trading_pair}. ", exc_info=True)
                    await asyncio.sleep(5)
            return retval

    async def _inner_messages(self,
                              ws: websockets.WebSocketClientProtocol) -> AsyncIterable[str]:
        # Terminate the recv() loop as soon as the next message timed out, so the outer loop can reconnect.
        try:
            while True:
                try:
                    msg: str = await asyncio.wait_for(ws.recv(), timeout=Constants.MESSAGE_TIMEOUT)
                    yield msg
                except asyncio.TimeoutError:
                    try:
                        pong_waiter = await ws.ping()
                        await asyncio.wait_for(pong_waiter, timeout=Constants.PING_TIMEOUT)
                    except asyncio.TimeoutError:
                        raise
        except asyncio.TimeoutError:
            self.logger().warning("WebSocket ping timed out. Going to reconnect...")
            return
        except ConnectionClosed:
            return
        finally:
            await ws.close()

    async def listen_for_trades(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        while True:
            try:
                trading_pairs: List[str] = await self.get_trading_pairs()
                async with websockets.connect(Constants.EXCHANGE_WS_URI) as ws:
                    ws: websockets.WebSocketClientProtocol = ws
                    for trading_pair in trading_pairs:
                        subscribe_request: Dict[str, Any] = {
                            "event": Constants.WS_PUSHER_SUBSCRIBE_EVENT,
                            "streams": [stream.format(trading_pair=trading_pair) for stream in Constants.WS_TRADE_SUBSCRIBE_STREAMS]
                        }
                        await ws.send(json.dumps(subscribe_request))

                    async for raw_msg in self._inner_messages(ws):
                        # Altmarkets's data value for id is a large int too big for ujson to parse
                        msg: Dict[str, Any] = json.loads(raw_msg)
                        if "ping" in raw_msg:
                            await ws.send(f'{{"op":"pong","timestamp": {str(msg["ping"])}}}')
                        elif "subscribed" in raw_msg:
                            pass
                        elif ".trades" in raw_msg:
                            trading_pair = list(msg.keys())[0].split(".")[0]
                            for trade in msg[f"{trading_pair}.trades"]["trades"]:
                                trade_message: OrderBookMessage = AltmarketsOrderBook.trade_message_from_exchange(
                                    trade,
                                    metadata={"trading_pair": trading_pair}
                                )
                                output.put_nowait(trade_message)
                        else:
                            # Debug log output for pub WS messages
                            self.logger().info(f"Unrecognized message received from Altmarkets websocket: {msg}")
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error("Trades: Unexpected error with WebSocket connection. Retrying after 30 seconds...",
                                    exc_info=True)
                await asyncio.sleep(Constants.MESSAGE_TIMEOUT)

    async def listen_for_order_book_diffs(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        while True:
            try:
                trading_pairs: List[str] = await self.get_trading_pairs()
                async with websockets.connect(Constants.EXCHANGE_WS_URI) as ws:
                    ws: websockets.WebSocketClientProtocol = ws
                    for trading_pair in trading_pairs:
                        subscribe_request: Dict[str, Any] = {
                            "event": "subscribe",
                            "streams": [stream.format(trading_pair=trading_pair) for stream in Constants.WS_OB_SUBSCRIBE_STREAMS]
                        }
                        await ws.send(json.dumps(subscribe_request))

                    async for raw_msg in self._inner_messages(ws):
                        # Altmarkets's data value for id is a large int too big for ujson to parse
                        msg: Dict[str, Any] = json.loads(raw_msg)
                        if "ping" in raw_msg:
                            await ws.send(f'{{"op":"pong","timestamp": {str(msg["ping"])}}}')
                        elif "subscribed" in raw_msg:
                            pass
                        elif ".ob-inc" in raw_msg:
                            # msg_key = list(msg.keys())[0]
                            trading_pair = list(msg.keys())[0].split(".")[0]
                            order_book_message: OrderBookMessage = AltmarketsOrderBook.diff_message_from_exchange(
                                msg[f"{trading_pair}.ob-inc"],
                                metadata={"trading_pair": trading_pair}
                            )
                            output.put_nowait(order_book_message)
                        elif ".ob-snap" in raw_msg:
                            # msg_key = list(msg.keys())[0]
                            trading_pair = list(msg.keys())[0].split(".")[0]
                            order_book_message: OrderBookMessage = AltmarketsOrderBook.snapshot_message_from_exchange(
                                msg[f"{trading_pair}.ob-snap"],
                                metadata={"trading_pair": trading_pair}
                            )
                            output.put_nowait(order_book_message)
                        else:
                            # Debug log output for pub WS messages
                            self.logger().info(f"OB: Unrecognized message received from Altmarkets websocket: {msg}")
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error("Unexpected error with WebSocket connection. Retrying after 30 seconds...",
                                    exc_info=True)
                await asyncio.sleep(Constants.MESSAGE_TIMEOUT)

    async def listen_for_order_book_snapshots(self, ev_loop: asyncio.BaseEventLoop, output: asyncio.Queue):
        while True:
            try:
                trading_pairs: List[str] = await self.get_trading_pairs()
                async with aiohttp.ClientSession() as client:
                    for trading_pair in trading_pairs:
                        try:
                            snapshot: Dict[str, Any] = await self.get_snapshot(client, trading_pair)
                            snapshot_message: OrderBookMessage = AltmarketsOrderBook.snapshot_message_from_exchange(
                                snapshot,
                                metadata={"trading_pair": trading_pair}
                            )
                            output.put_nowait(snapshot_message)
                            self.logger().debug(f"Saved order book snapshot for {trading_pair}")
                            await asyncio.sleep(5.0)
                        except asyncio.CancelledError:
                            raise
                        except Exception:
                            self.logger().error("Unexpected error.", exc_info=True)
                            await asyncio.sleep(5.0)
                    this_hour: pd.Timestamp = pd.Timestamp.utcnow().replace(minute=0, second=0, microsecond=0)
                    next_hour: pd.Timestamp = this_hour + pd.Timedelta(hours=1)
                    delta: float = next_hour.timestamp() - time.time()
                    await asyncio.sleep(delta)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error("Unexpected error.", exc_info=True)
                await asyncio.sleep(5.0)
