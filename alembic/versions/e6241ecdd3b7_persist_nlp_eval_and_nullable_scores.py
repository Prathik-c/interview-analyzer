"""persist_nlp_eval_and_nullable_scores

Revision ID: e6241ecdd3b7
Revises: '22d7c252225c'
Create Date: 2026-10-13 10:30:34.944523

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e6241ecdd3b7'
down_revision: Union[str, None] = '22d7c252225c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('answers', schema=None) as batch_op:
        batch_op.add_column(sa.Column('nlp_evaluation', sa.JSON(), nullable=True))
        batch_op.alter_column('transcription_status',
                              existing_type=sa.String(length=50),
                              server_default='no_recording')

    with op.batch_alter_table('final_evaluations', schema=None) as batch_op:
        batch_op.alter_column('overall_score', existing_type=sa.Integer(), nullable=True)
        batch_op.alter_column('nlp_score', existing_type=sa.Integer(), nullable=True)
        batch_op.alter_column('speech_score', existing_type=sa.Integer(), nullable=True)
        batch_op.alter_column('video_score', existing_type=sa.Integer(), nullable=True)


def downgrade() -> None:
    with op.batch_alter_table('final_evaluations', schema=None) as batch_op:
        batch_op.alter_column('overall_score', existing_type=sa.Integer(), nullable=False)
        batch_op.alter_column('nlp_score', existing_type=sa.Integer(), nullable=False)
        batch_op.alter_column('speech_score', existing_type=sa.Integer(), nullable=False)
        batch_op.alter_column('video_score', existing_type=sa.Integer(), nullable=False)

    with op.batch_alter_table('answers', schema=None) as batch_op:
        batch_op.alter_column('transcription_status',
                              existing_type=sa.String(length=50),
                              server_default='COMPLETED')
        batch_op.drop_column('nlp_evaluation')

