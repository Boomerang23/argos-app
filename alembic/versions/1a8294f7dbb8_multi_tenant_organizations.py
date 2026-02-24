"""multi-tenant organizations

Revision ID: 1a8294f7dbb8
Revises: cf1c11251ae1
Create Date: 2026-02-22 23:45:49.586872
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "1a8294f7dbb8"
down_revision: Union[str, Sequence[str], None] = "cf1c11251ae1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1) Table organizations
    op.create_table(
        "organizations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_organizations_id"), "organizations", ["id"], unique=False)
    op.create_index(op.f("ix_organizations_name"), "organizations", ["name"], unique=True)

    # 2) Add organization_id columns + indexes + FKs
    op.add_column("alerts", sa.Column("organization_id", sa.Integer(), nullable=True))
    op.create_index(op.f("ix_alerts_organization_id"), "alerts", ["organization_id"], unique=False)
    op.create_foreign_key(None, "alerts", "organizations", ["organization_id"], ["id"])

    op.add_column("audit_logs", sa.Column("organization_id", sa.Integer(), nullable=True))
    op.create_index(op.f("ix_audit_logs_organization_id"), "audit_logs", ["organization_id"], unique=False)
    op.create_foreign_key(None, "audit_logs", "organizations", ["organization_id"], ["id"])

    op.add_column("clients_v2", sa.Column("organization_id", sa.Integer(), nullable=True))
    op.create_index(op.f("ix_clients_v2_organization_id"), "clients_v2", ["organization_id"], unique=False)
    op.create_foreign_key(None, "clients_v2", "organizations", ["organization_id"], ["id"])

    op.add_column("custom_lists", sa.Column("organization_id", sa.Integer(), nullable=True))
    op.create_index(op.f("ix_custom_lists_organization_id"), "custom_lists", ["organization_id"], unique=False)
    op.create_foreign_key(None, "custom_lists", "organizations", ["organization_id"], ["id"])

    op.add_column("sanctions", sa.Column("organization_id", sa.Integer(), nullable=True))
    op.create_index(op.f("ix_sanctions_organization_id"), "sanctions", ["organization_id"], unique=False)
    op.create_foreign_key(None, "sanctions", "organizations", ["organization_id"], ["id"])

    op.add_column("users", sa.Column("organization_id", sa.Integer(), nullable=True))
    op.create_index(op.f("ix_users_organization_id"), "users", ["organization_id"], unique=False)
    op.create_foreign_key(None, "users", "organizations", ["organization_id"], ["id"])

    # 3) Create default org + backfill
    conn = op.get_bind()

    conn.execute(
        sa.text(
            """
            INSERT INTO organizations (name, created_at)
            SELECT :name, NOW()
            WHERE NOT EXISTS (SELECT 1 FROM organizations WHERE name = :name)
            """
        ),
        {"name": "Default Org"},
    )

    default_org_id = conn.execute(
        sa.text("SELECT id FROM organizations WHERE name = :name"),
        {"name": "Default Org"},
    ).scalar()

    for table in ["users", "clients_v2", "sanctions", "custom_lists", "alerts", "audit_logs"]:
        conn.execute(
            sa.text(f"UPDATE {table} SET organization_id = :oid WHERE organization_id IS NULL"),
            {"oid": default_org_id},
        )

    # 4) Make NOT NULL after backfill
    op.alter_column("users", "organization_id", existing_type=sa.Integer(), nullable=False)
    op.alter_column("clients_v2", "organization_id", existing_type=sa.Integer(), nullable=False)
    op.alter_column("sanctions", "organization_id", existing_type=sa.Integer(), nullable=False)
    op.alter_column("custom_lists", "organization_id", existing_type=sa.Integer(), nullable=False)
    op.alter_column("alerts", "organization_id", existing_type=sa.Integer(), nullable=False)
    op.alter_column("audit_logs", "organization_id", existing_type=sa.Integer(), nullable=False)


def downgrade() -> None:
    # Drop constraints/columns in reverse order
    op.drop_constraint(None, "users", type_="foreignkey")
    op.drop_index(op.f("ix_users_organization_id"), table_name="users")
    op.drop_column("users", "organization_id")

    op.drop_constraint(None, "sanctions", type_="foreignkey")
    op.drop_index(op.f("ix_sanctions_organization_id"), table_name="sanctions")
    op.drop_column("sanctions", "organization_id")

    op.drop_constraint(None, "custom_lists", type_="foreignkey")
    op.drop_index(op.f("ix_custom_lists_organization_id"), table_name="custom_lists")
    op.drop_column("custom_lists", "organization_id")

    op.drop_constraint(None, "clients_v2", type_="foreignkey")
    op.drop_index(op.f("ix_clients_v2_organization_id"), table_name="clients_v2")
    op.drop_column("clients_v2", "organization_id")

    op.drop_constraint(None, "audit_logs", type_="foreignkey")
    op.drop_index(op.f("ix_audit_logs_organization_id"), table_name="audit_logs")
    op.drop_column("audit_logs", "organization_id")

    op.drop_constraint(None, "alerts", type_="foreignkey")
    op.drop_index(op.f("ix_alerts_organization_id"), table_name="alerts")
    op.drop_column("alerts", "organization_id")

    op.drop_index(op.f("ix_organizations_name"), table_name="organizations")
    op.drop_index(op.f("ix_organizations_id"), table_name="organizations")
    op.drop_table("organizations")