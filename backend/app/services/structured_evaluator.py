import re
import math
import logging
from typing import Dict, Any, List, Optional, Set
from backend.app.schemas.question import QuestionItem

logger = logging.getLogger("structured_evaluator")

# Standard English stop words
STOP_WORDS: Set[str] = {
    "a", "about", "above", "after", "again", "against", "all", "am", "an", "and",
    "any", "are", "aren't", "as", "at", "be", "because", "been", "before", "being",
    "below", "between", "both", "but", "by", "can", "can't", "cannot", "could",
    "couldn't", "did", "didn't", "do", "does", "doesn't", "doing", "don't", "down",
    "during", "each", "few", "for", "from", "further", "had", "hadn't", "has",
    "hasn't", "have", "haven't", "having", "he", "he'd", "he'll", "he's", "her",
    "here", "here's", "hers", "herself", "him", "himself", "his", "how", "how's",
    "i", "i'd", "i'll", "i'm", "i've", "if", "in", "into", "is", "isn't", "it",
    "it's", "its", "itself", "let's", "me", "more", "most", "mustn't", "my",
    "myself", "no", "nor", "not", "of", "off", "on", "once", "only", "or", "other",
    "ought", "our", "ours", "ourselves", "out", "over", "own", "same", "shan't",
    "she", "she'd", "she'll", "she's", "should", "shouldn't", "so", "some", "such",
    "than", "that", "that's", "the", "their", "theirs", "them", "themselves",
    "then", "there", "there's", "these", "they", "they'd", "they'll", "they're",
    "they've", "this", "those", "through", "to", "too", "under", "until", "up",
    "very", "was", "wasn't", "we", "we'd", "we'll", "we're", "we've", "were",
    "weren't", "what", "what's", "when", "when's", "where", "where's", "which",
    "while", "who", "who's", "whom", "why", "why's", "with", "won't", "would",
    "wouldn't", "you", "you'd", "you'll", "you're", "you've", "your", "yours",
    "yourself", "yourselves"
}

# Common evasive or non-committal phrases
EVASION_PATTERNS = [
    r"\bi\s+(?:don't|do\s+not)\s+know\b",
    r"\bno\s+idea\b",
    r"\bnot\s+sure\b",
    r"\bcan't\s+remember\b",
    r"\bcannot\s+recall\b",
    r"\bskip\s+(?:this|question)\b",
    r"\bpass\s+on\s+this\b",
    r"\bi\s+have\s+no\s+clue\b",
    r"\bnever\s+heard\s+of\b",
]

# Uncertainty indicators suggesting interviewer follow-up is beneficial
UNCERTAINTY_PATTERNS = [
    r"\bi\s+think\s+maybe\b",
    r"\bi\s+guess\b",
    r"\bnot\s+100%\s+sure\b",
    r"\bnot\s+really\s+sure\b",
    r"\bcould\s+be\s+wrong\b",
    r"\bi\s+might\s+be\s+mistaken\b",
    r"\bsomething\s+like\s+that\b",
    r"\bprobably\s+not\s+certain\b",
]

