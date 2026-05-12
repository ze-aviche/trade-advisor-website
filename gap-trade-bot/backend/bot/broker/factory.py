"""
Broker factory — instantiates the right BrokerBase subclass from a config dict.

Usage:
    broker = create_broker('alpaca', {'api_key': '...', 'api_secret': '...', 'paper': True})
    broker = create_broker('das',    {'host': '127.0.0.1', 'port': 9800})
"""
from __future__ import annotations
from typing import Any
from .base import BrokerBase


# Registry: broker_name → (display_label, required_config_keys)
_BROKER_REGISTRY: dict[str, dict] = {
    'alpaca': {
        'label':    'Alpaca Markets',
        'required': ['api_key', 'api_secret'],
        'optional': {'paper': True},
        'docs_url': 'https://alpaca.markets/docs/trading/',
    },
    'tradier': {
        'label':    'Tradier',
        'required': ['api_key'],
        'optional': {'paper': True},
        'docs_url': 'https://documentation.tradier.com/',
    },
    'tastytrade': {
        'label':    'Tastytrade',
        'required': ['username', 'password'],
        'optional': {'paper': False},
        'docs_url': 'https://developer.tastytrade.com/',
    },
    'das': {
        'label':    'DAS Trader Pro (local)',
        'required': [],
        'optional': {'host': '127.0.0.1', 'port': 9800,
                     'username': '', 'password': '', 'account': ''},
        'docs_url': 'https://dastrader.com/',
    },
}


def get_supported_brokers() -> list[dict]:
    """Return metadata for all supported brokers (for the settings UI dropdown)."""
    return [
        {
            'name':     name,
            'label':    meta['label'],
            'required': meta['required'],
            'docs_url': meta['docs_url'],
        }
        for name, meta in _BROKER_REGISTRY.items()
    ]


def create_broker(broker_name: str, config: dict[str, Any]) -> BrokerBase:
    """
    Instantiate and return the appropriate BrokerBase subclass.

    Args:
        broker_name: one of 'alpaca', 'tradier', 'tastytrade', 'das'
        config:      dict with API credentials / connection params

    Raises:
        ValueError:  unknown broker_name or missing required config key
    """
    broker_name = broker_name.lower().strip()

    if broker_name not in _BROKER_REGISTRY:
        supported = ', '.join(_BROKER_REGISTRY)
        raise ValueError(f"Unknown broker '{broker_name}'. Supported: {supported}")

    meta = _BROKER_REGISTRY[broker_name]
    for key in meta['required']:
        if not config.get(key):
            raise ValueError(f"Broker '{broker_name}' requires config key '{key}'")

    # Merge defaults then override with supplied config
    cfg = {**meta['optional'], **config}

    if broker_name == 'alpaca':
        from .alpaca import AlpacaBroker
        return AlpacaBroker(
            api_key    = cfg['api_key'],
            api_secret = cfg['api_secret'],
            paper      = bool(cfg.get('paper', True)),
        )

    if broker_name == 'tradier':
        from .tradier import TradierBroker
        return TradierBroker(
            api_key = cfg['api_key'],
            paper   = bool(cfg.get('paper', True)),
        )

    if broker_name == 'tastytrade':
        from .tastytrade import TastytradeBroker
        return TastytradeBroker(
            username = cfg['username'],
            password = cfg['password'],
            paper    = bool(cfg.get('paper', False)),
        )

    if broker_name == 'das':
        from .das import DASBroker
        return DASBroker(
            host     = cfg.get('host', '127.0.0.1'),
            port     = int(cfg.get('port', 9800)),
            username = cfg.get('username', ''),
            password = cfg.get('password', ''),
            account  = cfg.get('account', ''),
        )

    raise ValueError(f"No adapter implemented for '{broker_name}'")
