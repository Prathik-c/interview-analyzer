from enum import Enum

class AssessmentType(str, Enum):
    INTERVIEW = "INTERVIEW"
    DSA = "DSA"
    APTITUDE = "APTITUDE"
    TECHNICAL_QUIZ = "TECHNICAL_QUIZ"
    ROLE_SPECIFIC = "ROLE_SPECIFIC"

class ProcessingStatus(str, Enum):
    PENDING = "PENDING"
    RECORDING_UPLOADED = "RECORDING_UPLOADED"
    TRANSCRIBING = "TRANSCRIBING"
    ANALYSING_SPEECH = "ANALYSING_SPEECH"
    ANALYSING_VIDEO = "ANALYSING_VIDEO"
    EVALUATING_NLP = "EVALUATING_NLP"
    GENERATING_NEXT_QUESTION = "GENERATING_NEXT_QUESTION"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"

JOB_ROLES = [
    "Software Engineer",
    "Frontend Developer",
    "Backend Developer",
    "Full Stack Developer",
    "Mobile App Developer",
    "Java Developer",
    "Python Developer",
    "C++ Developer",
    "Machine Learning Engineer",
    "Machine Learning Researcher",
    "AI Engineer",
    "Deep Learning Engineer",
    "Computer Vision Engineer",
    "NLP Engineer",
    "Generative AI Engineer",
    "MLOps Engineer",
    "Data Scientist",
    "Data Analyst",
    "Data Engineer",
    "Business Intelligence Analyst",
    "DevOps Engineer",
    "Cloud Engineer",
    "Cloud Architect",
    "Cybersecurity Engineer",
    "Product Manager",
    "Project Manager",
    "UI/UX Designer",
    "QA Engineer",
    "Test Engineer"
]

DEFAULT_JOB_ROLES = [
    "Software Engineer",
    "Machine Learning Engineer",
    "Data Scientist",
    "Frontend Developer",
    "Data Analyst"
]

FILLER_WORDS = [
    "um", "uh", "like", "actually", "basically", "you know",
    "i mean", "sort of", "kind of", "right", "honestly", "literally"
]

# Speech pacing standards
OPTIMAL_WPM_MIN = 120
OPTIMAL_WPM_MAX = 170
