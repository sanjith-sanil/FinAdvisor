"""add_statement_password_encrypted_to_cards

Revision ID: 96ac5a1dabea
Revises: d78b14bbfbee
Create Date: 2026-06-08 09:52:14.064177

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '96ac5a1dabea'
down_revision = 'd78b14bbfbee'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("cards", sa.Column("statement_password_encrypted", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("cards", "statement_password_encrypted")

