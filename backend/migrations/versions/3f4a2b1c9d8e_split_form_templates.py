"""split form templates from launched tasks

Revision ID: 3f4a2b1c9d8e
Revises: eabff908f664
Create Date: 2026-06-03 10:40:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "3f4a2b1c9d8e"
down_revision = "eabff908f664"
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
        "form_templates",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=160), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("show_intro", sa.Boolean(), nullable=False),
        sa.Column("intro_text", sa.Text(), nullable=False),
        sa.Column("intro_seconds", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "template_options",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("template_id", sa.Integer(), nullable=False),
        sa.Column("label", sa.String(length=80), nullable=False),
        sa.Column("value", sa.String(length=80), nullable=False),
        sa.Column("score_weight", sa.Integer(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["template_id"], ["form_templates.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("template_id", "value", name="uq_template_option_value"),
    )
    op.create_table(
        "template_sections",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("template_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=160), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["template_id"], ["form_templates.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "template_items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("template_id", sa.Integer(), nullable=False),
        sa.Column("section_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=240), nullable=False),
        sa.Column("item_type", sa.String(length=20), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["section_id"], ["template_sections.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["template_id"], ["form_templates.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    with op.batch_alter_table("evaluation_forms", schema=None) as batch_op:
        batch_op.add_column(sa.Column("template_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_evaluation_forms_template_id_form_templates",
            "form_templates",
            ["template_id"],
            ["id"],
            ondelete="SET NULL",
        )

    op.execute(
        """
        INSERT INTO form_templates (
            id, title, description, show_intro, intro_text, intro_seconds, created_at, updated_at
        )
        SELECT id, title, description, show_intro, intro_text, intro_seconds, created_at, updated_at
        FROM evaluation_forms
        """
    )
    op.execute(
        """
        INSERT INTO template_options (
            id, template_id, label, value, score_weight, sort_order, created_at, updated_at
        )
        SELECT id, form_id, label, value, score_weight, sort_order, created_at, updated_at
        FROM form_options
        """
    )
    op.execute(
        """
        INSERT INTO template_sections (
            id, template_id, title, sort_order, created_at, updated_at
        )
        SELECT id, form_id, title, sort_order, created_at, updated_at
        FROM form_sections
        """
    )
    op.execute(
        """
        INSERT INTO template_items (
            id, template_id, section_id, title, item_type, sort_order, created_at, updated_at
        )
        SELECT id, form_id, section_id, title, item_type, sort_order, created_at, updated_at
        FROM form_items
        """
    )
    op.execute("UPDATE evaluation_forms SET template_id = id")

    for table_name in (
        "form_templates",
        "template_options",
        "template_sections",
        "template_items",
    ):
        reset_postgres_sequence(table_name)


def downgrade():
    with op.batch_alter_table("evaluation_forms", schema=None) as batch_op:
        batch_op.drop_constraint(
            "fk_evaluation_forms_template_id_form_templates",
            type_="foreignkey",
        )
        batch_op.drop_column("template_id")

    op.drop_table("template_items")
    op.drop_table("template_sections")
    op.drop_table("template_options")
    op.drop_table("form_templates")
