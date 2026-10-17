"""
video_analysis_service.py — Local body posture and visual analysis.

Uses OpenCV for video loading and frame sampling.
Uses MediaPipe Tasks Pose Landmarker (pose_landmarker_lite.task) for upper-body landmarks.
Falls back to OpenCV Haar cascade face detection with bundled XML.
Uses ffmpeg to transcode problematic WebM containers if OpenCV cannot decode directly.

IMPORTANT LIMITATIONS (disclosed intentionally):
- Camera position varies; landmark detection rates will differ.
- Gaze direction, facial movement, and body motion do NOT prove confidence,
  attention, or emotional state.
- Do not penalise candidates for glasses, disability, unconventional camera
  setup, or individual communication styles.
- All results are labelled as observable signals with confidence disclosures.
- Video analysis can be disabled via VIDEO_ANALYSIS_ENABLED=false in .env.
"""

import os
import shutil
import logging
import subprocess
import tempfile
import numpy as np
from pathlib import Path
from typing import List, Optional, Tuple

from backend.app.schemas.evaluation import VideoMetrics
from backend.app.core.config import settings

logger = logging.getLogger("video_analysis_service")

# ── Bundled Asset Paths ────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent
MODELS_DIR = BASE_DIR / "assets" / "models"
POSE_LANDMARKER_MODEL_PATH = MODELS_DIR / "pose_landmarker_lite.task"
HAAR_CASCADE_MODEL_PATH = MODELS_DIR / "haarcascade_frontalface_default.xml"

# ── Optional dependencies (graceful degradation) ──────────────────────────────
try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False
    logger.info("OpenCV (cv2) not installed — video analysis disabled.")

try:
    import mediapipe as mp
    from mediapipe.tasks import python as mp_python
    from mediapipe.tasks.python import vision as mp_vision
    MEDIAPIPE_AVAILABLE = True
except ImportError:
    MEDIAPIPE_AVAILABLE = False
    logger.info("MediaPipe Tasks not installed — falling back to Haar cascade face detection.")

# Check model availability at startup
if not POSE_LANDMARKER_MODEL_PATH.exists():
    logger.warning(f"Pose Landmarker model not found at {POSE_LANDMARKER_MODEL_PATH}. MediaPipe analysis will be unavailable.")

if not HAAR_CASCADE_MODEL_PATH.exists():
    logger.warning(f"Haar cascade XML not found at {HAAR_CASCADE_MODEL_PATH}. Haar fallback may be unavailable.")

# ── Configuration ──────────────────────────────────────────────────────────────
TARGET_SAMPLE_FPS: float = 3.0
SAMPLE_INTERVAL_MS: float = 1000.0 / TARGET_SAMPLE_FPS  # ~333.3 ms

# Upper-body landmark indices for MediaPipe Pose (33-point model)
# Nose: 0, Left Shoulder: 11, Right Shoulder: 12
POSE_LANDMARKS = {
    "nose": 0,
    "left_shoulder": 11,
    "right_shoulder": 12,
    "left_hip": 23,
    "right_hip": 24,
}


