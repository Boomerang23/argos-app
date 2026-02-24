"""add organization_id to scan_history

Revision ID: 1441f56a86d9
Revises: 13ae91696f87
Create Date: 2026-02-23 22:22:54.165533

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1441f56a86d9'
down_revision: Union[str, Sequence[str], None] = '13ae91696f87'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.add_column("scan_history", sa.Column("organization_id", sa.Integer(), nullable=True))
    op.create_index(op.f("ix_scan_history_organization_id"), "scan_history", ["organization_id"], unique=False)
    op.create_foreign_key(None, "scan_history", "organizations", ["organization_id"], ["id"])

def downgrade() -> None:
    op.drop_constraint(None, "scan_history", type_="foreignkey")
    op.drop_index(op.f("ix_scan_history_organization_id"), table_name="scan_history")
    op.drop_column("scan_history", "organization_id")