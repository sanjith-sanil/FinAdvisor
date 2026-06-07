"""add bank metadata and collection counters

Revision ID: 0004_bank_email_enforce
Revises: 0003_auto_collection
Create Date: 2026-04-22 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


revision = "0004_bank_email_enforce"
down_revision = "0003_auto_collection"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("transactions", sa.Column("bank_name", sa.String(length=100), nullable=True))
    op.add_column("transactions", sa.Column("bank_code", sa.String(length=20), nullable=True))
    op.add_column("transactions", sa.Column("sender_email", sa.String(length=255), nullable=True))
    op.add_column("transactions", sa.Column("sender_phone", sa.String(length=50), nullable=True))

    op.add_column("sms_emails_raw", sa.Column("bank_name", sa.String(length=100), nullable=True))
    op.add_column("sms_emails_raw", sa.Column("bank_code", sa.String(length=20), nullable=True))
    op.alter_column("sms_emails_raw", "subject", existing_type=sa.String(length=255), type_=sa.String(length=500))
    op.alter_column("sms_emails_raw", "message_id", existing_type=sa.String(length=255), type_=sa.String(length=500))
    op.create_unique_constraint("uq_sms_emails_raw_message_id", "sms_emails_raw", ["message_id"])

    op.add_column(
        "collection_logs",
        sa.Column("non_bank_emails_rejected", sa.Integer(), server_default=sa.text("0"), nullable=False),
    )
    op.add_column(
        "collection_logs",
        sa.Column("bank_emails_found", sa.Integer(), server_default=sa.text("0"), nullable=False),
    )
    op.add_column(
        "collection_logs",
        sa.Column("duplicates_skipped", sa.Integer(), server_default=sa.text("0"), nullable=False),
    )


def downgrade() -> None:
    op.drop_column("collection_logs", "duplicates_skipped")
    op.drop_column("collection_logs", "bank_emails_found")
    op.drop_column("collection_logs", "non_bank_emails_rejected")

    op.drop_constraint("uq_sms_emails_raw_message_id", "sms_emails_raw", type_="unique")
    op.alter_column("sms_emails_raw", "message_id", existing_type=sa.String(length=500), type_=sa.String(length=255))
    op.alter_column("sms_emails_raw", "subject", existing_type=sa.String(length=500), type_=sa.String(length=255))
    op.drop_column("sms_emails_raw", "bank_code")
    op.drop_column("sms_emails_raw", "bank_name")

    op.drop_column("transactions", "sender_phone")
    op.drop_column("transactions", "sender_email")
    op.drop_column("transactions", "bank_code")
    op.drop_column("transactions", "bank_name")