class VideoService:
    """Analyzes candidate video for observable posture and presence signals."""

    def analyze_video_recording(self, video_path: Path) -> VideoMetrics:
        """
        Analyze a recorded interview video.

        Returns VideoMetrics with:
        - Face / pose detection rates
        - Posture, attention, and movement variation
        - Analysis method and any warnings
        """
        video_enabled = getattr(settings, "VIDEO_ANALYSIS_ENABLED", True)
        if not video_enabled:
            return VideoMetrics(
                frames_sampled=0,
                frames_with_face=0,
                face_detection_rate=0.0,
                pose_detection_rate=0.0,
                face_visibility_score=None,
                attention_score=None,
                posture_score=None,
                stability_score=None,
                movement_variation=None,
                head_movement_variation=None,
                video_analysis_enabled=False,
                analysis_method="disabled",
                analysis_warnings=["Video analysis is disabled in application settings."],
                delivery_pattern_notes=[],
                video_score=None
            )

        if not video_path.exists():
            return self._unavailable_metrics("Video file not found.")

        if not CV2_AVAILABLE:
            return self._unavailable_metrics("OpenCV not installed — video analysis unavailable.")

        # Ensure video is decodable by OpenCV (transcode WebM if necessary)
        working_video_path, temp_file_to_clean = self._ensure_decodable_video(video_path)

        try:
            # 1. Primary: MediaPipe Tasks Pose Landmarker
            if MEDIAPIPE_AVAILABLE and POSE_LANDMARKER_MODEL_PATH.exists():
                try:
                    return self._analyze_with_mediapipe(working_video_path)
                except Exception as exc:
                    logger.warning(
                        "MediaPipe PoseLandmarker analysis failed: %s. Falling back to Haar cascade.", exc
                    )

            # 2. Secondary: Haar cascade face detection
            return self._analyze_with_haar(working_video_path)

        except Exception as exc:
            logger.exception("Unexpected error during video analysis: %s", exc)
            return self._unavailable_metrics(f"Video analysis failed: {exc}")
        finally:
            if temp_file_to_clean and os.path.exists(str(temp_file_to_clean)):
                try:
                    os.remove(str(temp_file_to_clean))
                except Exception as e:
                    logger.debug(f"Failed to remove temp transcoded video: {e}")

    # ── MediaPipe Tasks Pose Analysis ──────────────────────────────────────────

    def _analyze_with_mediapipe(self, video_path: Path) -> VideoMetrics:
        """
        Upper-body posture analysis using the MediaPipe Tasks PoseLandmarker API.
        Measures shoulder alignment variation and head (nose) position.
        """
        warnings = []

        base_options = mp_python.BaseOptions(model_asset_path=str(POSE_LANDMARKER_MODEL_PATH.resolve()))
        options = mp_vision.PoseLandmarkerOptions(
            base_options=base_options,
            running_mode=mp_vision.RunningMode.IMAGE,
            num_poses=1,
            min_pose_detection_confidence=0.5,
            min_pose_presence_confidence=0.5,
            min_tracking_confidence=0.5
        )

        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            return self._unavailable_metrics("Could not open video file.")

        total_frames = 0
        sampled_frames = 0
        pose_detected = 0

        shoulder_x_positions: List[float] = []
        nose_y_positions: List[float] = []
        torso_tilts: List[float] = []

        last_sample_time_ms = -1.0
        fps = cap.get(cv2.CAP_PROP_FPS)
        fallback_frame_step = max(1, int(fps / TARGET_SAMPLE_FPS)) if fps and fps > 0 else 8

        try:
            with mp_vision.PoseLandmarker.create_from_options(options) as landmarker:
                while cap.isOpened():
                    ret, frame = cap.read()
                    if not ret:
                        break
                    total_frames += 1

                    # Sample by timestamp (POS_MSEC) ~3 frames per second
                    curr_msec = cap.get(cv2.CAP_PROP_POS_MSEC)
                    if curr_msec > 0:
                        if last_sample_time_ms >= 0 and (curr_msec - last_sample_time_ms) < SAMPLE_INTERVAL_MS:
                            continue
                        last_sample_time_ms = curr_msec
                    else:
                        # Fallback to frame step if POS_MSEC is unsupported
                        if total_frames % fallback_frame_step != 0:
                            continue

                    sampled_frames += 1
                    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
                    detection_result = landmarker.detect(mp_image)

                    if detection_result.pose_landmarks and len(detection_result.pose_landmarks) > 0:
                        pose_detected += 1
                        lm = detection_result.pose_landmarks[0]

                        ls = lm[POSE_LANDMARKS["left_shoulder"]]
                        rs = lm[POSE_LANDMARKS["right_shoulder"]]
                        nose = lm[POSE_LANDMARKS["nose"]]

                        # Shoulder midpoint x (relative to frame width)
                        mid_x = (ls.x + rs.x) / 2.0
                        shoulder_x_positions.append(mid_x)

                        # Nose y position (relative to frame height)
                        nose_y_positions.append(nose.y)

                        # Shoulder tilt: vertical difference
                        tilt = abs(ls.y - rs.y)
                        torso_tilts.append(tilt)

        finally:
            cap.release()

        if sampled_frames == 0:
            return self._unavailable_metrics("No frames could be sampled from video.")

        pose_rate = pose_detected / sampled_frames if sampled_frames > 0 else 0.0

        if pose_detected == 0:
            warnings.append("No human pose landmarks detected in sampled video frames.")
            return VideoMetrics(
                frames_sampled=sampled_frames,
                frames_with_face=0,
                face_detection_rate=0.0,
                pose_detection_rate=0.0,
                face_visibility_score=0,
                attention_score=None,
                posture_score=None,
                stability_score=None,
                movement_variation=None,
                head_movement_variation=None,
                video_analysis_enabled=True,
                analysis_method="mediapipe_pose",
                analysis_warnings=warnings,
                delivery_pattern_notes=[],
                video_score=None
            )

        if pose_rate < 0.2:
            warnings.append(
                f"Pose landmarks detected in only {pose_rate:.0%} of sampled frames. "
                "Results may be unreliable — check camera position and lighting."
            )

        # ── Movement variation ────────────────────────────────────────────────
        shoulder_variation = float(np.std(shoulder_x_positions)) if shoulder_x_positions else 0.0
        head_variation = float(np.std(nose_y_positions)) if nose_y_positions else 0.0
        avg_tilt = float(np.mean(torso_tilts)) if torso_tilts else 0.0

        # ── Posture score (informational, not a competence metric) ───────────
        if avg_tilt < 0.03:
            posture_score = 92
        elif avg_tilt < 0.07:
            posture_score = 80
        else:
            posture_score = max(55, 90 - int(avg_tilt * 400))

        # ── Attention proxy (head y stability) ───────────────────────────────
        if head_variation < 0.05:
            attention_score = 88
        elif head_variation < 0.12:
            attention_score = 78
        else:
            attention_score = max(55, 90 - int(head_variation * 250))
            warnings.append(
                "High head movement detected. This may reflect natural gesturing or an unstable camera."
            )

        face_visibility_score = min(100, int(pose_rate * 100))
        stability_score = min(100, int((face_visibility_score + attention_score) / 2))

        overall = round(
            face_visibility_score * 0.30
            + attention_score     * 0.35
            + posture_score       * 0.35
        )

        delivery_notes = []
        if shoulder_variation > 0.08:
            delivery_notes.append(
                "Observable upper-body movement variation detected. "
                "This may reflect natural gesturing. No inference about emotional state is made."
            )

        return VideoMetrics(
            frames_sampled=sampled_frames,
            frames_with_face=pose_detected,
            face_detection_rate=round(pose_rate, 3),
            pose_detection_rate=round(pose_rate, 3),
            face_visibility_score=face_visibility_score,
            attention_score=attention_score,
            posture_score=posture_score,
            stability_score=stability_score,
            movement_variation=round(shoulder_variation, 4),
            head_movement_variation=round(head_variation, 4),
            video_analysis_enabled=True,
            analysis_method="mediapipe_pose",
            analysis_warnings=warnings,
            delivery_pattern_notes=delivery_notes,
            video_score=overall
        )

    # ── Haar cascade fallback ─────────────────────────────────────────────────

    def _analyze_with_haar(self, video_path: Path) -> VideoMetrics:
        """
        Face detection using OpenCV Haar cascade with bundled XML as a fallback.
        """
        warnings = ["Using Haar cascade face detection."]

        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            return self._unavailable_metrics("Could not open video file.")

        cascade_path = str(HAAR_CASCADE_MODEL_PATH.resolve()) if HAAR_CASCADE_MODEL_PATH.exists() else (
            getattr(cv2.data, "haarcascades", "") + "haarcascade_frontalface_default.xml"
        )

        if not os.path.exists(cascade_path):
            return self._unavailable_metrics("Haar cascade model XML file not found.")

        face_cascade = cv2.CascadeClassifier(cascade_path)
        if face_cascade.empty():
            return self._unavailable_metrics("Could not load Haar cascade classifier.")

        total_frames = 0
        sampled_frames = 0
        face_detected_frames = 0
        attention_scores: List[float] = []
        posture_scores: List[float] = []

        last_sample_time_ms = -1.0
        fps = cap.get(cv2.CAP_PROP_FPS)
        fallback_frame_step = max(1, int(fps / TARGET_SAMPLE_FPS)) if fps and fps > 0 else 8

        try:
            while cap.isOpened():
                ret, frame = cap.read()
                if not ret:
                    break
                total_frames += 1

                # Sample by timestamp ~3 fps
                curr_msec = cap.get(cv2.CAP_PROP_POS_MSEC)
                if curr_msec > 0:
                    if last_sample_time_ms >= 0 and (curr_msec - last_sample_time_ms) < SAMPLE_INTERVAL_MS:
                        continue
                    last_sample_time_ms = curr_msec
                else:
                    if total_frames % fallback_frame_step != 0:
                        continue

                sampled_frames += 1
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(60, 60))

                if len(faces) > 0:
                    face_detected_frames += 1
                    (x, y, w, h) = faces[0]
                    fh, fw = frame.shape[:2]

                    cx = x + w / 2
                    cy = y + h / 2
                    off_center = np.sqrt(((cx - fw / 2) / fw) ** 2 + ((cy - fh / 2) / fh) ** 2)
                    attn = max(40, 100 - int(off_center * 150))
                    attention_scores.append(attn)

                    vert_ratio = cy / fh
                    posture = 95 if 0.15 <= vert_ratio <= 0.45 else max(50, 95 - int(abs(vert_ratio - 0.3) * 120))
                    posture_scores.append(posture)
        finally:
            cap.release()

        if sampled_frames == 0:
            return self._unavailable_metrics("No frames sampled from video.")

        face_rate = face_detected_frames / sampled_frames if sampled_frames > 0 else 0.0

        if face_detected_frames == 0:
            warnings.append("No faces detected in sampled video frames.")
            return VideoMetrics(
                frames_sampled=sampled_frames,
                frames_with_face=0,
                face_detection_rate=0.0,
                pose_detection_rate=0.0,
                face_visibility_score=0,
                attention_score=None,
                posture_score=None,
                stability_score=None,
                video_analysis_enabled=True,
                analysis_method="haar_cascade",
                analysis_warnings=warnings,
                delivery_pattern_notes=[],
                video_score=None
            )
        face_vis = min(100, int(face_rate * 100))
        avg_attn = int(np.mean(attention_scores)) if attention_scores else 78
        avg_post = int(np.mean(posture_scores)) if posture_scores else 80
        stability = min(100, max(55, int((face_vis + avg_attn) / 2)))
        overall = round(face_vis * 0.30 + avg_attn * 0.35 + avg_post * 0.35)

        if face_rate < 0.3:
            warnings.append(
                f"Face detected in only {face_rate:.0%} of sampled frames. "
                "Camera angle, lighting, or face position may affect this."
            )

        return VideoMetrics(
            frames_sampled=sampled_frames,
            frames_with_face=face_detected_frames,
            face_detection_rate=round(face_rate, 3),
            pose_detection_rate=0.0,
            face_visibility_score=face_vis,
            attention_score=avg_attn,
            posture_score=avg_post,
            stability_score=stability,
            video_analysis_enabled=True,
            analysis_method="haar_cascade",
            analysis_warnings=warnings,
            delivery_pattern_notes=[],
            video_score=overall
        )

    # ── Helpers ────────────────────────────────────────────────────────────────

    def _ensure_decodable_video(self, video_path: Path) -> Tuple[Path, Optional[Path]]:
        """
        Check if OpenCV can read frames from video_path.
        If OpenCV fails to read the WebM container (e.g. missing VP9 codec in cv2),
        transcode via ffmpeg to a temporary mp4.
        Returns: (decodable_path, temp_file_to_cleanup_or_None)
        """
        if not video_path.exists():
            return video_path, None

        cap = cv2.VideoCapture(str(video_path))
        can_read = False
        if cap.isOpened():
            ret, _ = cap.read()
            if ret:
                can_read = True
        cap.release()

        if can_read:
            return video_path, None

        # Attempt ffmpeg transcode
        try:
            temp_fd, temp_path_str = tempfile.mkstemp(suffix=".mp4")
            os.close(temp_fd)
            temp_mp4 = Path(temp_path_str)

            cmd = [
                "ffmpeg", "-y", "-i", str(video_path),
                "-c:v", "libx264", "-preset", "ultrafast",
                "-an", str(temp_mp4)
            ]
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
            if temp_mp4.exists() and temp_mp4.stat().st_size > 0:
                logger.info(f"Successfully transcoded {video_path.name} to {temp_mp4.name} for OpenCV analysis.")
                return temp_mp4, temp_mp4
        except Exception as e:
            logger.warning(f"ffmpeg transcode for OpenCV decoding failed: {e}")

        return video_path, None

    def _unavailable_metrics(self, reason: str) -> VideoMetrics:
        """
        Return missing/unavailable metrics with None for scores and a clear warning.
        Does NOT invent a score or default to 0/80.
        """
        logger.warning(f"Video analysis unavailable: {reason}")
        return VideoMetrics(
            frames_sampled=0,
            frames_with_face=0,
            face_detection_rate=0.0,
            pose_detection_rate=0.0,
            face_visibility_score=None,
            attention_score=None,
            posture_score=None,
            stability_score=None,
            movement_variation=None,
            head_movement_variation=None,
            video_analysis_enabled=True,
            analysis_method="unavailable",
            analysis_warnings=[f"Video analysis unavailable: {reason}"],
            delivery_pattern_notes=[],
            video_score=None
        )


video_service = VideoService()