# Curated technical misconception patterns across common computer science domains
MISCONCEPTION_RULES = [
    # Threads vs Processes
    {
        "id": "thread_separate_memory",
        "description": "Claiming threads do not share memory or have isolated address spaces",
        "pattern": r"\bthreads?\s+(?:always\s+)?(?:have|has)\s+(?:their|its)?\s*(?:own\s+)?(?:completely\s+)?(?:separate|isolated|independent)\s+memory\b",
        "keywords": ["thread", "process", "memory"]
    },
    {
        "id": "threads_do_not_share_memory",
        "description": "Asserting threads do not share memory or resources",
        "pattern": r"\bthreads?\s+(?:do\s+not|don't|never|cannot|can't)\s+share\s+(?:memory|resources)\b",
        "keywords": ["thread", "memory", "resource"]
    },
    {
        "id": "process_shared_memory_default",
        "description": "Claiming processes share memory space by default without IPC",
        "pattern": r"\bprocesses\s+(?:automatically|by\s+default)\s+share\s+(?:the\s+same\s+)?memory\s+space\b",
        "keywords": ["process", "memory"]
    },
    # HTTP / REST
    {
        "id": "get_request_modifies_data",
        "description": "Claiming GET requests should mutate or delete server state",
        "pattern": r"\bget\s+requests?\s+(?:are\s+used\s+to\s+|should\s+)?(?:modify|update|delete|mutate)\s+(?:data|resources?|database)\b",
        "keywords": ["get", "http", "rest"]
    },
    {
        "id": "http_is_stateful",
        "description": "Claiming standard HTTP protocol is stateful",
        "pattern": r"\bhttp\s+(?:is|has\s+a)\s+stateful\s+protocol\b",
        "keywords": ["http", "protocol"]
    },
    # Databases / SQL
    {
        "id": "primary_key_null",
        "description": "Claiming primary keys can store null values",
        "pattern": r"\bprimary\s+keys?\s+(?:can|may)\s+(?:contain|be|have)\s+null\b",
        "keywords": ["primary", "key", "null"]
    },
    {
        "id": "indexing_speeds_writes",
        "description": "Claiming database indexes speed up insert/write operations",
        "pattern": r"\bindexes?\s+(?:speeds?\s+up|accelerates?|improves?)\s+(?:write|insert|update)\s+performance\b",
        "keywords": ["index", "write", "database"]
    },
    {
        "id": "sql_is_nosql",
        "description": "Claiming SQL is non-relational or schema-less by nature",
        "pattern": r"\bsql\s+is\s+(?:a\s+)?(?:non-?relational|schema-?less)\s+database\b",
        "keywords": ["sql", "database"]
    },
    # Algorithms / Data Structures
    {
        "id": "binary_search_unsorted",
        "description": "Claiming binary search works on unsorted collections",
        "pattern": r"\bbinary\s+search\s+(?:works?\s+on|requires?\s+an?)\s+unsorted\b",
        "keywords": ["binary", "search", "unsorted"]
    },
    {
        "id": "hashmap_linear_average",
        "description": "Claiming hash map average lookup is O(N)",
        "pattern": r"\bhash\s*maps?\s+(?:average\s+lookup|average\s+time)\s+is\s+o\(?n\)?\b",
        "keywords": ["hashmap", "hash", "lookup"]
    },
    {
        "id": "array_random_access_linear",
        "description": "Claiming array index random access is O(N)",
        "pattern": r"\barray\s+(?:random\s+access|index\s+lookup)\s+is\s+o\(?n\)?\b",
        "keywords": ["array", "access"]
    },
    # Concurrency / Synchronization
    {
        "id": "mutex_allows_concurrent_writes",
        "description": "Claiming a mutex allows multiple concurrent writing threads",
        "pattern": r"\bmutex\s+allows?\s+multiple\s+(?:concurrent\s+)?(?:writers?|writes?)\b",
        "keywords": ["mutex", "concurrent"]
    },
    # Memory Management
    {
        "id": "python_machine_code",
        "description": "Claiming standard Python compiles directly to native machine code binaries",
        "pattern": r"\bpython\s+(?:is\s+compiled\s+directly\s+to\s+native\s+machine\s+code)\b",
        "keywords": ["python", "machine", "code"]
    }
]

