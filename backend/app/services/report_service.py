"""
report_service.py — PDF report generation for completed interview sessions.

Uses fpdf2 (pip install fpdf2) — a lightweight, dependency-free PDF library
compatible with Python 3.8+ and no GPU required.

Report contents:
1. Candidate and session information
2. Interview date and completion status
3. Overall score and component breakdown
4. Per-question evaluation table
5. Transcripts and technical feedback
6. Covered and missing concepts
7. Misconceptions and corrections
8. Speech metrics (WPM, fillers, pauses)
9. Visual analysis (if enabled and available)
10. Strengths and improvement recommendations
11. Scoring methodology and limitations
12. Disclaimer: delivery measurements do not diagnose anxiety or personality

Security: report is generated from session data fetched via authenticated API.
One user's report cannot be accessed by another (enforced in the route handler).
"""

import re
import logging
from datetime import datetime
from typing import Optional, Any

logger = logging.getLogger("report_service")

try:
    from fpdf import FPDF, XPos, YPos
    FPDF2_AVAILABLE = True
except ImportError:
    FPDF2_AVAILABLE = False
    FPDF = object
    XPos = YPos = None
    logger.warning(
        "fpdf2 not installed. PDF report generation unavailable. "
        "Run: pip install fpdf2"
    )


# ── Color palette (High-contrast for white page background) ──────────────────
DARK_BG   = (15, 23, 42)       # Dark slate band for header
SURFACE   = (15, 23, 42)       # Dark slate band for question headers
ACCENT    = (20, 45, 85)       # Dark navy for section headings (contrast 13.7:1)
GREEN     = (22, 101, 52)      # Deep green for positive metrics (contrast 7.1:1)
AMBER     = (180, 83, 9)       # Dark amber for improvement & warnings (contrast 5.0:1)
RED       = (185, 28, 28)      # Deep crimson for misconceptions & errors (contrast 6.5:1)
TEXT_MAIN = (30, 30, 30)       # Dark primary body text (contrast 16.7:1 on white)
TEXT_MUTED= (85, 85, 85)       # Dark secondary text (contrast 7.5:1 on white, >= 4.5)
WHITE     = (255, 255, 255)
LIGHT_GRAY= (241, 245, 249)

# ── Page layout constants ──────────────────────────────────────────────────────
MARGIN  = 15
LW      = 180   # usable line width


def clean_text(text: Any) -> str:
    """Sanitize strings so they are safe for standard PDF core fonts (latin-1)."""
    if text is None:
        return ""
    if not isinstance(text, str):
        text = str(text)
    replacements = {
        "\u2014": " - ",
        "\u2013": " - ",
        "\u2026": "...",
        "\u2018": "'",
        "\u2019": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u2022": "*",
        "\u2713": "[+]",
        "\u2192": "->",
        "\u26a1": "",
        "\u26a0": "[!]",
        "\u2139": "[i]",
        "\u00f7": "/",
    }
    for orig, repl in replacements.items():
        text = text.replace(orig, repl)
    # Replace any run of characters that cannot be encoded as latin-1 with "[non-English text]"
    text = re.sub(r"[^\x00-\xff]+", "[non-English text]", text)
    return text.encode("latin-1", "replace").decode("latin-1")


