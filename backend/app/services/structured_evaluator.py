"""
structured_evaluator.py — Local deterministic technical answer evaluator.

Principles:
- Explainable rule-based scoring with no external API calls.
- Concept-level assessment (covered / partial / missing / contradicted).
- Synonym and paraphrase support via configurable maps.
- Negation-aware misconception detection (e.g. "primary key CANNOT be null"
  is correct and must NOT be flagged as the misconception).
- Anti-length-bias: a concise correct answer can outscore a long irrelevant one.
- Returns structured evidence tied to the actual transcript.
- Clearly labeled as 'local_only' evaluation method.
"""

import re
import logging
from typing import Dict, Any, List, Optional, Set, Tuple

from backend.app.schemas.question import QuestionItem

logger = logging.getLogger("structured_evaluator")

# ── Stop words ────────────────────────────────────────────────────────────────
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

# ── Evasion patterns ──────────────────────────────────────────────────────────
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

# ── Uncertainty markers (suggest follow-up, not automatic penalisation) ────────
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

# ── Negation prefixes that negate the following claim ─────────────────────────
# Used to flip misconception detection: if the statement is negated, it may be
# a correct assertion (e.g. "primary keys cannot be null" is correct).
NEGATION_PREFIXES = [
    r"(?:cannot|can't|does\s+not|doesn't|do\s+not|don't|"
    r"will\s+not|won't|must\s+not|mustn't|should\s+not|shouldn't|"
    r"never|no(?:t)?)\s+"
]

