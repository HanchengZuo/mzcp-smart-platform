"""add task packages for ordered multi-form surveys

Revision ID: 8b7c6d5e4f3a
Revises: 3f4a2b1c9d8e
Create Date: 2026-06-03 20:20:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "8b7c6d5e4f3a"
down_revision = "3f4a2b1c9d8e"
branch_labels = None
depends_on = None


def reset_postgres_sequence(table_name):
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    op.execute(
        sa.text(
            f"""
            SELECT setval(
                pg_get_serial_sequence('{table_name}', 'id'),
                COALESCE((SELECT MAX(id) FROM {table_name}), 1),
                (SELECT COUNT(*) FROM {table_name}) > 0
            )
            """
        )
    )


def upgrade():
    op.create_table(
        "evaluation_tasks",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("unit_id", sa.Integer(), nullable=False),
        sa.Column("group_id", sa.Integer(), nullable=False),
        sa.Column("period_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["group_id"], ["inspection_groups.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["period_id"], ["period_tasks.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["unit_id"], ["units.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )

    with op.batch_alter_table("evaluation_forms", schema=None) as batch_op:
        batch_op.add_column(sa.Column("task_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("form_order", sa.Integer(), nullable=False, server_default="1"))
        batch_op.create_foreign_key(
            "fk_evaluation_forms_task_id_evaluation_tasks",
            "evaluation_tasks",
            ["task_id"],
            ["id"],
            ondelete="CASCADE",
        )

    with op.batch_alter_table("survey_links", schema=None) as batch_op:
        batch_op.add_column(sa.Column("task_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_survey_links_task_id_evaluation_tasks",
            "evaluation_tasks",
            ["task_id"],
            ["id"],
            ondelete="CASCADE",
        )
        batch_op.create_unique_constraint("uq_task_level", ["task_id", "level_id"])

    op.execute(
        """
        INSERT INTO evaluation_tasks (
            id, title, status, unit_id, group_id, period_id, created_at, updated_at
        )
        SELECT id, title, status, unit_id, group_id, period_id, created_at, updated_at
        FROM evaluation_forms
        """
    )
    op.execute("UPDATE evaluation_forms SET task_id = id, form_order = 1")
    op.execute("UPDATE survey_links SET task_id = form_id")
    reset_postgres_sequence("evaluation_tasks")


def downgrade():
    with op.batch_alter_table("survey_links", schema=None) as batch_op:
        batch_op.drop_constraint("uq_task_level", type_="unique")
        batch_op.drop_constraint(
            "fk_survey_links_task_id_evaluation_tasks",
            type_="foreignkey",
        )
        batch_op.drop_column("task_id")

    with op.batch_alter_table("evaluation_forms", schema=None) as batch_op:
        batch_op.drop_constraint(
            "fk_evaluation_forms_task_id_evaluation_tasks",
            type_="foreignkey",
        )
        batch_op.drop_column("form_order")
        batch_op.drop_column("task_id")

    op.drop_table("evaluation_tasks")
