"""
Telliot-feeds-backed price fetcher for the relayer.

This mirrors the Layer Values Monitor's telliot-feeds integration:
`layer-values-monitor/src/layer_values_monitor/telliot_feeds.py`

Scope (initial): SpotPrice-style queries only (asset/currency).
"""

from __future__ import annotations

import asyncio
import logging
from typing import Optional, Tuple

from clamfig.base import Registry
from eth_abi import decode
from eth_utils import decode_hex

# Ensure older telliot-feeds releases can import under eth-abi v5+
# from src.eth_abi_compat import ensure_eth_abi_single_helpers

# ensure_eth_abi_single_helpers()

from telliot_feeds.datafeed import DataFeed
from telliot_feeds.datasource import DataSource
from telliot_feeds.dtypes.datapoint import OptionalDataPoint
from telliot_feeds.feeds import CATALOG_FEEDS, DATAFEED_BUILDER_MAPPING
from telliot_feeds.queries.abi_query import AbiQuery
from telliot_feeds.queries.json_query import JsonQuery
from telliot_feeds.queries.query_catalog import query_catalog

from src.logger_utils import get_logger


logger = get_logger(__name__)


def _strip_0x(s: Optional[str]) -> str:
    if not s:
        return ""
    return s[2:] if s.startswith("0x") else s


def _get_query_from_data(query_data: bytes) -> AbiQuery | JsonQuery | None:
    for q_type in (JsonQuery, AbiQuery):
        try:
            return q_type.get_query_from_data(query_data)
        except ValueError:
            pass
    return None


def _get_query(query_data_hex: str) -> AbiQuery | JsonQuery | None:
    qd = decode_hex(query_data_hex)
    return _get_query_from_data(qd)


def _get_feed_from_catalog(tag: str) -> DataFeed | None:
    return CATALOG_FEEDS.get(tag)


def _get_source_from_data(query_data: bytes, log: logging.Logger) -> DataSource | None:
    """
    Recreate data source using query type decoded from query_data.
    This is copied/adapted from LVM.
    """
    try:
        query_type, encoded_param_values = decode(["string", "bytes"], query_data)
    except OverflowError:
        log.error("OverflowError while decoding query data.")
        return None
    try:
        cls = Registry.registry[query_type]
    except KeyError:
        log.error(f"Unsupported query type: {query_type}")
        return None
    try:
        params_abi = cls.abi
    except AttributeError:
        log.error(f"query type {query_type} doesn't have abi attribute to decode params")
        return None
    param_names = [p["name"] for p in params_abi]
    param_types = [p["type"] for p in params_abi]
    param_values = decode(param_types, encoded_param_values)

    feed_builder = DATAFEED_BUILDER_MAPPING.get(query_type)
    if feed_builder is None:
        log.error(f"query type {query_type} not supported by datafeed builder")
        return None

    source_class = feed_builder.source.__class__
    source = source_class()
    for key, value in zip(param_names, param_values, strict=False):
        setattr(source, key, value)
    return source


async def _get_feed(query_id: str, query: AbiQuery | JsonQuery | None, log: logging.Logger) -> DataFeed | None:
    if query is None:
        log.warning(f"No query data found for query_id: {query_id}")
        return None

    # Some telliot-feeds versions have edge cases in query_catalog.find that can raise.
    # If it fails, treat as "not in catalog" and reconstruct the source from query_data.
    try:
        catalog_entry = query_catalog.find(query_id=query_id)
    except Exception as e:
        log.debug(f"telliot-feeds query_catalog.find failed for query_id={query_id}: {e}")
        catalog_entry = []

    if len(catalog_entry) == 0:
        source = _get_source_from_data(query_data=query.query_data, log=log)
        if source is None:
            log.warning("no source found in telliot-feeds for query")
            return None
        return DataFeed(query=query, source=source)
    return _get_feed_from_catalog(catalog_entry[0].tag)


async def _fetch_value(feed: DataFeed, timeout_seconds: float, log: logging.Logger) -> OptionalDataPoint:
    try:
        return await asyncio.wait_for(feed.source.fetch_new_datapoint(), timeout=timeout_seconds)
    except TimeoutError:
        log.warning(f"Timeout fetching trusted value from telliot-feeds ({timeout_seconds}s)")
        return None
    except Exception as e:
        log.warning(f"Error fetching trusted value from telliot-feeds: {e}")
        return None


async def fetch_spot_price_from_telliot_feeds(
    *,
    query_id_hex: str,
    query_data_hex: str,
    timeout_seconds: float = 15.0,
) -> Tuple[Optional[float], Optional[Exception]]:
    """
    Fetch a SpotPrice value from telliot-feeds.

    Args:
        query_id_hex: hex string for query_id (may include 0x prefix)
        query_data_hex: hex string for query_data (may include 0x prefix)
        timeout_seconds: overall timeout for source fetch

    Returns:
        (price, error)
    """
    try:
        qid = _strip_0x(query_id_hex).lower()
        query = _get_query(query_data_hex)
        feed = await _get_feed(qid, query, logger)
        if feed is None:
            return None, Exception("telliot-feeds: could not build feed for query")

        # Scope guard: SpotPrice only
        if not (hasattr(feed.query, "asset") and hasattr(feed.query, "currency")):
            return None, Exception("telliot-feeds: unsupported query type (not SpotPrice)")

        datapoint = await _fetch_value(feed, timeout_seconds, logger)
        if not datapoint:
            return None, Exception("telliot-feeds: no datapoint returned")

        value, _dt = datapoint
        if value is None:
            return None, Exception("telliot-feeds: datapoint value is None")

        return float(value), None
    except Exception as e:
        return None, Exception(f"telliot-feeds: error fetching price: {e}")


