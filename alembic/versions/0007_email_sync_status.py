"""add email sync status fields

Revision ID: 0007_email_sync_status
Revises: 0006_card_benefits
Create Date: 2026-04-27 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


revision = "0007_email_sync_status"
down_revision = "0006_card_benefits"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("email_configs", sa.Column("first_sync_done", sa.Boolean(), nullable=False, server_default=sa.text("false")))
    op.add_column("email_configs", sa.Column("total_emails_scanned", sa.Integer(), nullable=False, server_default=sa.text("0")))
    op.add_column("email_configs", sa.Column("sync_status", sa.String(length=50), nullable=False, server_default="idle"))
    op.add_column("email_configs", sa.Column("last_sync_error", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("email_configs", "last_sync_error")
    op.drop_column("email_configs", "sync_status")
    op.drop_column("email_configs", "total_emails_scanned")
    op.drop_column("email_configs", "first_sync_done")
