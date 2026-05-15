"""cleanup user roles to admin lead manager

Revision ID: af46c2a94e35
Revises: 086ea9c3161e
Create Date: 2026-05-15 17:32:57.866657

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'af46c2a94e35'
down_revision: Union[str, None] = '086ea9c3161e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Migrate data for removed/renamed roles (safety net for any prod rows)
    op.execute("UPDATE users SET role = 'admin'   WHERE role = 'project_manager'")
    op.execute("UPDATE users SET role = 'lead'    WHERE role = 'lead_manager'")
    op.execute("UPDATE users SET role = 'manager' WHERE role = 'analyst'")

    # 2. Detach column from the native enum type (→ plain VARCHAR)
    op.execute("ALTER TABLE users ALTER COLUMN role TYPE VARCHAR(50) USING role::VARCHAR")

    # 3. Drop the old native enum type
    op.execute("DROP TYPE userrole")

    # 4. Create the new native enum type with 3 values
    op.execute("CREATE TYPE userrole AS ENUM ('admin', 'lead', 'manager')")

    # 5. Restore the column to the new enum type
    op.execute("ALTER TABLE users ALTER COLUMN role TYPE userrole USING role::userrole")


def downgrade() -> None:
    # 1. Detach column from the new enum type (→ plain VARCHAR)
    op.execute("ALTER TABLE users ALTER COLUMN role TYPE VARCHAR(50) USING role::VARCHAR")

    # 2. Drop the new enum type
    op.execute("DROP TYPE userrole")

    # 3. Rename lead → lead_manager before restoring old type
    op.execute("UPDATE users SET role = 'lead_manager' WHERE role = 'lead'")

    # 4. Откат: lead → lead_manager. project_manager/analyst остаются как admin/manager
    #    (точный обратный мапинг невозможен, восстанавливать руками при необходимости).
    op.execute(
        "CREATE TYPE userrole AS ENUM ('admin', 'project_manager', 'lead_manager', 'analyst', 'manager')"
    )

    # 5. Restore the column to the old enum type
    op.execute("ALTER TABLE users ALTER COLUMN role TYPE userrole USING role::userrole")
