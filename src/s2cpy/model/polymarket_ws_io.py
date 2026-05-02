from __future__ import annotations

from typing import Dict
from pydantic import BaseModel


class WSMarketUpdate(BaseModel):
	"""Example model for a market update message from a websocket stream.

	This is intentionally minimal — real schema should be extended based on the
	realtime API documentation from Polymarket.
	"""
	type: str
	market_id: str
	prices: Dict[str, float]
	timestamp: str



