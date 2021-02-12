import logging
import unittest.mock

import pytest

from mm_bot.exchange.maker.borderless import _call_js_cli, JSCallFailedError

@pytest.mark.asyncio
async def test_call_js_raises():
    with pytest.raises(SystemExit) as excinfo:
        await _call_js_cli([
            'get', 'balance',
            '--bcRpcAddress', 'https://localhost:3001',
            '--bcRpcScookie', 'trololo',
            '--bcAddress', '0x7efbb13383757ca1f581dd5e20cb2e9f24448608'
            ])

    assert 1 == excinfo.value.code
    assert excinfo.type == SystemExit


@pytest.mark.asyncio
async def test_call_js_filters_sensitive_params():
    mock_logger = unittest.mock.Mock(logging.Logger)
    with pytest.raises(JSCallFailedError) as excinfo:
        await _call_js_cli([
            'cmd', 'argument',
            '--bcRpcAddress', 'https://localhost:3001',
            '--bcPrivateKeyHex', 'fbb2123ca3f2143dee',
            '--privateKey', '7efbb13383757ca1f581dd5e20cb2e9f24448608'
            ], mock_logger)

    joined_log_args = mock_logger.info.call_args[0][1]
    assert joined_log_args == 'cmd argument --bcRpcAddress https://localhost:3001 --bcPrivateKeyHex *** --privateKey ***'
