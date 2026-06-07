"""add chatbot tables

Revision ID: 0005_chatbot_tables
Revises: 0004_bank_email_enforce
Create Date: 2026-04-24 00:00:00.000000

"""

import uuid

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from app.data.chatbot_seed import CHATBOT_TEMPLATES


revision = "0005_chatbot_tables"
down_revision = "0004_bank_email_enforce"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM pg_type t
                JOIN pg_namespace n ON n.oid = t.typnamespace
                WHERE t.typname = 'chatbot_message_role' AND n.nspname = current_schema()
            ) THEN
                CREATE TYPE chatbot_message_role AS ENUM ('bot', 'user');
            END IF;
        END $$;
        """
    )

    role_enum = postgresql.ENUM("bot", "user", name="chatbot_message_role", create_type=False)

    op.create_table(
        "chatbot_question_templates",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("template_text", sa.Text(), nullable=False),
        sa.Column("category", sa.String(length=50), nullable=False),
        sa.Column("data_query_type", sa.String(length=100), nullable=False),
        sa.Column("requires_placeholder", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("placeholder_source", sa.String(length=50), server_default=sa.text("'none'"), nullable=False),
        sa.Column("placeholder_field", sa.String(length=50), nullable=True),
        sa.Column("keywords", sa.Text(), nullable=True),
        sa.Column("display_order", sa.Integer(), nullable=False),
        sa.Column("follow_up_categories", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    op.create_table(
        "chatbot_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("started_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("last_active", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("message_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )

    op.create_table(
        "chatbot_messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role", role_enum, nullable=False),
        sa.Column("message_text", sa.Text(), nullable=False),
        sa.Column("matched_template_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("resolved_question", sa.Text(), nullable=True),
        sa.Column("data_used", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["chatbot_sessions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["matched_template_id"], ["chatbot_question_templates.id"]),
    )

    templates_table = sa.table(
        "chatbot_question_templates",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("template_text", sa.Text()),
        sa.column("category", sa.String(length=50)),
        sa.column("data_query_type", sa.String(length=100)),
        sa.column("requires_placeholder", sa.Boolean()),
        sa.column("placeholder_source", sa.String(length=50)),
        sa.column("placeholder_field", sa.String(length=50)),
        sa.column("keywords", sa.Text()),
        sa.column("display_order", sa.Integer()),
        sa.column("follow_up_categories", sa.Text()),
        sa.column("is_active", sa.Boolean()),
    )

    rows = []
    for template in CHATBOT_TEMPLATES:
        rows.append(
            {
                "id": uuid.uuid4(),
                "template_text": template["template_text"],
                "category": template["category"],
                "data_query_type": template["data_query_type"],
                "requires_placeholder": template["requires_placeholder"],
                "placeholder_source": template["placeholder_source"],
                "placeholder_field": template.get("placeholder_field"),
                "keywords": template.get("keywords"),
                "display_order": template["display_order"],
                "follow_up_categories": template.get("follow_up_categories"),
                "is_active": True,
            }
        )

    op.bulk_insert(templates_table, rows)


def downgrade() -> None:
    op.drop_table("chatbot_messages")
    op.drop_table("chatbot_sessions")
    op.drop_table("chatbot_question_templates")

    op.execute("DROP TYPE IF EXISTS chatbot_message_role")
