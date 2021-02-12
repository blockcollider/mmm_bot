import os

import pytest
import sqlalchemy
from sqlalchemy.pool import StaticPool

from mm_bot.model.repository import OrderRepository
from mm_bot.model.order import metadata, MakerOrder, TakerOrder
from mm_bot.model.constants import Status

@pytest.fixture
def repository_with_schema(caplog):
    """
    This dance with creating test.db in file would not be necessary if
    both sqlalchemy engine and Database could be configured to share the same
    in mem sqlite database
    """
    caplog.set_level(__import__('logging').DEBUG)
    self_dir = os.path.dirname(os.path.abspath(__file__))
    main_dir = os.path.abspath(os.path.join(self_dir, '..', '..', '..'))

    url = f'sqlite:///{main_dir}/test.db'
    engine = sqlalchemy.create_engine(url)
    metadata.create_all(engine)

    r = OrderRepository(url)

    yield r

    metadata.drop_all(engine)
    os.remove(f'{main_dir}/test.db')

@pytest.mark.asyncio
async def test_instance():
    r = OrderRepository('sqlite://:memory:')
    assert isinstance(r, OrderRepository)

    await r.close()

@pytest.mark.asyncio
async def test_get_order_by_id(repository_with_schema):
    orders = await repository_with_schema.get_all_orders('maker')
    assert len(orders) == 0

    maker_order = MakerOrder(
            exchange='borderless',
            status='open', # open
            order_type='sell',
            currency='BTC/ETH',
            order_body={'foo': 'bar', 'baz': 1},
            tx_hash='a1b2b3c4d5e6faa2321',
            tx_output_index=1,
            block_height='1',
            taker_order_body={},
            created_at=None,
            updated_at=None,
            id=None,
            )
    maker_order = await repository_with_schema.create_order(maker_order)
    assert maker_order.id == 1

    order = await repository_with_schema.get_order_by_id('maker', maker_order.id)
    assert order.id == maker_order.id
    assert order.tx_hash == maker_order.tx_hash

    order = await repository_with_schema.get_order_by_id('maker', 1000000)
    assert order is None


@pytest.mark.asyncio
async def test_get_all_orders(repository_with_schema):
    orders = await repository_with_schema.get_all_orders('taker')
    assert len(orders) == 0

    orders = await repository_with_schema.get_all_orders('maker')
    assert len(orders) == 0

    maker_order = MakerOrder(
            exchange='borderless',
            status='open', # open
            order_type='sell',
            currency='BTC/ETH',
            order_body={'foo': 'bar', 'baz': 1},
            tx_hash='a1b2b3c4d5e6faa2321',
            tx_output_index=1,
            block_height='1',
            taker_order_body={},
            created_at=None,
            updated_at=None,
            id=None,
            )
    maker_order = await repository_with_schema.create_order(maker_order)
    assert maker_order.id == 1

    filled_maker_order = MakerOrder(
            exchange='borderless',
            status='filled', # filled
            order_type='sell',
            currency='BTC/ETH',
            order_body={'foo': 'bar', 'baz': 1},
            tx_hash='a1b2b3c4d5e6faa2321',
            tx_output_index=1,
            block_height='1',
            taker_order_body={},
            created_at=None,
            updated_at=None,
            id=None,
            )
    filled_maker_order = await repository_with_schema.create_order(filled_maker_order)
    assert filled_maker_order.id == 2

    all_maker_orders = await repository_with_schema.get_all_orders('maker')
    assert len(all_maker_orders) == 2


@pytest.mark.asyncio
async def test_get_open_orders(repository_with_schema):
    open_orders = await repository_with_schema.get_open_orders('taker')
    assert len(open_orders) == 0

    open_orders = await repository_with_schema.get_open_orders('maker')
    assert len(open_orders) == 0

    maker_order = MakerOrder(
            exchange='borderless',
            status='open',
            order_type='sell',
            currency='BTC/ETH',
            order_body={'foo': 'bar', 'baz': 1},
            tx_hash='a1b2b3c4d5e6faa2321',
            tx_output_index=1,
            block_height='1',
            taker_order_body={},
            created_at=None,
            updated_at=None,
            id=None,
            )
    maker_order = await repository_with_schema.create_order(maker_order)
    assert maker_order.id == 1

    taker_order = TakerOrder(
        exchange='binance',
        status='open',
        order_type='buy',
        currency='BTC/ETH',
        order_body={'foo': 'bar', 'baz': 2},
        order_id='ee55df98-95d7-409f-a8f0-d8a5bf047acd',
        maker_order_id = maker_order.id,
        created_at=None,
        updated_at=None,
    )
    taker_order = await repository_with_schema.create_order(taker_order)
    assert taker_order.id == 1

    open_taker_orders_count = await repository_with_schema.count_open_orders('taker')
    open_orders = await repository_with_schema.get_open_orders('taker')
    assert len(open_orders) == open_taker_orders_count
    assert isinstance(open_orders[0], TakerOrder)
    assert open_orders[0].id == taker_order.id

    open_maker_orders_count = await repository_with_schema.count_open_orders('maker')
    open_orders = await repository_with_schema.get_open_orders('maker')
    assert len(open_orders) == open_maker_orders_count
    assert isinstance(open_orders[0], MakerOrder)
    assert open_orders[0].id == maker_order.id

    await repository_with_schema.delete_order(maker_order)
    await repository_with_schema.delete_order(taker_order)

    open_orders = await repository_with_schema.get_open_orders('maker')
    assert len(open_orders) == 0
    open_orders = await repository_with_schema.get_open_orders('taker')
    assert len(open_orders) == 0

    await repository_with_schema.close()


