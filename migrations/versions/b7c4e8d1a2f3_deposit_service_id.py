"""deposit service_id (SoleasPay)

Revision ID: b7c4e8d1a2f3
Revises: 3f7a2b9c1d4e
Create Date: 2026-10-11 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b7c4e8d1a2f3'
down_revision = '3f7a2b9c1d4e'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('deposits', schema=None) as batch_op:
        batch_op.add_column(sa.Column('service_id', sa.Integer(), nullable=True))


def downgrade():
    with op.batch_alter_table('deposits', schema=None) as batch_op:
        batch_op.drop_column('service_id')
