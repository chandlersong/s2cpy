from s2cpy.infrastructure.settings import get_global_config, setup_global_logging, AppSettings, PolyMarketRelayerAccount
from loguru import logger


async def test_config():
    config = get_global_config()
    setup_global_logging(config.log)
    logger.info(f"应用名称: {config.instance_name}")
    logger.info(f"运行环境: {config.environment}")
    logger.info(f"debug: {config.debug}")
    assert config.debug == True
    assert config.environment == "untest"


def test_mini_account_config():
    cfg = {
        "accounts": {
            "broker1": {"name": "123", "type": "polymarket_relayer_account", "private_key": "abc",
                        "funder_address": "bcd",
                        "deposit_wallet": "efg"},
        },
    }

    s = AppSettings(**cfg)

    assert isinstance(s.accounts["broker1"], PolyMarketRelayerAccount)
    assert s.get_default_account().private_key == "abc"
    assert s.get_default_account().funder_address == "bcd"
    assert s.get_default_account().deposit_wallet == "efg"
    assert s.get_default_account().name == "123"


def test_account_config_with_defined_account():
    cfg = {
        "accounts": {
            "broker1": {"name": "123", "type": "polymarket_relayer_account", "private_key": "abc",
                        "funder_address": "bcd",
                        "deposit_wallet": "efg"},
            "broker2": {"name": "1111", "type": "polymarket_relayer_account", "private_key": "333",
                        "funder_address": "222",
                        "deposit_wallet": "555"},

        },
        "default_account": "broker1",
    }

    s = AppSettings(**cfg)

    assert s.get_default_account().name == "123"
