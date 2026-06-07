"""initial schema

Revision ID: 0001_init
Revises: 
Create Date: 2026-04-19 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0001_init"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("customer_id", sa.String(length=12), nullable=False, unique=True),
        sa.Column("full_name", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False, unique=True),
        sa.Column("phone", sa.String(length=15)),
        sa.Column("date_of_birth", sa.Date()),
        sa.Column("address", sa.Text()),
        sa.Column("profile_picture_url", sa.Text()),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True)),
    )

    op.create_table(
        "bank_accounts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("bank_name", sa.String(length=100), nullable=False),
        sa.Column("account_number_last4", sa.String(length=4)),
        sa.Column("account_type", sa.Enum("savings", "current", "salary", name="account_type")),
        sa.Column("current_balance", sa.DECIMAL(15, 2)),
        sa.Column("last_updated", sa.TIMESTAMP(timezone=True)),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )

    op.create_table(
        "cards",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("bank_name", sa.String(length=100), nullable=False),
        sa.Column("card_holder_name", sa.String(length=255), nullable=False),
        sa.Column("card_type", sa.Enum("credit", "debit", name="card_type"), nullable=False),
        sa.Column("card_last4", sa.String(length=4), nullable=False),
        sa.Column("card_network", sa.Enum("visa", "mastercard", "rupay", "amex", "other", name="card_network")),
        sa.Column("expiry_month", sa.Integer()),
        sa.Column("expiry_year", sa.Integer()),
        sa.Column("credit_limit", sa.DECIMAL(15, 2)),
        sa.Column("current_balance", sa.DECIMAL(15, 2)),
        sa.Column("available_balance", sa.DECIMAL(15, 2)),
        sa.Column("pending_emi_amount", sa.DECIMAL(15, 2)),
        sa.Column("emi_tenure_months", sa.Integer()),
        sa.Column("emi_interest_rate", sa.DECIMAL(5, 2)),
        sa.Column("monthly_emi_amount", sa.DECIMAL(15, 2)),
        sa.Column("billing_cycle_date", sa.Integer()),
        sa.Column("payment_due_date", sa.Integer()),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")),
        sa.Column("color_theme", sa.String(length=20)),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True)),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )

    op.create_table(
        "transactions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("card_id", postgresql.UUID(as_uuid=True)),
        sa.Column("bank_account_id", postgresql.UUID(as_uuid=True)),
        sa.Column("transaction_type", sa.Enum("debit", "credit", name="transaction_type"), nullable=False),
        sa.Column("amount", sa.DECIMAL(15, 2), nullable=False),
        sa.Column("merchant_name", sa.String(length=255)),
        sa.Column("merchant_category", sa.String(length=100)),
        sa.Column("description", sa.Text()),
        sa.Column("transaction_date", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("balance_after", sa.DECIMAL(15, 2)),
        sa.Column("reference_number", sa.String(length=100)),
        sa.Column("source", sa.Enum("sms", "email", "pdf_upload", "manual", name="transaction_source"), nullable=False),
        sa.Column("raw_message", sa.Text()),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["card_id"], ["cards.id"]),
        sa.ForeignKeyConstraint(["bank_account_id"], ["bank_accounts.id"]),
    )

    op.create_table(
        "sms_emails_raw",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_type", sa.Enum("sms", "email", name="sms_source_type"), nullable=False),
        sa.Column("raw_content", sa.Text(), nullable=False),
        sa.Column("sender", sa.String(length=255)),
        sa.Column("received_at", sa.TIMESTAMP(timezone=True)),
        sa.Column("is_processed", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("parsed_transaction_id", postgresql.UUID(as_uuid=True)),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["parsed_transaction_id"], ["transactions.id"]),
    )

    op.create_table(
        "pdf_uploads",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("file_path", sa.Text(), nullable=False),
        sa.Column("upload_date", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()")),
        sa.Column("bank_name", sa.String(length=100)),
        sa.Column("statement_period_from", sa.Date()),
        sa.Column("statement_period_to", sa.Date()),
        sa.Column("total_transactions_parsed", sa.Integer(), server_default=sa.text("0")),
        sa.Column("status", sa.Enum("pending", "processing", "completed", "failed", name="pdf_status")),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )

    op.create_table(
        "budget_goals",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("category", sa.String(length=100)),
        sa.Column("monthly_limit", sa.DECIMAL(15, 2)),
        sa.Column("current_spent", sa.DECIMAL(15, 2), server_default=sa.text("0")),
        sa.Column("month", sa.Integer()),
        sa.Column("year", sa.Integer()),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )


def downgrade() -> None:
    op.drop_table("budget_goals")
    op.drop_table("pdf_uploads")
    op.drop_table("sms_emails_raw")
    op.drop_table("transactions")
    op.drop_table("cards")
    op.drop_table("bank_accounts")
    op.drop_table("users")