# ── Technical misconception rules ─────────────────────────────────────────────
# Each rule:
#   id          — unique identifier
#   description — human-readable description of the misconception
#   pattern     — regex matching the INCORRECT claim (without negation)
#   negated_ok  — if True, the negated form of this claim is CORRECT
#                 (e.g. "primary keys CAN be null" is wrong;
#                       "primary keys CANNOT be null" is right)
#   keywords    — words that must appear in the question/topic for this rule to activate
MISCONCEPTION_RULES = [
    # ── Threads / Processes ────────────────────────────────────────────────
    {
        "id": "thread_separate_memory",
        "description": "Claiming threads do not share memory",
        "pattern": r"\bthreads?\s+(?:always\s+)?(?:have|has)\s+(?:their|its)?\s*(?:own\s+)?(?:completely\s+)?(?:separate|isolated|independent)\s+memory\b",
        "negated_ok": False,
        "keywords": ["thread", "process", "memory"]
    },
    {
        "id": "threads_never_share_memory",
        "description": "Asserting threads never share memory",
        "pattern": r"\bthreads?\s+(?:never)\s+share\s+(?:memory|resources)\b",
        "negated_ok": False,
        "keywords": ["thread", "memory"]
    },
    {
        "id": "process_shared_memory_default",
        "description": "Claiming processes share memory by default without IPC",
        "pattern": r"\bprocesses\s+(?:automatically|by\s+default)\s+share\s+(?:the\s+same\s+)?memory\s+space\b",
        "negated_ok": False,
        "keywords": ["process", "memory"]
    },
    # ── HTTP / REST ────────────────────────────────────────────────────────
    {
        "id": "get_request_modifies_data",
        "description": "Claiming GET requests should mutate server state",
        "pattern": r"\bget\s+requests?\s+(?:are\s+used\s+to\s+|should\s+)?(?:modify|update|delete|mutate)\s+(?:data|resources?|database)\b",
        "negated_ok": False,
        "keywords": ["get", "http", "rest"]
    },
    {
        "id": "http_is_stateful",
        "description": "Claiming HTTP is stateful",
        "pattern": r"\bhttp\s+(?:is|has\s+a)\s+stateful\s+protocol\b",
        "negated_ok": True,   # "HTTP is NOT stateful" is correct
        "keywords": ["http", "protocol", "stateful"]
    },
    # ── Databases / SQL ────────────────────────────────────────────────────
    {
        "id": "primary_key_can_be_null",
        "description": "Claiming primary keys can store null values",
        "pattern": r"\bprimary\s+keys?\s+(?:can|may|could)\s+(?:contain|be|have|store|accept|allow)\s+null\b",
        "negated_ok": True,   # "primary keys CANNOT be null" is the CORRECT statement
        "keywords": ["primary", "key", "null"]
    },
    {
        "id": "indexing_speeds_writes",
        "description": "Claiming indexes always speed up write operations",
        "pattern": r"\bindexes?\s+(?:speeds?\s+up|accelerates?|improves?)\s+(?:write|insert|update)\s+performance\b",
        "negated_ok": False,
        "keywords": ["index", "write", "database"]
    },
    {
        "id": "sql_is_nosql",
        "description": "Claiming SQL is non-relational or schema-less",
        "pattern": r"\bsql\s+is\s+(?:a\s+)?(?:non-?relational|schema-?less)\s+database\b",
        "negated_ok": False,
        "keywords": ["sql", "database"]
    },
    # ── Algorithms / Data Structures ──────────────────────────────────────
    {
        "id": "binary_search_unsorted",
        "description": "Claiming binary search works on unsorted collections",
        "pattern": r"\bbinary\s+search\s+(?:works?\s+on|requires?\s+an?)\s+unsorted\b",
        "negated_ok": False,
        "keywords": ["binary", "search", "unsorted"]
    },
    {
        "id": "hashmap_linear_average",
        "description": "Claiming hash map average lookup is O(N)",
        "pattern": r"\bhash\s*maps?\s+(?:average\s+lookup|average\s+time)\s+is\s+o\(?n\)?\b",
        "negated_ok": False,
        "keywords": ["hashmap", "hash", "lookup"]
    },
    {
        "id": "array_random_access_linear",
        "description": "Claiming array random access is O(N)",
        "pattern": r"\barray\s+(?:random\s+access|index\s+lookup)\s+is\s+o\(?n\)?\b",
        "negated_ok": False,
        "keywords": ["array", "access"]
    },
    # ── Concurrency ────────────────────────────────────────────────────────
    {
        "id": "mutex_allows_concurrent_writes",
        "description": "Claiming a mutex allows multiple concurrent writers",
        "pattern": r"\bmutex\s+allows?\s+multiple\s+(?:concurrent\s+)?(?:writers?|writes?)\b",
        "negated_ok": False,
        "keywords": ["mutex", "concurrent"]
    },
    # ── Python ────────────────────────────────────────────────────────────
    {
        "id": "python_compiles_to_machine_code",
        "description": "Claiming standard CPython compiles to native machine code",
        "pattern": r"\bpython\s+(?:is\s+compiled\s+directly\s+to\s+native\s+machine\s+code)\b",
        "negated_ok": False,
        "keywords": ["python", "machine", "code"]
    }
]

