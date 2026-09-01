# Import all the models, so that Base has them before being imported by Alembic
from backend.app.db.session import Base
from backend.app.db.models import (
    UserDB, AssessmentSessionDB, ResumeDB, QuestionDB, SubmissionDB,
    RecordingDB, SpeechAnalysisDB, VideoAnalysisDB, NLPEvaluationDB, FinalEvaluationDB
)
