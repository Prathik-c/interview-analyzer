from backend.app.db.models.user import UserDB
from backend.app.db.models.interview import AssessmentSessionDB
from backend.app.db.models.resume import ResumeDB
from backend.app.db.models.question import QuestionDB
from backend.app.db.models.submission import SubmissionDB
from backend.app.db.models.recording import RecordingDB
from backend.app.db.models.speech import SpeechAnalysisDB
from backend.app.db.models.video import VideoAnalysisDB
from backend.app.db.models.evaluation import NLPEvaluationDB, FinalEvaluationDB

__all__ = [
    "UserDB",
    "AssessmentSessionDB",
    "ResumeDB",
    "QuestionDB",
    "SubmissionDB",
    "RecordingDB",
    "SpeechAnalysisDB",
    "VideoAnalysisDB",
    "NLPEvaluationDB",
    "FinalEvaluationDB"
]