# ── Synonym / paraphrase map ──────────────────────────────────────────────────
# Maps canonical concept terms to sets of acceptable synonyms.
# When evaluating concept coverage, any synonym counts as covering the concept.
SYNONYM_MAP: Dict[str, Set[str]] = {
    "process":        {"program", "application", "app", "executable", "task"},
    "thread":         {"lightweight process", "execution unit", "worker"},
    "memory":         {"ram", "heap", "stack", "address space", "storage"},
    "isolation":      {"separate", "independent", "sandboxed", "isolated"},
    "ipc":            {"inter-process communication", "pipe", "socket", "shared memory", "message queue"},
    "primary key":    {"pk", "unique identifier", "unique id", "primary constraint"},
    "foreign key":    {"fk", "reference", "referential constraint"},
    "null":           {"none", "nil", "empty", "missing value"},
    "http":           {"hypertext transfer protocol", "web protocol"},
    "stateless":      {"no state", "no session", "does not maintain state", "connectionless"},
    "idempotent":     {"safe to repeat", "same result when repeated", "repeatable"},
    "index":          {"database index", "b-tree", "btree", "hash index"},
    "transaction":    {"atomic operation", "acid", "atomicity"},
    "normalization":  {"normal form", "1nf", "2nf", "3nf", "bcnf"},
    "binary search":  {"bisect", "log n search", "divide and conquer search"},
    "hash map":       {"hashmap", "hash table", "dictionary", "dict", "associative array"},
    "mutex":          {"mutual exclusion", "lock", "semaphore"},
    "docker":         {"container", "containerization"},
    "concurrency":    {"parallel", "concurrent", "multi-threading", "threading"},
    "recursion":      {"recursive", "calls itself", "base case"},
    "inheritance":    {"extends", "subclass", "superclass", "is-a"},
    "polymorphism":   {"override", "overload", "duck typing"},
    "encapsulation":  {"data hiding", "private", "access modifier"},
    "api":            {"application programming interface", "endpoint", "interface"},
    "rest":           {"restful", "representational state transfer"},
    "sql":            {"structured query language", "relational database", "rdbms"},
    "nosql":          {"non-relational", "document store", "key-value store", "mongodb"},
    "git":            {"version control", "vcs", "source control"},
    "ci/cd":          {"continuous integration", "continuous delivery", "pipeline"},
    "cache":          {"caching", "memoize", "memoization", "redis", "memcached"},
    "latency":        {"delay", "response time", "lag"},
    "throughput":     {"requests per second", "rps", "bandwidth", "qps"},
    "load balancing": {"load balancer", "distribute load", "round robin", "nginx"},
    "microservices":  {"micro service", "service-oriented", "soa"},
    "solid":          {"single responsibility", "open closed", "liskov", "interface segregation", "dependency inversion"},
    "tcp":            {"transmission control protocol", "reliable connection"},
    "udp":            {"user datagram protocol", "connectionless protocol"},
    "encryption":     {"cipher", "encrypt", "aes", "rsa", "tls", "ssl"},
    "authentication": {"auth", "login", "jwt", "oauth", "token"},
    "authorization":  {"permissions", "access control", "rbac"},
    "deadlock":       {"circular wait", "resource contention", "livelock"},
    "gradient":       {"gradient descent", "backpropagation", "learning rate"},
    "overfitting":    {"overfit", "high variance", "memorisation"},
    "underfitting":   {"underfit", "high bias", "too simple"},
}

# ── Domain concept map by topic ───────────────────────────────────────────────
TOPIC_CONCEPT_MAP: Dict[str, List[str]] = {
    "process":         ["thread", "memory", "space", "execution", "share", "cpu", "stack", "heap", "isolation", "resource", "ipc", "overhead"],
    "thread":          ["process", "memory", "space", "execution", "share", "stack", "lightweight", "concurrency", "cpu", "overhead"],
    "database":        ["query", "table", "index", "acid", "transaction", "schema", "relation", "consistency", "primary", "foreign", "normalization"],
    "sql":             ["query", "table", "join", "select", "index", "schema", "acid", "relational", "primary", "key"],
    "api":             ["endpoint", "request", "response", "rest", "http", "status", "json", "payload", "authentication", "client", "server"],
    "rest":            ["http", "get", "post", "put", "delete", "stateless", "resource", "endpoint", "status", "json", "idempotent"],
    "git":             ["commit", "branch", "merge", "repository", "remote", "pull", "push", "conflict", "rebase", "checkout"],
    "docker":          ["container", "image", "dockerfile", "virtualization", "isolation", "host", "port", "volume", "compose"],
    "data structure":  ["array", "list", "stack", "queue", "tree", "graph", "hash", "node", "complexity", "pointer"],
    "security":        ["authentication", "authorization", "token", "encryption", "hash", "jwt", "vulnerability", "permission"],
    "machine learning": ["model", "training", "weights", "features", "dataset", "loss", "gradient", "evaluation", "accuracy", "overfitting"],
    "python":          ["function", "class", "module", "object", "interpreter", "list", "dict", "generator", "decorator", "gil"],
    "backend":         ["server", "api", "database", "service", "request", "route", "handler", "middleware", "performance", "scaling"],
    "frontend":        ["component", "dom", "state", "props", "ui", "render", "event", "css", "javascript", "browser"],
    "concurrency":     ["thread", "process", "lock", "mutex", "deadlock", "race", "synchronization", "async", "await"],
    "algorithm":       ["complexity", "big-o", "sorting", "searching", "recursion", "divide", "dynamic", "greedy"],
    "networking":      ["tcp", "udp", "ip", "dns", "http", "https", "port", "socket", "latency", "bandwidth"],
    "cloud":           ["aws", "azure", "gcp", "s3", "ec2", "lambda", "kubernetes", "docker", "microservices", "scaling"],
    "design pattern":  ["singleton", "factory", "observer", "strategy", "decorator", "proxy", "facade", "solid"],
}


