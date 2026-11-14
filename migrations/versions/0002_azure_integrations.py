"""Persist Azure extraction, language, safety, and F0 usage data."""

import sqlalchemy as sa
from alembic import op

revision = "0002_azure_integrations"
down_revision = "0001_platform_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("contract_versions", sa.Column("layout_data", sa.JSON(), nullable=True))
    op.add_column("contract_versions", sa.Column("language_insights", sa.JSON(), nullable=True))
    op.add_column("contract_versions", sa.Column("safety_findings", sa.JSON(), nullable=True))
    op.create_table(
        "contract_translations",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "version_id",
            sa.String(length=36),
            sa.ForeignKey("contract_versions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("source_language", sa.String(length=20), nullable=False),
        sa.Column("target_language", sa.String(length=20), nullable=False),
        sa.Column("translated_text", sa.Text(), nullable=False),
        sa.Column("scope", sa.String(length=30), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_translations_version_created",
        "contract_translations",
        ["version_id", "created_at"],
    )
    op.create_table(
        "azure_usage_counters",
        sa.Column("service", sa.String(length=40), primary_key=True),
        sa.Column("period", sa.String(length=7), primary_key=True),
        sa.Column("units", sa.Integer(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("azure_usage_counters")
    op.drop_index("ix_translations_version_created", table_name="contract_translations")
    op.drop_table("contract_translations")
    op.drop_column("contract_versions", "safety_findings")
    op.drop_column("contract_versions", "language_insights")
    op.drop_column("contract_versions", "layout_data")
