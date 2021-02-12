"""create tables

Revision ID: 4858f8eb42b6
Revises:
Create Date: 2019-11-02 23:53:55.929174+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '4858f8eb42b6'
down_revision = None
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import func

"""
id, created_at, updated_at
taker_order_id: (for borderless, hash + index)
maker_order_id: (foreign key to borderless_orders)


maker_orders <> taker_orders (1 to many)

taker_orders: <> maker_orders (
id, created_at, updated_at
status --> open, filled, cancelled
order_body: json?
order_id

sa.ForeignKeyConstraint(('maker_id',), ['maker_orders.id'], name='taker_orders_to_maker_orders'),
"""

def upgrade():
    op.create_table(
        'maker_orders',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('exchange', sa.VARCHAR(50), nullable=False, default='borderless'),
        sa.Column('status', sa.VARCHAR(50), nullable=False, default='open'), # open, filled, cancelled
        sa.Column('order_type', sa.VARCHAR(50), nullable=False), # buy or sell
        sa.Column('currency', sa.VARCHAR(255), nullable=False, default='ETH/BTC'),
        sa.Column('tx_hash', sa.VARCHAR(255), nullable=False),
        sa.Column('tx_output_index', sa.Integer(), nullable=False),
        sa.Column('order_body', sa.JSON(), nullable=False),
        sa.Column('block_height', sa.VARCHAR(255)),
        sa.Column('taker_order_body', sa.JSON(), nullable=True),

        sa.Column('created_at', sa.DateTime(timezone=True), server_default=func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), onupdate=func.now())
    )
    op.create_index('maker_orders_status', 'maker_orders', ['status'])
    op.create_index('maker_orders_tx_hash', 'maker_orders', ['tx_hash'])
    op.create_index('maker_orders_created_at', 'maker_orders', ['created_at'])
    op.create_index('maker_orders_updated_at', 'maker_orders', ['updated_at'])

    op.create_table(
        'taker_orders',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('exchange', sa.VARCHAR(50), nullable=False, default='binance'),
        sa.Column('status', sa.VARCHAR(50), nullable=False, default='open'), # open, filled, cancelled
        sa.Column('order_type', sa.VARCHAR(50), nullable=False), # buy or sell
        sa.Column('currency', sa.VARCHAR(255), nullable=False, default='ETH/BTC'),
        sa.Column('order_id', sa.VARCHAR(255), nullable=False),
        sa.Column('order_body', sa.JSON(), nullable=False),

        sa.Column('maker_order_id', sa.Integer(), nullable=False),

        sa.Column('created_at', sa.DateTime(timezone=True), server_default=func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), onupdate=func.now()),

        sa.ForeignKeyConstraint(('maker_order_id',), ['maker_orders.id'], name='taker_orders_to_maker_orders')
    )
    op.create_index('taker_orders_status', 'taker_orders', ['status'])
    op.create_index('taker_orders_order_id', 'taker_orders', ['order_id'])
    op.create_index('taker_orders_maker_order_id', 'taker_orders', ['maker_order_id'])
    op.create_index('taker_orders_created_at', 'taker_orders', ['created_at'])
    op.create_index('taker_orders_updated_at', 'taker_orders', ['updated_at'])

def downgrade():
    op.drop_table("taker_orders")
    op.drop_table("maker_orders")