class InterviewPDF(FPDF):
    """Custom FPDF subclass with report branding helpers."""

    def cell(self, *args, **kwargs):
        if len(args) >= 3 and isinstance(args[2], str):
            args_list = list(args)
            args_list[2] = clean_text(args_list[2])
            args = tuple(args_list)
        elif "text" in kwargs:
            kwargs["text"] = clean_text(kwargs["text"])
        return super().cell(*args, **kwargs)

    def multi_cell(self, *args, **kwargs):
        if len(args) >= 3 and isinstance(args[2], str):
            args_list = list(args)
            args_list[2] = clean_text(args_list[2])
            args = tuple(args_list)
        elif "text" in kwargs:
            kwargs["text"] = clean_text(kwargs["text"])
        return super().multi_cell(*args, **kwargs)

    def header(self):
        self.set_fill_color(*DARK_BG)
        self.rect(0, 0, self.w, 18, "F")
        self.set_font("Helvetica", "B", 10)
        self.set_text_color(*WHITE)
        self.set_xy(MARGIN, 5)
        self.cell(0, 8, "Interview Analyzer - Confidential Performance Report", align="L")
        self.set_text_color(*WHITE)
        self.set_xy(MARGIN, 5)
        self.cell(0, 8, f"Page {self.page_no()}", align="R")
        self.ln(14)

    def footer(self):
        self.set_y(-14)
        self.set_font("Helvetica", "", 7.5)
        self.set_text_color(*TEXT_MUTED)
        self.cell(0, 6,
            "This report is generated from AI-assisted analysis. "
            "Speech and visual signals are observable measurements, not psychological diagnoses.",
            align="C"
        )

    def section_title(self, text: str):
        if self.will_page_break(25):
            self.add_page()
        self.set_font("Helvetica", "B", 13)
        self.set_text_color(*ACCENT)
        self.cell(0, 8, clean_text(text), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.set_draw_color(*ACCENT)
        self.line(MARGIN, self.get_y(), MARGIN + LW, self.get_y())
        self.ln(4)

    def sub_title(self, text: str):
        self.set_font("Helvetica", "B", 10)
        self.set_text_color(*TEXT_MAIN)
        self.cell(0, 7, clean_text(text), new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    def body_text(self, text: str, color=None):
        self.set_font("Helvetica", "", 9)
        self.set_text_color(*(color or TEXT_MAIN))
        self.multi_cell(LW, 5, clean_text(text), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.ln(1)

    def kv_row(self, key: str, value: str, key_color=None, val_color=None):
        self.set_font("Helvetica", "B", 9)
        self.set_text_color(*(key_color or TEXT_MUTED))
        self.cell(55, 5.5, clean_text(key), new_x=XPos.RIGHT, new_y=YPos.TOP)
        self.set_font("Helvetica", "", 9)
        self.set_text_color(*(val_color or TEXT_MAIN))
        self.multi_cell(LW - 55, 5.5, clean_text(str(value)), new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    def score_bar(self, label: str, score: Optional[int], color=None):
        bar_color = color or ACCENT
        self.set_font("Helvetica", "", 9)
        self.set_text_color(*TEXT_MAIN)
        self.cell(60, 5.5, clean_text(label), new_x=XPos.RIGHT, new_y=YPos.TOP)
        if score is None:
            self.set_font("Helvetica", "I", 9)
            self.set_text_color(*TEXT_MUTED)
            self.cell(110, 5.5, "Not measured", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            self.ln(1)
            return

        # Bar background
        self.set_fill_color(226, 232, 240)
        self.rect(self.get_x(), self.get_y() + 1, 90, 3.5, "F")
        # Bar fill
        self.set_fill_color(*bar_color)
        self.rect(self.get_x(), self.get_y() + 1, 90 * min(score, 100) / 100, 3.5, "F")
        self.set_xy(self.get_x() + 93, self.get_y())
        self.set_font("Helvetica", "B", 9)
        self.set_text_color(*TEXT_MAIN)
        self.cell(20, 5.5, f"{score}/100", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.ln(1)

    def chips(self, items: list, color: tuple):
        """Render a list as colored inline tags."""
        self.set_font("Helvetica", "", 8)
        for item in items:
            c_item = clean_text(item)
            w = self.get_string_width(c_item) + 6
            if self.get_x() + w > MARGIN + LW:
                self.ln(6)
            self.set_fill_color(*color)
            self.set_text_color(*WHITE)
            self.cell(w, 5, c_item, fill=True, new_x=XPos.RIGHT, new_y=YPos.TOP)
            self.cell(2, 5)
        self.ln(8)



class ReportService:
    def generate_pdf_report(self, session) -> bytes:
        """
        Generate a PDF report from a completed AssessmentSession.

        Args:
            session: AssessmentSession Pydantic model (must have evaluation set).

        Returns:
            bytes: PDF file content.

        Raises:
            RuntimeError: if fpdf2 is not installed.
            ValueError:   if session has no evaluation data.
        """
        if not FPDF2_AVAILABLE:
            raise RuntimeError(
                "fpdf2 is not installed. Run: pip install fpdf2"
            )

        if not session.evaluation:
            raise ValueError("Session has no evaluation data. Complete the interview first.")

        ev = session.evaluation
        role = session.selected_role or "Unspecified Role"
        session_date = session.created_at or datetime.now().strftime("%Y-%m-%d")
        status = session.status or "unknown"

        pdf = InterviewPDF()
        pdf.set_auto_page_break(auto=True, margin=20)
        pdf.set_margins(MARGIN, 22, MARGIN)
        pdf.add_page()

        # ── Cover / header block ──────────────────────────────────────────────
        pdf.set_font("Helvetica", "B", 22)
        pdf.set_text_color(*TEXT_MAIN)
        pdf.cell(0, 12, "Interview Performance Report", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        pdf.set_font("Helvetica", "", 11)
        pdf.set_text_color(*TEXT_MUTED)
        pdf.cell(0, 7, f"Role: {role}  |  Date: {session_date}  |  Status: {status.upper()}",
                 new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.ln(6)

        # ── Overall score block ───────────────────────────────────────────────
        pdf.section_title("Overall Score")
        pdf.score_bar("Overall Multimodal Score",  ev.overall_score, ACCENT)
        pdf.score_bar("Technical / NLP Score",      ev.nlp_score,     GREEN)
        pdf.score_bar("Speech Delivery Score",       ev.speech_score,  AMBER)
        pdf.score_bar("Visual / Posture Score",      ev.video_score,   ACCENT)
        if getattr(ev, "modalities_used", None):
            pdf.set_font("Helvetica", "I", 8.5)
            pdf.set_text_color(*TEXT_MUTED)
            pdf.cell(0, 5, f"Contributing modalities: {', '.join(ev.modalities_used)}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.ln(3)

        # Summary
        if ev.summary:
            pdf.body_text(ev.summary)
        pdf.ln(2)

        # ── Session info ──────────────────────────────────────────────────────
        pdf.section_title("Session Information")
        pdf.kv_row("Session ID:",      session.session_id[:16] + "...")
        pdf.kv_row("Role Applied:",    role)
        pdf.kv_row("Interview Date:",  session_date)
        pdf.kv_row("Completion:",      status.upper())
        pdf.kv_row("Questions Done:",  f"{len(session.submissions)} of {len(session.questions)}")
        pdf.ln(4)

        # ── Aggregate speech metrics ──────────────────────────────────────────
        if ev.avg_wpm or ev.total_filler_count is not None:
            pdf.section_title("Interview-Wide Speech Metrics")
            if ev.avg_wpm:
                pdf.kv_row("Average WPM:", str(ev.avg_wpm))
            if ev.total_filler_count is not None:
                pdf.kv_row("Total Filler Words:", str(ev.total_filler_count))
            if ev.total_pause_count is not None:
                pdf.kv_row("Total Pauses Detected:", str(ev.total_pause_count))
            for note in ev.delivery_pattern_notes or []:
                pdf.body_text(f"* {note}", color=TEXT_MUTED)
            pdf.ln(2)

        # ── Strengths & gaps ──────────────────────────────────────────────────
        pdf.section_title("Key Strengths")
        for s in ev.strengths or ["No specific strengths recorded."]:
            pdf.body_text(f"[+]  {s}", color=GREEN)

        pdf.section_title("Areas for Improvement")
        for g in ev.gaps or ["No specific gaps recorded."]:
            pdf.body_text(f"*  {g}", color=AMBER)

        pdf.section_title("Recommendations")
        for r in ev.recommendations or ["No recommendations recorded."]:
            pdf.body_text(f"->  {r}")
        pdf.ln(2)

        # ── Per-question breakdown ────────────────────────────────────
        pdf.section_title("Per-Question Analysis")

        for q in ev.per_question:
            if pdf.will_page_break(50):
                pdf.add_page()

            # Question header
            pdf.set_fill_color(*SURFACE)
            pdf.rect(MARGIN, pdf.get_y(), LW, 8, "F")
            pdf.set_font("Helvetica", "B", 10)
            pdf.set_text_color(*WHITE)

            nlp_disp = f"{q.nlp_score}%" if q.nlp_score is not None else "Not measured"
            speech_disp = f"{q.speech_score}%" if q.speech_score is not None else "Not measured"
            video_disp = f"{q.video_score}%" if q.video_score is not None else "Not measured"
            score_disp = f"{q.score}/100" if q.score is not None else "Not measured"

            pdf.cell(LW, 8,
                     f"  Q{q.question_id}  -  Score: {score_disp}   "
                     f"(NLP: {nlp_disp} | Speech: {speech_disp} | Video: {video_disp})",
                     new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            pdf.ln(1)

            # Question text
            pdf.set_font("Helvetica", "BI", 9)
            pdf.set_text_color(*TEXT_MAIN)
            pdf.multi_cell(LW, 5, q.question, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            pdf.ln(1)

            # Transcript
            transcript = (q.transcript or "").strip()
            t_status = q.transcription_status or "no_recording"
            if transcript:
                pdf.set_font("Helvetica", "I", 8.5)
                pdf.set_text_color(*TEXT_MUTED)
                pdf.multi_cell(LW, 4.5,
                    f"Transcript ({t_status}): \"{transcript[:400]}{'...' if len(transcript) > 400 else ''}\"",
                    new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            else:
                pdf.set_font("Helvetica", "I", 8.5)
                pdf.set_text_color(*RED)
                pdf.cell(LW, 5, f"[No transcript - status: {t_status}]",
                         new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            pdf.ln(2)

            # Feedback
            pdf.set_font("Helvetica", "", 9)
            pdf.set_text_color(*TEXT_MAIN)
            pdf.multi_cell(LW, 5, f"Feedback: {q.feedback or 'N/A'}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            pdf.ln(1)

            # Concept coverage
            if q.covered_concepts:
                pdf.sub_title("Covered Concepts:")
                pdf.chips(q.covered_concepts, (22, 101, 52))
            if q.missing_concepts:
                pdf.sub_title("Missing Concepts:")
                pdf.chips(q.missing_concepts, (146, 64, 14))
            if q.misconceptions:
                pdf.sub_title("Misconceptions Detected:")
                for m in q.misconceptions:
                    pdf.body_text(f"[!]  {m}", color=RED)

            # Reasoning summary
            if q.reasoning_summary:
                pdf.body_text(f"Analysis: {q.reasoning_summary}", color=TEXT_MUTED)

            # Evaluation method
            if q.evaluation_method:
                pdf.set_font("Helvetica", "I", 7.5)
                pdf.set_text_color(*TEXT_MUTED)
                pdf.cell(0, 5, f"Evaluation method: {q.evaluation_method}",
                         new_x=XPos.LMARGIN, new_y=YPos.NEXT)

            pdf.ln(5)

        # ── Per-question speech metrics ────────────────────────────────────────
        pdf.section_title("Speech Delivery Details (Per Question)")

        for q_id, sub in session.submissions.items():
            sm = sub.speech_metrics
            if not sm:
                continue

            if pdf.will_page_break(50):
                pdf.add_page()

            pdf.sub_title(f"Question {q_id} - Speech")
            pdf.kv_row("WPM:", f"{sm.words_per_minute}  (reference: 120-170 WPM)")

            # Duration handling (Requirement 1a)
            dur = None
            if sm and getattr(sm, "duration_seconds", None) is not None and sm.duration_seconds > 0:
                dur = sm.duration_seconds
            else:
                q_match = next((pq for pq in (ev.per_question or []) if pq.question_id == int(q_id)), None)
                if q_match and getattr(q_match, "duration_seconds", None) is not None and q_match.duration_seconds > 0:
                    dur = q_match.duration_seconds

            dur_str = f"{dur:.1f} s" if dur is not None else "not available"
            pdf.kv_row("Duration:", dur_str)
            pdf.kv_row("Word Count:", str(sm.word_count))
            pdf.kv_row("Filler Words:", f"{sm.filler_word_count}  (rate: {sm.filler_frequency:.1%})")
            pdf.kv_row("Pauses Detected:", f"{sm.pause_count}  (long: {sm.long_pause_count})")
            if sm.longest_pause_seconds:
                pdf.kv_row("Longest Pause:", f"{sm.longest_pause_seconds:.1f} s")
            if sm.has_word_timestamps:
                pdf.kv_row("Median Gap:", f"{sm.median_inter_word_gap_ms:.0f} ms" if sm.median_inter_word_gap_ms is not None else "Not measured")
                pdf.kv_row("Mean Gap:", f"{sm.mean_inter_word_gap_ms:.0f} ms" if sm.mean_inter_word_gap_ms is not None else "Not measured")
            pdf.kv_row("Analysis Method:", sm.analysis_method or "Not measured")
            for w in sm.analysis_warnings or []:
                pdf.body_text(f"[!] {w}", color=AMBER)
            for n in sm.delivery_pattern_notes or []:
                pdf.body_text(f"[i] {n}", color=TEXT_MUTED)

            # Filler breakdown
            if sm.filler_breakdown:
                filler_text = "  |  ".join(f"{k}: {v}" for k, v in sm.filler_breakdown.items())
                pdf.body_text(f"Filler breakdown: {filler_text}", color=TEXT_MUTED)
            pdf.ln(3)

        # ── Visual analysis ───────────────────────────────────────────────────
        pdf.section_title("Visual & Posture Analysis")

        for q_id, sub in session.submissions.items():
            vm = sub.video_metrics
            if not vm:
                continue

            if pdf.will_page_break(50):
                pdf.add_page()

            pdf.sub_title(f"Question {q_id} - Visual")
            pdf.kv_row("Analysis Method:", str(vm.analysis_method) if vm.analysis_method else "Not measured")
            pdf.kv_row("Frames Sampled:", str(vm.frames_sampled) if vm.frames_sampled is not None else "Not measured")
            pdf.kv_row("Frames with Detection:", str(vm.frames_with_face) if vm.frames_with_face is not None else "Not measured")
            
            det_rate_str = f"{vm.face_detection_rate:.0%}" if vm.face_detection_rate is not None else "Not measured"
            pdf.kv_row("Detection Rate:", det_rate_str)
            
            face_vis_str = f"{vm.face_visibility_score}/100" if vm.face_visibility_score is not None else "Not measured"
            pdf.kv_row("Face Visibility:", face_vis_str)
            
            att_str = f"{vm.attention_score}/100" if vm.attention_score is not None else "Not measured"
            pdf.kv_row("Attention:", att_str)
            
            posture_str = f"{vm.posture_score}/100" if vm.posture_score is not None else "Not measured"
            pdf.kv_row("Posture:", posture_str)
            
            vid_score_str = f"{vm.video_score}/100" if vm.video_score is not None else "Not measured"
            pdf.kv_row("Video Score:", vid_score_str)

            if getattr(vm, "posture_unavailable_reason", None):
                pdf.kv_row("Posture Unavailable:", str(vm.posture_unavailable_reason))

            if vm.movement_variation is not None:
                pdf.kv_row("Movement Variation:", f"{vm.movement_variation:.4f} (std dev)")
            for w in vm.analysis_warnings or []:
                pdf.body_text(f"[!] {w}", color=AMBER)
            for n in vm.delivery_pattern_notes or []:
                pdf.body_text(f"[i] {n}", color=TEXT_MUTED)
            pdf.ln(3)

        # ── Delivery patterns section ─────────────────────────────────────────
        pdf.section_title("Delivery Patterns - Observable Signals")
        pdf.body_text(
            "The following observable delivery patterns were detected during the interview. "
            "These are measurable signals, NOT diagnoses of anxiety, confidence, or emotional state. "
            "Each pattern can have many explanations including thinking time, question difficulty, "
            "language familiarity, environmental noise, microphone quality, and individual speaking style.",
            color=TEXT_MUTED
        )
        pdf.ln(2)

        all_speech_notes = []
        all_video_notes = []
        for _, sub in session.submissions.items():
            if sub.speech_metrics:
                all_speech_notes.extend(sub.speech_metrics.delivery_pattern_notes or [])
            if sub.video_metrics:
                all_video_notes.extend(sub.video_metrics.delivery_pattern_notes or [])

        if all_speech_notes:
            pdf.sub_title("Speech Patterns:")
            for note in set(all_speech_notes):
                pdf.body_text(f"* {note}")
        if all_video_notes:
            pdf.sub_title("Visual Patterns:")
            for note in set(all_video_notes):
                pdf.body_text(f"* {note}")

        if not all_speech_notes and not all_video_notes:
            pdf.body_text("No notable delivery patterns detected.", color=TEXT_MUTED)

        # ── Methodology ───────────────────────────────────────────────────────
        pdf.section_title("Evaluation Methodology")
        pdf.body_text(
            "Technical score (NLP): Evaluated by Groq LLM (primary, 75%) and a local structured "
            "evaluator (secondary, 25%). Weights are configurable. When Groq is unavailable, "
            "the result is labelled 'local_only'.",
        )
        pdf.body_text(
            "Speech delivery: WPM calculated from transcript word count / recording duration. "
            "Pauses detected via audio energy analysis (pydub) where available. "
            "The conversational reference range (120-170 WPM) is a broad guide, not a scoring threshold.",
        )
        pdf.body_text(
            "Visual analysis: Performed locally using MediaPipe Pose (if installed) or OpenCV Haar "
            "cascade. Face/pose detection rates and movement variation are reported. These are "
            "observable signals only.",
        )

        pdf.section_title("Limitations & Disclaimer")
        pdf.body_text(
            "* Speech and visual measurements are NOT validated diagnostic tools for anxiety, "
            "confidence, attention, or any psychological state.\n"
            "* Scores may be affected by microphone quality, camera position, lighting, "
            "background noise, and internet connection.\n"
            "* The system does not account for accent, disability, or individual communication style.\n"
            "* Evaluation weights (NLP 50%, Speech 25%, Video 25%) represent a design choice, "
            "not a scientifically validated standard.\n"
            "* This report should be used as one input among many in any hiring or assessment "
            "decision - not as the sole determinant.",
            color=TEXT_MUTED
        )

        return bytes(pdf.output())


report_service = ReportService()
