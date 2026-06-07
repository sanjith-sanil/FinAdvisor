"""add card benefits table and extended card fields

Revision ID: 0006_card_benefits
Revises: 0005_chatbot_tables
Create Date: 2026-04-25 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0006_card_benefits"
down_revision = "0005_chatbot_tables"
branch_labels = None
depends_on = None


benefit_category_enum = sa.Enum(
    "cashback",
    "rewards",
    "lounge",
    "insurance",
    "fuel",
    "dining",
    "shopping",
    "travel",
    "emi",
    "other",
    name="benefit_category",
    native_enum=False,
)


def upgrade() -> None:
    op.add_column("cards", sa.Column("annual_fee", sa.DECIMAL(10, 2), nullable=False, server_default=sa.text("0")))
    op.add_column("cards", sa.Column("joining_fee", sa.DECIMAL(10, 2), nullable=False, server_default=sa.text("0")))
    op.add_column("cards", sa.Column("reward_points_balance", sa.Integer(), nullable=False, server_default=sa.text("0")))
    op.add_column("cards", sa.Column("reward_points_rate", sa.String(length=100), nullable=True))
    op.add_column("cards", sa.Column("cashback_rate", sa.String(length=100), nullable=True))
    op.add_column("cards", sa.Column("lounge_access", sa.Boolean(), nullable=False, server_default=sa.text("false")))
    op.add_column(
        "cards",
        sa.Column("lounge_visits_per_quarter", sa.Integer(), nullable=False, server_default=sa.text("0")),
    )
    op.add_column(
        "cards",
        sa.Column("fuel_surcharge_waiver", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column("cards", sa.Column("credit_score_impact", sa.Integer(), nullable=False, server_default=sa.text("0")))
    op.add_column("cards", sa.Column("notes", sa.Text(), nullable=True))

    op.create_table(
        "card_benefits",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("card_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("benefit_category", benefit_category_enum, nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("value", sa.String(length=100), nullable=True),
        sa.Column("conditions", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["card_id"], ["cards.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_card_benefits_card_id", "card_benefits", ["card_id"])
    op.create_index("ix_card_benefits_user_id", "card_benefits", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_card_benefits_user_id", table_name="card_benefits")
    op.drop_index("ix_card_benefits_card_id", table_name="card_benefits")
    op.drop_table("card_benefits")

    op.drop_column("cards", "notes")
    op.drop_column("cards", "credit_score_impact")
    op.drop_column("cards", "fuel_surcharge_waiver")
    op.drop_column("cards", "lounge_visits_per_quarter")
    op.drop_column("cards", "lounge_access")
    op.drop_column("cards", "cashback_rate")
    op.drop_column("cards", "reward_points_rate")
    op.drop_column("cards", "reward_points_balance")
    op.drop_column("cards", "joining_fee")
    op.drop_column("cards", "annual_fee")
