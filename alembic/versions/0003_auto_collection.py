"""add email and sms collection tables

Revision ID: 0003_auto_collection
Revises: 0002_add_user_password_hash
Create Date: 2026-04-20 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0003_auto_collection"
down_revision = "0002_add_user_password_hash"
branch_labels = None
depends_on = None


def upgrade() -> None:
    email_auth_type = postgresql.ENUM("imap_password", "oauth", name="email_auth_type", create_type=False)
    collection_log_type = postgresql.ENUM(
        "email_check", "sms_received", "error", name="collection_log_type", create_type=False
    )
    collection_source = postgresql.ENUM(
        "imap", "oauth", "sms_webhook", "manual", name="collection_source", create_type=False
    )

    email_auth_type.create(op.get_bind(), checkfirst=True)
    collection_log_type.create(op.get_bind(), checkfirst=True)
    collection_source.create(op.get_bind(), checkfirst=True)

    op.add_column("users", sa.Column("phone_number", sa.String(length=15)))
    op.add_column("users", sa.Column("sms_webhook_key", sa.String(length=64), unique=True))
    op.add_column("users", sa.Column("sms_configured", sa.Boolean(), server_default=sa.text("false")))
    op.add_column("users", sa.Column("email_collection_configured", sa.Boolean(), server_default=sa.text("false")))
    op.add_column("users", sa.Column("registration_step", sa.Integer(), server_default=sa.text("1")))

    op.add_column("sms_emails_raw", sa.Column("subject", sa.String(length=255)))
    op.add_column("sms_emails_raw", sa.Column("message_id", sa.String(length=255)))

    op.create_table(
        "email_configs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("email_address", sa.String(length=255), nullable=False),
        sa.Column("auth_type", email_auth_type, nullable=False),
        sa.Column("password_encrypted", sa.Text()),
        sa.Column("imap_server", sa.String(length=255)),
        sa.Column("imap_port", sa.Integer(), server_default="993"),
        sa.Column("oauth_refresh_token_encrypted", sa.Text()),
        sa.Column("oauth_access_token_encrypted", sa.Text()),
        sa.Column("oauth_token_expiry", sa.TIMESTAMP(timezone=True)),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")),
        sa.Column("last_checked", sa.TIMESTAMP(timezone=True)),
        sa.Column("last_error", sa.Text()),
        sa.Column("emails_processed_total", sa.Integer(), server_default=sa.text("0")),
        sa.Column("transactions_found_total", sa.Integer(), server_default=sa.text("0")),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()")),
    )

    op.create_table(
        "collection_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("log_type", collection_log_type, nullable=False),
        sa.Column("source", collection_source, nullable=False),
        sa.Column("emails_checked", sa.Integer(), server_default=sa.text("0")),
        sa.Column("transactions_found", sa.Integer(), server_default=sa.text("0")),
        sa.Column("error_message", sa.String(length=500)),
        sa.Column("duration_ms", sa.Integer()),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()")),
    )


def downgrade() -> None:
    op.drop_table("collection_logs")
    op.drop_table("email_configs")

    op.drop_column("sms_emails_raw", "message_id")
    op.drop_column("sms_emails_raw", "subject")

    op.drop_column("users", "registration_step")
    op.drop_column("users", "email_collection_configured")
    op.drop_column("users", "sms_configured")
    op.drop_column("users", "sms_webhook_key")
    op.drop_column("users", "phone_number")

    op.execute("DROP TYPE IF EXISTS collection_source")
    op.execute("DROP TYPE IF EXISTS collection_log_type")
    op.execute("DROP TYPE IF EXISTS email_auth_type")
