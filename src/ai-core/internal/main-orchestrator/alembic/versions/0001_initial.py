"""Initial orchestrator state.

Revision ID: 0001
Revises:
"""

from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "jobs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("idempotency_key_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("request_encrypted", sa.Text()),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("stage", sa.String(24), nullable=False),
        sa.Column("requested_image_count", sa.Integer(), nullable=False),
        sa.Column("accepted_image_count", sa.Integer(), nullable=False),
        sa.Column("failed_attempt_count", sa.Integer(), nullable=False),
        sa.Column("current_index", sa.Integer(), nullable=False),
        sa.Column("input_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deadline_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("results_available_until", sa.DateTime(timezone=True)),
        sa.Column("result_delivery_status", sa.String(16)),
        sa.Column("error_code", sa.String(64)),
        sa.Column("error_message", sa.String(256)),
        sa.Column("error_reasons", sa.JSON()),
        sa.Column("face_artifact_id", sa.String(40), nullable=False),
        sa.Column("body_artifact_id", sa.String(40), nullable=False),
        sa.Column("face_imported", sa.Boolean(), nullable=False),
        sa.Column("body_imported", sa.Boolean(), nullable=False),
        sa.Column("color_type", sa.String(16)),
        sa.Column("import_attempt", sa.Integer(), nullable=False),
        sa.Column("import_next_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "image_slots",
        sa.Column("job_id", sa.String(36), sa.ForeignKey("jobs.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("order_index", sa.Integer(), primary_key=True),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("outfit_encrypted", sa.Text()),
        sa.Column("outfit_hash", sa.String(64)),
        sa.Column("candidate_count", sa.Integer(), nullable=False),
        sa.Column("candidate_artifact_id", sa.String(40)),
        sa.Column("accepted_artifact_id", sa.String(40)),
        sa.Column("stage_attempt", sa.Integer(), nullable=False),
    )
    op.create_table(
        "artifacts",
        sa.Column("id", sa.String(40), primary_key=True),
        sa.Column("job_id", sa.String(36), sa.ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("order_index", sa.Integer()),
        sa.Column("checksum_sha256", sa.String(71)),
        sa.Column("size_bytes", sa.BigInteger()),
        sa.Column("format", sa.String(16)),
        sa.Column("width", sa.Integer()),
        sa.Column("height", sa.Integer()),
        sa.Column("result_metadata", sa.JSON()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_artifacts_job_id", "artifacts", ["job_id"])
    op.create_table(
        "commands",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("job_id", sa.String(36), sa.ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("stage", sa.String(24), nullable=False),
        sa.Column("attempt", sa.Integer(), nullable=False),
        sa.Column("order_index", sa.Integer()),
        sa.Column("payload_encrypted", sa.Text(), nullable=False),
        sa.Column("result_encrypted", sa.Text()),
        sa.Column("error_code", sa.String(64)),
        sa.Column("error_retryable", sa.Boolean()),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("next_send_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True)),
        sa.Column("sent_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_commands_job_id", "commands", ["job_id"])
    op.create_index("ix_commands_status", "commands", ["status"])
    op.create_table(
        "outfit_reservations",
        sa.Column("job_id", sa.String(36), sa.ForeignKey("jobs.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("outfit_hash", sa.String(64), primary_key=True),
    )
    op.create_table(
        "events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("job_id", sa.String(36), sa.ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("delivery_status", sa.String(16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("job_id", "sequence", name="uq_event_sequence"),
    )
    op.create_index("ix_events_job_id", "events", ["job_id"])
    op.create_table(
        "cleanup_requests",
        sa.Column("artifact_id", sa.String(40), sa.ForeignKey("artifacts.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("job_id", sa.String(36), sa.ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("done", sa.Boolean(), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("next_try_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    for table in ("cleanup_requests", "events", "outfit_reservations", "commands", "artifacts", "image_slots", "jobs"):
        op.drop_table(table)
