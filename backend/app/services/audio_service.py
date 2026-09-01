import subprocess
import shutil
from pathlib import Path
from typing import Optional

class AudioService:
    def extract_audio_from_webm(self, video_path: Path, output_audio_path: Optional[Path] = None) -> Path:
        """Extract MP3 audio track from WebM video file using ffmpeg if installed, or return original file."""
        if not video_path.exists():
            raise FileNotFoundError(f"Video file not found at {video_path}")
            
        if output_audio_path is None:
            output_audio_path = video_path.with_suffix(".mp3")
            
        ffmpeg_bin = shutil.which("ffmpeg")
        if ffmpeg_bin:
            try:
                cmd = [
                    ffmpeg_bin, "-y", "-i", str(video_path),
                    "-vn", "-acodec", "libmp3lame", "-q:a", "2",
                    str(output_audio_path)
                ]
                subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return output_audio_path
            except Exception as e:
                print(f"ffmpeg extraction failed, using source webm: {e}")
                return video_path
        else:
            return video_path

audio_service = AudioService()
