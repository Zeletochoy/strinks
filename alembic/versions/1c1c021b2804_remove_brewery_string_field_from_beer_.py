"""Remove brewery string field from Beer table

Revision ID: 1c1c021b2804
Revises: adf73c371c58
Create Date: 2025-08-17 14:58:44.720394

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "1c1c021b2804"
down_revision: str | Sequence[str] | None = "adf73c371c58"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # Drop the deprecated brewery string column
    with op.batch_alter_table("beers", schema=None) as batch_op:
        batch_op.drop_column("brewery")


def downgrade() -> None:
    """Downgrade schema."""
    # Re-add the brewery string column
    with op.batch_alter_table("beers", schema=None) as batch_op:
        batch_op.add_column(sa.Column("brewery", sa.String(), nullable=False))