# Core conceptual terms mapping by topic/domain for semantic verification
TOPIC_CONCEPT_MAP: Dict[str, List[str]] = {
    "process": ["thread", "memory", "space", "execution", "share", "cpu", "stack", "heap", "isolation", "resource", "ipc", "overhead"],
    "thread": ["process", "memory", "space", "execution", "share", "stack", "lightweight", "concurrency", "cpu", "overhead"],
    "database": ["query", "table", "index", "acid", "transaction", "schema", "relation", "consistency", "primary", "foreign", "normalization"],
    "sql": ["query", "table", "join", "select", "index", "schema", "acid", "relational", "primary", "key"],
    "api": ["endpoint", "request", "response", "rest", "http", "status", "json", "payload", "authentication", "client", "server"],
    "rest": ["http", "get", "post", "put", "delete", "stateless", "resource", "endpoint", "status", "json", "idempotent"],
    "git": ["commit", "branch", "merge", "repository", "remote", "pull", "push", "conflict", "rebase", "checkout"],
    "docker": ["container", "image", "dockerfile", "virtualization", "isolation", "host", "port", "volume", "compose"],
    "data structure": ["array", "list", "stack", "queue", "tree", "graph", "hash", "node", "complexity", "pointer"],
    "security": ["authentication", "authorization", "token", "encryption", "hash", "jwt", "vulnerability", "permission"],
    "machine learning": ["model", "training", "weights", "features", "dataset", "loss", "gradient", "evaluation", "accuracy", "overfitting"],
    "python": ["function", "class", "module", "object", "interpreter", "list", "dict", "generator", "decorator", "gil"],
    "backend": ["server", "api", "database", "service", "request", "route", "handler", "middleware", "performance", "scaling"],
    "frontend": ["component", "dom", "state", "props", "ui", "render", "event", "css", "javascript", "browser"]
}


