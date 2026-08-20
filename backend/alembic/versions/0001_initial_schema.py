"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-08-15

"""
from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "rules",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("keyword", sa.String(), nullable=False),
        sa.Column("dm_message", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True)),
    )

    op.create_table(
        "webhook_events",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("event_id", sa.String(), nullable=False),
        sa.Column("event_type", sa.String(), nullable=False),
        sa.Column("post_id", sa.String(), nullable=True),
        sa.Column("comment_id", sa.String(), nullable=True),
        sa.Column("comment_text", sa.String(), nullable=True),
        sa.Column("from_user_id", sa.String(), nullable=True),
        sa.Column("from_username", sa.String(), nullable=True),
        sa.Column("event_sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("received_at", sa.DateTime(timezone=True)),
        sa.Column("processed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("process_note", sa.String(), nullable=True),
    )
    op.create_unique_constraint("uq_webhook_events_event_id", "webhook_events", ["event_id"])
    op.create_index("ix_webhook_events_event_id", "webhook_events", ["event_id"])
    op.create_index("ix_webhook_events_processed", "webhook_events", ["processed"])

    op.create_table(
        "dm_dedup",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("rule_id", sa.String(), nullable=False),
        sa.Column("recipient_user_id", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("rule_id", "recipient_user_id", name="uq_dm_dedup_rule_user"),
    )

    op.create_table(
        "dm_jobs",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("rule_id", sa.String(), nullable=False),
        sa.Column("webhook_event_id", sa.String(), nullable=False),
        sa.Column("comment_id", sa.String(), nullable=True),
        sa.Column("recipient_user_id", sa.String(), nullable=False),
        sa.Column("message", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True)),
        sa.Column("last_error", sa.String(), nullable=True),
        sa.Column("dm_id", sa.String(), nullable=True),
        sa.Column("idempotency_key", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True)),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_dm_jobs_status_next_attempt", "dm_jobs", ["status", "next_attempt_at"])
    op.create_index("ix_dm_jobs_dm_id", "dm_jobs", ["dm_id"])
    op.create_index("ix_dm_jobs_comment_id", "dm_jobs", ["comment_id"])

    op.create_table(
        "delivery_attempts",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("dm_job_id", sa.String(), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("action", sa.String(), nullable=False),
        sa.Column("http_status", sa.Integer(), nullable=True),
        sa.Column("outcome", sa.String(), nullable=False),
        sa.Column("detail", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_delivery_attempts_dm_job_id", "delivery_attempts", ["dm_job_id"])
    op.create_index(
        "ix_delivery_attempts_action_created_at", "delivery_attempts", ["action", "created_at"]
    )

    op.create_table(
        "duplicate_blocks",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("rule_id", sa.String(), nullable=False),
        sa.Column("recipient_user_id", sa.String(), nullable=False),
        sa.Column("webhook_event_id", sa.String(), nullable=False),
        sa.Column("blocked_at", sa.DateTime(timezone=True)),
    )


def downgrade() -> None:
    op.drop_table("duplicate_blocks")
    op.drop_table("delivery_attempts")
    op.drop_table("dm_jobs")
    op.drop_table("dm_dedup")
    op.drop_table("webhook_events")
    op.drop_table("rules")
