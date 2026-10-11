"""support conversation memory (last_intent)

Revision ID: 3f7a2b9c1d4e
Revises: 214a3e0210e6
Create Date: 2026-10-11 00:10:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '3f7a2b9c1d4e'
down_revision = '214a3e0210e6'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('support_conversations', schema=None) as batch_op:
        batch_op.add_column(sa.Column('last_intent', sa.String(length=40), nullable=True))
        batch_op.add_column(sa.Column('last_intent_at', sa.DateTime(), nullable=True))


def downgrade():
    with op.batch_alter_table('support_conversations', schema=None) as batch_op:
        batch_op.drop_column('last_intent_at')
        batch_op.drop_column('last_intent')