@pytest.mark.asyncio
async def test_get_taker_orders_by_maker_id(repository_with_schema):
    taker_order_1 = TakerOrder(
        exchange='binance',
        status='open',
        order_type='buy',
        currency='BTC/ETH',
        order_body={'foo': 'bar', 'baz': 2},
        order_id='ee55df98-95d7-409f-a8f0-d8a5bf047acd',
        maker_order_id = 1,
        created_at=None,
        updated_at=None,
    )

    taker_order_2 = TakerOrder(
        exchange='binance',
        status='open',
        order_type='buy',
        currency='BTC/ETH',
        order_body={'foo': 'bar', 'baz': 2},
        order_id='ee55df98-95d7-409f-a8f0-d8a5bf047acd',
        maker_order_id = 1,
        created_at=None,
        updated_at=None,
    )

    taker_order_1 = await repository_with_schema.create_order(taker_order_1)
    taker_order_2 = await repository_with_schema.create_order(taker_order_2)

    by_maker_order_id = await repository_with_schema.get_taker_orders_by_maker_id({1})
    assert by_maker_order_id[0] == taker_order_1
    assert by_maker_order_id[1] == taker_order_2



@pytest.mark.asyncio
async def test_update_order(repository_with_schema):
    taker_order = TakerOrder(
        exchange='binance',
        status='open',
        order_type='buy',
        currency='BTC/ETH',
        order_body={'foo': 'bar', 'baz': 2},
        order_id='ee55df98-95d7-409f-a8f0-d8a5bf047acd',
        maker_order_id = 1,
        created_at=None,
        updated_at=None,
    )

    new_order_id = 'aaa'
    taker_order = await repository_with_schema.create_order(taker_order)
    taker_order.order_id = new_order_id
    await repository_with_schema.update_order(taker_order)

    fetched_order, = await repository_with_schema.get_open_orders('taker')
    assert fetched_order == taker_order
    assert fetched_order.order_id == new_order_id

@pytest.mark.asyncio
async def test_update_status(repository_with_schema):
    taker_order = TakerOrder(
        exchange='binance',
        status='open',
        order_type='buy',
        currency='BTC/ETH',
        order_body={'foo': 'bar', 'baz': 2},
        order_id='ee55df98-95d7-409f-a8f0-d8a5bf047acd',
        maker_order_id = 1,
        created_at=None,
        updated_at=None,
    )

    new_status = Status.CANCELED
    taker_order = await repository_with_schema.create_order(taker_order)
    await repository_with_schema.update_status([taker_order], new_status)

    cancelled_order,  = await repository_with_schema._get_orders('taker', new_status)
    assert cancelled_order.order_id == taker_order.order_id
    assert cancelled_order.exchange == taker_order.exchange

@pytest.mark.asyncio
async def test_find_update_or_create_orders(repository_with_schema):
    taker_order = TakerOrder(
        exchange='binance',
        status='open',
        order_type='buy',
        currency='BTC/ETH',
        order_body={'foo': 'bar', 'baz': 2},
        order_id='ee55df98-95d7-409f-a8f0-d8a5bf047acd',
        maker_order_id = 1,
        created_at=None,
        updated_at=None,
    )
    taker_order = await repository_with_schema.create_order(taker_order)

    updated_order_body = {'foo': 'bar bar'}
    new_taker_order = TakerOrder(
        exchange='binance',
        status='open',
        order_type='buy',
        currency='BTC/ETH',
        order_body={'foo': 'bar', 'baz': 3},
        order_id='fe55df98-95d7-409f-a8f0-d8a5bf047acd',
        maker_order_id = 2,
        created_at=None,
        updated_at=None,
    )
    taker_order.order_body = updated_order_body

    updated_orders = await repository_with_schema.find_update_or_create_orders([taker_order, new_taker_order])
    assert len(updated_orders) == 2
    for order in updated_orders:
        if order.order_id == new_taker_order.order_id:
            assert order.id == 2
        else:
            assert order.id == taker_order.id
            assert order.order_body == updated_order_body
            assert order == taker_order