class LocalStructuredEvaluator:
    """
    Zero-Cost Local Structured Evaluator (OpenJev-Style Secondary Layer).
    
    Provides deterministic, explainable structured signals:
    - technical_correctness (0-100)
    - relevance (0-100)
    - completeness (0-100)
    - major_misconception (bool)
    - needs_followup (bool)
    - structured_score (0-100)
    
    Runs 100% locally with zero external API calls and zero cloud inference cost.
    """

    def __init__(self):
        logger.info("LocalStructuredEvaluator initialized (Zero-Cost Local Layer)")

    def _tokenize(self, text: str) -> List[str]:
        """Extract clean alphanumeric words from text."""
        return re.findall(r"[a-z0-9_]+", text.lower())

    def _extract_content_words(self, words: List[str]) -> List[str]:
        """Filter out common stop words to retain key informative words."""
        return [w for w in words if w not in STOP_WORDS and len(w) > 1]

    def _extract_question_entities(self, question_text: str) -> List[str]:
        """Extract primary target entities/subjects from question."""
        words = self._tokenize(question_text)
        content_words = self._extract_content_words(words)
        
        # Look for explicit comparison entities e.g., "difference between X and Y"
        diff_match = re.search(r"difference\s+between\s+([a-z0-9_\s]+?)\s+and\s+([a-z0-9_\s]+?)(?:\?|$|\.|\,)", question_text.lower())
        if diff_match:
            first_subject = self._extract_content_words(self._tokenize(diff_match.group(1)))
            second_subject = self._extract_content_words(self._tokenize(diff_match.group(2)))
            entities = list(dict.fromkeys(first_subject + second_subject))
            if entities:
                return entities

        # Return unique informative content words
        return list(dict.fromkeys(content_words))

    def _detect_evasion(self, answer_text: str) -> bool:
        """Check if candidate answer consists primarily of evasion or non-answers."""
        cleaned = answer_text.strip().lower()
        if len(cleaned.split()) <= 6:
            for pattern in EVASION_PATTERNS:
                if re.search(pattern, cleaned):
                    return True
        return False

    def _detect_misconception(self, answer_text: str, question_text: str, topic: str) -> bool:
        """Scan candidate answer for established technical misconceptions."""
        normalized_answer = answer_text.lower()
        
        for rule in MISCONCEPTION_RULES:
            # Check if keywords match the question or topic
            keywords = rule.get("keywords", [])
            matches_context = any(
                kw in question_text.lower() or kw in topic.lower() or kw in normalized_answer
                for kw in keywords
            )
            
            if matches_context:
                if re.search(rule["pattern"], normalized_answer):
                    logger.warning(f"Detected technical misconception: {rule['id']} - {rule['description']}")
                    return True

        return False

    def _detect_uncertainty(self, answer_text: str) -> bool:
        """Check if the answer contains strong hesitation or uncertainty markers."""
        normalized = answer_text.lower()
        return any(bool(re.search(pat, normalized)) for pat in UNCERTAINTY_PATTERNS)

    def _calculate_relevance(
        self,
        question_entities: List[str],
        answer_words: List[str],
        answer_content_words: List[str],
        is_evasive: bool
    ) -> int:
        """Evaluate how directly the candidate addresses the question."""
        if is_evasive:
            return 10

        if not question_entities or not answer_content_words:
            return 50

        # Measure coverage of question key entities in the candidate answer
        answer_set = set(answer_content_words)
        entities_covered = sum(1 for ent in question_entities if ent in answer_set or any(ent in word or word in ent for word in answer_set))
        coverage_ratio = entities_covered / len(question_entities) if question_entities else 1.0

        # If question has multiple major entities (e.g. process AND thread), check both
        if len(question_entities) >= 2:
            relevance_score = 40 + (coverage_ratio * 58)
        else:
            relevance_score = 50 + (coverage_ratio * 48)

        # Penalize if answer is completely devoid of question words
        if entities_covered == 0 and len(answer_words) > 10:
            relevance_score = max(20, relevance_score - 30)

        return int(max(0, min(100, round(relevance_score))))

    def _calculate_completeness(
        self,
        answer_words: List[str],
        answer_content_words: List[str],
        question_text: str,
        topic: str
    ) -> int:
        """Evaluate depth, explanation structure, and domain concept density."""
        word_count = len(answer_words)
        
        # Word count depth progression (calibrated for technical answers)
        if word_count < 10:
            depth_score = word_count * 3.5  # 0 - 35
        elif word_count < 25:
            depth_score = 35 + ((word_count - 10) * 1.6)  # 35 - 59
        elif word_count < 60:
            depth_score = 60 + ((word_count - 25) * 0.7)  # 60 - 84
        elif word_count < 120:
            depth_score = 85 + ((word_count - 60) * 0.2)  # 85 - 97
        else:
            depth_score = 98

        # Explanatory and comparative markers
        answer_text_lower = " ".join(answer_words)
        structural_markers = [
            "because", "whereas", "while", "unlike", "instead", "differ", "means",
            "refers to", "consists of", "allows", "handles", "example", "tradeoff",
            "overhead", "advantage", "shares", "isolated", "responsible for"
        ]
        marker_hits = sum(1 for marker in structural_markers if marker in answer_text_lower)
        structure_bonus = min(15, marker_hits * 3)

        # Domain concept density
        domain_concepts: Set[str] = set()
        for key, concepts in TOPIC_CONCEPT_MAP.items():
            if key in question_text.lower() or key in topic.lower():
                domain_concepts.update(concepts)

        if domain_concepts:
            concept_hits = sum(1 for c in domain_concepts if c in set(answer_content_words))
            concept_ratio = min(1.0, concept_hits / max(3, len(domain_concepts) * 0.4))
            domain_bonus = concept_ratio * 15
        else:
            unique_ratio = len(set(answer_content_words)) / max(1, len(answer_content_words))
            domain_bonus = min(15, unique_ratio * 15)

        raw_completeness = (depth_score * 0.70) + structure_bonus + domain_bonus
        return int(max(0, min(100, round(raw_completeness))))

    def _calculate_technical_correctness(
        self,
        relevance: int,
        completeness: int,
        has_misconception: bool,
        answer_content_words: List[str],
        question_text: str,
        topic: str
    ) -> int:
        """Evaluate technical accuracy, factoring in misconceptions and domain alignment."""
        if has_misconception:
            # Significant cap on technical correctness for factual misconception
            base = min(45, (relevance * 0.35 + completeness * 0.30))
            return int(max(15, min(48, round(base))))

        # When no misconception is detected, technical correctness is anchored by
        # domain alignment and explanation quality
        domain_concepts: Set[str] = set()
        for key, concepts in TOPIC_CONCEPT_MAP.items():
            if key in question_text.lower() or key in topic.lower():
                domain_concepts.update(concepts)

        if domain_concepts:
            content_set = set(answer_content_words)
            hits = sum(1 for c in domain_concepts if c in content_set)
            accuracy_boost = min(20, hits * 4)
        else:
            accuracy_boost = 10

        # Harmonize with relevance and completeness
        base_correctness = (relevance * 0.55) + (completeness * 0.30) + accuracy_boost
        return int(max(20, min(98, round(base_correctness))))

    def evaluate(
        self,
        job_role: str,
        question: QuestionItem,
        candidate_answer: str
    ) -> Dict[str, Any]:
        """
        Evaluate candidate answer locally using explainable rule-based logic.
        
        Returns:
            Dict containing:
                - technical_correctness: int (0-100)
                - relevance: int (0-100)
                - completeness: int (0-100)
                - major_misconception: bool
                - needs_followup: bool
                - structured_score: int (0-100)
        """
        # Step 1: Empty answer guard
        if not candidate_answer or not candidate_answer.strip():
            logger.info("Structured evaluator: candidate answer is empty")
            return {
                "technical_correctness": 0,
                "relevance": 0,
                "completeness": 0,
                "major_misconception": False,
                "needs_followup": True,
                "structured_score": 0
            }

        q_text = question.question if question and question.question else ""
        q_topic = question.topic if question and question.topic else "General"
        
        words = self._tokenize(candidate_answer)
        content_words = self._extract_content_words(words)
        question_entities = self._extract_question_entities(q_text)

        # Step 2: Check for evasion / non-answer
        is_evasive = self._detect_evasion(candidate_answer)
        if is_evasive:
            logger.info("Structured evaluator: evasion detected in candidate answer")
            return {
                "technical_correctness": 15,
                "relevance": 10,
                "completeness": 10,
                "major_misconception": False,
                "needs_followup": True,
                "structured_score": 12
            }

        # Step 3: Check for major technical misconceptions
        has_misconception = self._detect_misconception(candidate_answer, q_text, q_topic)

        # Step 4: Calculate relevance and completeness
        relevance = self._calculate_relevance(question_entities, words, content_words, is_evasive)
        completeness = self._calculate_completeness(words, content_words, q_text, q_topic)

        # Step 5: Calculate technical correctness
        technical_correctness = self._calculate_technical_correctness(
            relevance=relevance,
            completeness=completeness,
            has_misconception=has_misconception,
            answer_content_words=content_words,
            question_text=q_text,
            topic=q_topic
        )

        # Step 6: Determine if follow-up is needed
        has_uncertainty = self._detect_uncertainty(candidate_answer)
        word_count = len(words)
        needs_followup = bool(
            has_misconception
            or has_uncertainty
            or word_count < 20
            or completeness < 55
            or relevance < 60
        )

        # Step 7: Calculate composite structured score
        # Conservative weighting: 50% correctness, 30% relevance, 20% completeness
        raw_score = (
            (technical_correctness * 0.50) +
            (relevance * 0.30) +
            (completeness * 0.20)
        )
        if has_misconception:
            structured_score = int(min(raw_score, 50))
        else:
            structured_score = int(round(raw_score))

        structured_score = max(0, min(100, structured_score))

        logger.info(
            f"Structured evaluation complete: correctness={technical_correctness}, "
            f"relevance={relevance}, completeness={completeness}, "
            f"misconception={has_misconception}, followup={needs_followup}, "
            f"score={structured_score}"
        )

        return {
            "technical_correctness": technical_correctness,
            "relevance": relevance,
            "completeness": completeness,
            "major_misconception": has_misconception,
            "needs_followup": needs_followup,
            "structured_score": structured_score
        }


# Singleton instance
structured_evaluator = LocalStructuredEvaluator()