class LocalStructuredEvaluator:
    """
    Zero-Cost Local Structured Evaluator.

    Provides deterministic, explainable evaluation signals without any external
    API calls or cloud inference. All evidence is tied to the candidate's
    actual transcript — no content is fabricated.

    Scoring rationale
    ─────────────────
    • A concise, technically correct answer CAN outscore a long irrelevant answer.
    • Long answers receive NO bonus purely for length.
    • Concept coverage is the primary correctness signal when expected concepts
      are available.
    • Misconceptions cap the score; negated misconception statements (correct
      assertions) do NOT trigger the cap.

    Configurable via .env / settings:
    • STRUCTURED_EVALUATION_ENABLED
    • STRUCTURED_EVALUATION_WEIGHT (Groq weight = 1 - this)
    """

    def __init__(self):
        logger.info("LocalStructuredEvaluator initialized (zero-cost local layer)")

    # ── Tokenisation helpers ──────────────────────────────────────────────────

    def _tokenize(self, text: str) -> List[str]:
        return re.findall(r"[a-z0-9_]+", text.lower())

    def _content_words(self, words: List[str]) -> List[str]:
        return [w for w in words if w not in STOP_WORDS and len(w) > 1]

    def _normalize(self, text: str) -> str:
        return re.sub(r"\s+", " ", text.lower().strip())

    # ── Concept matching with synonyms ────────────────────────────────────────

    def _term_in_answer(self, term: str, answer_norm: str, answer_words: Set[str]) -> bool:
        """
        Check whether a term (or any known synonym) appears in the answer.
        Supports multi-word synonyms via substring search on the normalized answer.
        """
        # Direct word match
        for t in self._tokenize(term):
            if t in answer_words:
                return True
        # Multi-word phrase match
        if term in answer_norm:
            return True
        # Synonym check
        synonyms = SYNONYM_MAP.get(term.lower(), set())
        for syn in synonyms:
            if syn in answer_norm or all(s in answer_words for s in self._tokenize(syn)):
                return True
        return False

    def _score_concept(
        self, concept: str, answer_norm: str, answer_words: Set[str]
    ) -> str:
        """
        Score a single expected concept against the answer.
        Returns: 'covered' | 'partial' | 'missing'
        """
        if self._term_in_answer(concept, answer_norm, answer_words):
            return "covered"
        # Partial: at least one token of a multi-word concept appears
        tokens = self._tokenize(concept)
        if len(tokens) > 1 and any(t in answer_words for t in tokens if len(t) > 2):
            return "partial"
        return "missing"

    # ── Evasion / uncertainty detection ──────────────────────────────────────

    def _detect_evasion(self, text: str) -> bool:
        cleaned = self._normalize(text)
        if len(cleaned.split()) <= 15:
            for pat in EVASION_PATTERNS:
                if re.search(pat, cleaned):
                    return True
        return False

    def _detect_uncertainty(self, text: str) -> bool:
        norm = self._normalize(text)
        return any(bool(re.search(pat, norm)) for pat in UNCERTAINTY_PATTERNS)

    # ── Negation-aware misconception detection ────────────────────────────────

    def _is_negated(self, match_start: int, text: str) -> bool:
        """
        Check whether the matched pattern is preceded by a negation word
        within a short window (≤ 6 words before the match).
        """
        prefix = text[max(0, match_start - 60):match_start]
        for neg in NEGATION_PREFIXES:
            if re.search(neg + r"$", prefix.strip()):
                return True
        # Also check inline negation patterns like "cannot", "doesn't", "never"
        last_words = prefix.strip().split()[-6:]
        neg_words = {"not", "no", "cannot", "can't", "never", "doesn't",
                     "don't", "doesn't", "won't", "shouldn't", "mustn't",
                     "isn't", "aren't", "wasn't", "weren't"}
        return bool(neg_words.intersection(set(last_words)))

    def _detect_misconceptions(
        self, answer_text: str, question_text: str, topic: str
    ) -> List[str]:
        """
        Scan answer for known technical misconceptions.
        Returns list of misconception description strings.

        Negation-aware: if the pattern is preceded by a negating word and
        the rule's negated_ok flag is True, the match is not flagged.

        Example:
          Rule: "primary keys can be null"  (negated_ok=True)
          Answer: "primary keys CANNOT be null"  → no misconception
          Answer: "primary keys CAN be null"     → misconception flagged
        """
        normalized = answer_text.lower()
        detected = []

        for rule in MISCONCEPTION_RULES:
            keywords = rule.get("keywords", [])
            context_match = any(
                kw in question_text.lower() or kw in topic.lower() or kw in normalized
                for kw in keywords
            )
            if not context_match:
                continue

            m = re.search(rule["pattern"], normalized)
            if not m:
                continue

            # Check negation context
            if rule.get("negated_ok", False) and self._is_negated(m.start(), normalized):
                # Candidate correctly asserted the negated (true) form — not a misconception
                logger.debug(f"Rule {rule['id']}: match negated correctly — not flagging")
                continue

            logger.warning(f"Misconception detected: {rule['id']} — {rule['description']}")
            detected.append(rule["description"])

        return detected

    # ── Expected concept coverage ─────────────────────────────────────────────

    def _assess_concept_coverage(
        self,
        expected_concepts: List[str],
        answer_norm: str,
        answer_words: Set[str]
    ) -> Tuple[List[str], List[str], List[str], int]:
        """
        Returns (covered, partial, missing, coverage_score_0_100).
        coverage_score weights: covered=1.0, partial=0.5, missing=0.0
        """
        covered, partial_list, missing = [], [], []
        for concept in expected_concepts:
            status = self._score_concept(concept, answer_norm, answer_words)
            if status == "covered":
                covered.append(concept)
            elif status == "partial":
                partial_list.append(concept)
            else:
                missing.append(concept)

        total = len(expected_concepts)
        if total == 0:
            return covered, partial_list, missing, 75  # neutral when no expected concepts

        score = ((len(covered) * 1.0 + len(partial_list) * 0.5) / total) * 100
        return covered, partial_list, missing, int(min(100, score))

    # ── Question entity extraction ────────────────────────────────────────────

    def _extract_question_entities(self, question_text: str) -> List[str]:
        words = self._tokenize(question_text)
        content = self._content_words(words)

        diff_match = re.search(
            r"difference\s+between\s+([a-z0-9_\s]+?)\s+and\s+([a-z0-9_\s]+?)(?:\?|$|\.|\,)",
            question_text.lower()
        )
        if diff_match:
            a = self._content_words(self._tokenize(diff_match.group(1)))
            b = self._content_words(self._tokenize(diff_match.group(2)))
            entities = list(dict.fromkeys(a + b))
            if entities:
                return entities

        return list(dict.fromkeys(content))

    # ── Relevance ─────────────────────────────────────────────────────────────

    def _calculate_relevance(
        self,
        question_entities: List[str],
        answer_norm: str,
        answer_words_set: Set[str],
        is_evasive: bool
    ) -> int:
        if is_evasive:
            return 10
        if not question_entities:
            return 60  # neutral when no extractable entities

        covered = sum(
            1 for ent in question_entities
            if self._term_in_answer(ent, answer_norm, answer_words_set)
        )
        ratio = covered / len(question_entities)

        if len(question_entities) >= 2:
            score = 40 + (ratio * 58)
        else:
            score = 50 + (ratio * 48)

        if covered == 0 and len(answer_norm.split()) > 10:
            score = max(20, score - 30)

        return int(max(0, min(100, round(score))))

    # ── Completeness ──────────────────────────────────────────────────────────

    def _calculate_completeness(
        self,
        word_count: int,
        content_words: List[str],
        answer_norm: str,
        question_text: str,
        topic: str,
        concept_coverage_score: int
    ) -> int:
        """
        Measure depth and structure without rewarding verbosity.

        Anti-bias rule: word count is CAPPED at a ceiling contribution.
        Concept coverage (when available) is a stronger signal than length.
        """
        # Depth component — capped: 60+ words gives full depth credit
        if word_count < 10:
            depth = word_count * 3.5        # 0–35
        elif word_count < 30:
            depth = 35 + ((word_count - 10) * 1.5)  # 35–65
        elif word_count < 80:
            depth = 65 + ((word_count - 30) * 0.4)  # 65–85
        else:
            depth = 85  # cap — length beyond 80 words gives no extra credit

        # Structure markers (explanatory language)
        structural_markers = [
            "because", "whereas", "while", "unlike", "instead", "differ",
            "means", "refers to", "consists of", "allows", "handles", "example",
            "tradeoff", "overhead", "advantage", "shares", "isolated",
            "responsible for", "in contrast", "on the other hand", "however"
        ]
        marker_hits = sum(1 for m in structural_markers if m in answer_norm)
        structure_bonus = min(10, marker_hits * 2)

        # Domain concept density bonus
        domain_concepts: Set[str] = set()
        for key, concepts in TOPIC_CONCEPT_MAP.items():
            if key in question_text.lower() or key in topic.lower():
                domain_concepts.update(concepts)

        content_set = set(content_words)
        if domain_concepts:
            hits = sum(1 for c in domain_concepts if c in content_set)
            concept_density_bonus = min(10, int((hits / max(3, len(domain_concepts) * 0.4)) * 10))
        else:
            unique_ratio = len(content_set) / max(1, len(content_words))
            concept_density_bonus = min(10, int(unique_ratio * 10))

        # When we have expected concept coverage, blend it in (it's a stronger signal)
        if concept_coverage_score > 0:
            raw = (depth * 0.45) + (concept_coverage_score * 0.35) + structure_bonus + concept_density_bonus
        else:
            raw = (depth * 0.70) + structure_bonus + concept_density_bonus

        return int(max(0, min(100, round(raw))))

    # ── Technical correctness ─────────────────────────────────────────────────

    def _calculate_technical_correctness(
        self,
        relevance: int,
        completeness: int,
        misconceptions: List[str],
        content_words: List[str],
        question_text: str,
        topic: str,
        concept_coverage_score: int
    ) -> int:
        if misconceptions:
            # Misconception cap — answer cannot score well if it contains incorrect claims
            base = min(45, (relevance * 0.35 + completeness * 0.30))
            return int(max(15, min(48, round(base))))

        # Domain alignment bonus
        domain_concepts: Set[str] = set()
        for key, concepts in TOPIC_CONCEPT_MAP.items():
            if key in question_text.lower() or key in topic.lower():
                domain_concepts.update(concepts)

        content_set = set(content_words)
        if domain_concepts:
            hits = sum(1 for c in domain_concepts if c in content_set)
            accuracy_boost = min(20, hits * 4)
        else:
            accuracy_boost = 10

        # Blend: concept coverage is the primary signal if available
        if concept_coverage_score > 0:
            base = (concept_coverage_score * 0.50) + (relevance * 0.30) + accuracy_boost
        else:
            base = (relevance * 0.55) + (completeness * 0.30) + accuracy_boost

        return int(max(20, min(98, round(base))))

    # ── Evidence extraction ───────────────────────────────────────────────────

    def _extract_evidence(
        self,
        transcript: str,
        covered_concepts: List[str],
        misconceptions: List[str]
    ) -> List[str]:
        """
        Return short quoted excerpts from the transcript as evidence.
        Only uses text that actually appears in the transcript — no fabrication.
        """
        evidence = []
        sentences = re.split(r"(?<=[.!?])\s+", transcript)

        # Evidence for covered concepts
        for concept in covered_concepts[:3]:
            for sent in sentences:
                if concept.lower() in sent.lower() or any(
                    syn in sent.lower() for syn in SYNONYM_MAP.get(concept.lower(), set())
                ):
                    snippet = sent[:120].strip()
                    if snippet:
                        evidence.append(f"Covered '{concept}': \"{snippet}\"")
                    break

        # Evidence for misconceptions
        for mis in misconceptions[:2]:
            evidence.append(f"Misconception noted: {mis}")

        return evidence

    # ── Main evaluation entry point ───────────────────────────────────────────

    def evaluate(
        self,
        job_role: str,
        question: QuestionItem,
        candidate_answer: str,
        expected_concepts: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Evaluate a candidate's answer locally.

        Args:
            job_role:          The target job role (used for context).
            question:          The QuestionItem (may include topic, difficulty).
            candidate_answer:  The candidate's transcript or text answer.
            expected_concepts: Optional list of concepts the answer should cover.
                               If question.expected_concepts exists it is used;
                               otherwise falls back to topic-derived domain concepts.

        Returns a structured dict with all evaluation signals.
        The 'evaluation_method' key is always set to 'local_only'.
        """
        # ── Guard: empty answer ───────────────────────────────────────────────
        if not candidate_answer or not candidate_answer.strip():
            return {
                "technical_correctness": 0,
                "relevance_score": 0,
                "completeness_score": 0,
                "structured_score": 0,
                "covered_concepts": [],
                "partial_concepts": [],
                "missing_concepts": [],
                "misconceptions": [],
                "major_misconception": False,
                "needs_followup": True,
                "reasoning_summary": "No answer provided.",
                "evidence": [],
                "evaluation_method": "local_only",   # backward-compat alias
                "structured_method": "local_only",
                # legacy keys for backward compatibility
                "relevance": 0,
                "completeness": 0,
            }

        q_text  = question.question if question and question.question else ""
        q_topic = question.topic    if question and question.topic    else "General"
        q_diff  = getattr(question, "difficulty", "MEDIUM") or "MEDIUM"

        # Resolve expected concepts
        if expected_concepts is None:
            expected_concepts = getattr(question, "expected_concepts", None) or []

        # ── Tokenise ──────────────────────────────────────────────────────────
        words      = self._tokenize(candidate_answer)
        content_w  = self._content_words(words)
        word_count = len(words)
        answer_norm = self._normalize(candidate_answer)
        answer_set  = set(content_w)
        q_entities  = self._extract_question_entities(q_text)

        # ── Evasion check ─────────────────────────────────────────────────────
        is_evasive = self._detect_evasion(candidate_answer)
        if is_evasive:
            return {
                "technical_correctness": 15,
                "relevance_score": 10,
                "completeness_score": 10,
                "structured_score": 12,
                "covered_concepts": [],
                "partial_concepts": [],
                "missing_concepts": expected_concepts,
                "misconceptions": [],
                "major_misconception": False,
                "needs_followup": True,
                "reasoning_summary": "Answer appears to be evasive or non-committal.",
                "evidence": [],
                "evaluation_method": "local_only",   # backward-compat alias
                "structured_method": "local_only",
                "relevance": 10,
                "completeness": 10,
            }

        # ── Concept coverage ──────────────────────────────────────────────────
        covered, partial_list, missing, coverage_score = self._assess_concept_coverage(
            expected_concepts, answer_norm, answer_set
        )

        # ── Misconception detection (negation-aware) ──────────────────────────
        misconceptions = self._detect_misconceptions(candidate_answer, q_text, q_topic)
        has_misconception = len(misconceptions) > 0

        # ── Subscores ─────────────────────────────────────────────────────────
        relevance = self._calculate_relevance(q_entities, answer_norm, answer_set, is_evasive)
        completeness = self._calculate_completeness(
            word_count, content_w, answer_norm, q_text, q_topic, coverage_score
        )
        technical_correctness = self._calculate_technical_correctness(
            relevance, completeness, misconceptions, content_w,
            q_text, q_topic, coverage_score
        )

        # ── Follow-up detection ───────────────────────────────────────────────
        has_uncertainty = self._detect_uncertainty(candidate_answer)
        needs_followup = bool(
            has_misconception
            or has_uncertainty
            or word_count < 20
            or completeness < 55
            or relevance < 60
        )

        # ── Composite score ───────────────────────────────────────────────────
        # Weights: 45% correctness, 30% relevance, 25% completeness
        # Anti-length-bias: completeness already has a hard cap on word-count contribution
        raw = (technical_correctness * 0.45) + (relevance * 0.30) + (completeness * 0.25)
        structured_score = int(min(raw, 50) if has_misconception else round(raw))
        structured_score = max(0, min(100, structured_score))

        # ── Reasoning summary ─────────────────────────────────────────────────
        summary_parts = []
        if covered:
            summary_parts.append(f"Correctly covered: {', '.join(covered[:4])}.")
        if partial_list:
            summary_parts.append(f"Partially addressed: {', '.join(partial_list[:3])}.")
        if missing:
            summary_parts.append(f"Missing concepts: {', '.join(missing[:4])}.")
        if has_misconception:
            summary_parts.append(f"Misconception(s) detected: {'; '.join(misconceptions[:2])}.")
        if not summary_parts:
            if relevance >= 75 and technical_correctness >= 70:
                summary_parts.append("Answer is relevant and technically sound.")
            elif relevance < 50:
                summary_parts.append("Answer does not closely address the question topic.")
            else:
                summary_parts.append("Answer shows partial understanding.")

        reasoning_summary = " ".join(summary_parts)

        # ── Evidence ──────────────────────────────────────────────────────────
        evidence = self._extract_evidence(candidate_answer, covered, misconceptions)

        logger.info(
            f"Local eval: correctness={technical_correctness}, relevance={relevance}, "
            f"completeness={completeness}, score={structured_score}, "
            f"misconception={has_misconception}, covered={len(covered)}/{len(expected_concepts or [])}"
        )

        return {
            "technical_correctness": technical_correctness,
            "relevance_score": relevance,
            "completeness_score": completeness,
            "structured_score": structured_score,
            "covered_concepts": covered,
            "partial_concepts": partial_list,
            "missing_concepts": missing,
            "misconceptions": misconceptions,
            "major_misconception": has_misconception,
            "needs_followup": needs_followup,
            "reasoning_summary": reasoning_summary,
            "evidence": evidence,
            "evaluation_method": "local_only",   # backward-compat alias
            "structured_method": "local_only",
            # Legacy compatibility keys
            "relevance": relevance,
            "completeness": completeness,
        }


# Singleton
structured_evaluator = LocalStructuredEvaluator()
