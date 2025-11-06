"""WhisperX diarizing transcriber desktop application.

This module provides a full featured Tk/ttk user interface that wraps the
`whisperx` transcription stack while keeping the UI responsive and providing a
number of productivity improvements over the original prototype script.  The
application focuses on stability, observability, and ergonomics and exposes the
most common configuration knobs required to transcribe and diarise large batches
of audio files.

The widget hierarchy is intentionally organised so that new controls can be
added without having to rewrite sizeable portions of the codebase.  Most of the
logic has been moved into small helper classes or functions with the goal of
maximising testability and readability.
"""
from __future__ import annotations

import dataclasses
import json
import logging
import logging.handlers
import math
import os
import queue
import re
import shutil
import subprocess
import sys
import threading
import time
import traceback
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import tkinter as tk
from tkinter import filedialog, messagebox
from tkinter import ttk

# ---------------------------------------------------------------------------
# Optional third party integrations
# ---------------------------------------------------------------------------
try:  # Modern look and feel
    import ttkbootstrap as tb

    TTKB_AVAILABLE = True
except Exception:  # pragma: no cover - optional runtime dependency
    TTKB_AVAILABLE = False

try:  # Drag and drop support on Windows/macOS/Linux
    from tkinterdnd2 import DND_FILES, TkinterDnD

    TKDND_AVAILABLE = True
except Exception:  # pragma: no cover - optional runtime dependency
    TKDND_AVAILABLE = False

try:  # Lightweight audio preview
    import simpleaudio as _simpleaudio

    SIMPLEAUDIO_AVAILABLE = True
except Exception:  # pragma: no cover - optional runtime dependency
    _simpleaudio = None
    SIMPLEAUDIO_AVAILABLE = False

# On Windows, provide a no-deps fallback for audio preview
try:
    import winsound  # type: ignore[import-not-found]

    WINSOUND_AVAILABLE = True
except Exception:  # pragma: no cover - optional runtime dependency
    WINSOUND_AVAILABLE = False

# ---------------------------------------------------------------------------
# WhisperX imports are optional – we handle missing dependencies at runtime.
# ---------------------------------------------------------------------------
try:
    import torch
    import whisperx

    WHISPERX_AVAILABLE = True
    WHISPERX_IMPORT_ERROR = ""
except Exception as exc:  # pragma: no cover - depends on runtime env
    torch = None  # type: ignore[assignment]
    whisperx = None  # type: ignore[assignment]
    WHISPERX_AVAILABLE = False
    WHISPERX_IMPORT_ERROR = str(exc)

# Default token hint: do not embed secrets in code. The application reads
# Hugging Face tokens from the UI or the HUGGINGFACE_TOKEN environment variable.
HF_TOKEN_DEFAULT = ""

# ---------------------------------------------------------------------------
# Logging helpers
# ---------------------------------------------------------------------------
LOG_DIR = Path(__file__).resolve().parents[2] / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_PATH = LOG_DIR / "whisperx_app.log"

LOGGER = logging.getLogger("whisperx_app")
if not LOGGER.handlers:
    LOGGER.setLevel(logging.DEBUG)
    _handler = logging.handlers.RotatingFileHandler(  # type: ignore[attr-defined]
        LOG_PATH, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
    )
    _handler.setFormatter(
        logging.Formatter("%(asctime)s [%(levelname)s] %(threadName)s - %(message)s")
    )
    LOGGER.addHandler(_handler)
    # Console handler for quick feedback while developing – attaches to stderr
    _console = logging.StreamHandler()
    _console.setLevel(logging.INFO)
    _console.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
    LOGGER.addHandler(_console)


# ---------------------------------------------------------------------------
# Utility functions and dataclasses
# ---------------------------------------------------------------------------
@dataclass
class Segment:
    """Normalised representation of a diarised transcript segment."""

    start: float
    end: float
    speaker: str
    text: str

    def as_dict(self) -> Dict[str, object]:
        return {
            "start": round(self.start, 3),
            "end": round(self.end, 3),
            "speaker": self.speaker,
            "text": self.text,
        }


@dataclass
class TranscriptionResult:
    """Container describing artefacts produced for each audio file."""

    audio_path: Path
    transcript_path: Optional[Path] = None
    segment_path: Optional[Path] = None
    export_paths: Dict[str, Path] = field(default_factory=dict)
    segments: List[Segment] = field(default_factory=list)
    language: Optional[str] = None
    error: Optional[str] = None

    @property
    def success(self) -> bool:
        return self.error is None


@dataclass
class TranscriptionSettings:
    """High level parameters exposed to the UI."""

    model_size: str
    combine_transcripts: bool
    diarize: bool
    hf_token: str
    min_speakers: Optional[int]
    max_speakers: Optional[int]
    export_formats: Sequence[str]
    batch_size: int
    compute_type: str


@dataclass
class ParserSettings:
    """Configuration for the segment parser tab."""

    merge_threshold: float
    min_duration: float
    speaker_filter: Optional[str]
    keep_speaker_prefix: bool


SUPPORTED_AUDIO_EXTENSIONS = (
    ".wav",
    ".mp3",
    ".m4a",
    ".flac",
    ".aac",
    ".wma",
    ".ogg",
    ".opus",
    ".mp4",
)

EXPORT_FORMAT_LABELS = {
    "txt": "Plain text (.txt)",
    "srt": "SubRip (.srt)",
    "vtt": "WebVTT (.vtt)",
    "json": "JSON (.json)",
}


# ---------------------------------------------------------------------------
# Audio preparation helpers
# ---------------------------------------------------------------------------
def find_ffmpeg() -> Optional[str]:
    """Locate the ffmpeg executable if available on the host."""

    try:
        return shutil.which("ffmpeg") or shutil.which("ffmpeg.exe")
    except Exception:  # pragma: no cover - os specific
        return None


def ensure_supported_audio(path: Path, logger: logging.Logger) -> Tuple[Optional[Path], Optional[str]]:
    """Return a path that WhisperX can load, converting the file if necessary.

    If conversion is required a sibling WAV file is created.  The caller is
    responsible for managing the resulting file if temporary artefacts should be
    removed.
    """

    extension = path.suffix.lower()
    if extension in {".wav", ".mp3", ".flac", ".ogg", ".opus"}:
        return path, None

    ffmpeg = find_ffmpeg()
    if not ffmpeg:
        msg = (
            "Unsupported audio container. ffmpeg is required to convert "
            f"'{path.name}'."
        )
        logger.warning(msg)
        return None, msg

    converted_path = path.parent / f"{path.stem}_whisperx_temp.wav"
    cmd = [
        ffmpeg,
        "-y",
        "-i",
        str(path),
        "-ac",
        "1",
        "-ar",
        "16000",
        str(converted_path),
    ]
    try:
        logger.debug("Converting %s to temporary wav via ffmpeg", path)
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    except subprocess.CalledProcessError as exc:
        logger.error("ffmpeg conversion failed for %s: %s", path, exc)
        return None, f"ffmpeg conversion failed for {path.name}"
    if not converted_path.exists():
        msg = f"ffmpeg conversion for {path.name} did not create a wav file"
        logger.error(msg)
        return None, msg
    return converted_path, None


# ---------------------------------------------------------------------------
# Export helpers
# ---------------------------------------------------------------------------
def _format_timestamp(seconds: float) -> str:
    seconds = max(0.0, float(seconds))
    millis = int(round((seconds - math.floor(seconds)) * 1000))
    hours, remainder = divmod(int(seconds), 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def render_srt(segments: Sequence[Segment]) -> str:
    lines: List[str] = []
    for idx, seg in enumerate(segments, start=1):
        lines.append(str(idx))
        lines.append(f"{_format_timestamp(seg.start)} --> {_format_timestamp(seg.end)}")
        speaker_prefix = f"{seg.speaker}: " if seg.speaker else ""
        lines.append(f"{speaker_prefix}{seg.text}".strip())
        lines.append("")
    return "\n".join(lines)


def render_vtt(segments: Sequence[Segment]) -> str:
    lines = ["WEBVTT", ""]
    for seg in segments:
        start = _format_timestamp(seg.start).replace(",", ".")
        end = _format_timestamp(seg.end).replace(",", ".")
        speaker_prefix = f"{seg.speaker}: " if seg.speaker else ""
        lines.append(f"{start} --> {end}")
        lines.append(f"{speaker_prefix}{seg.text}".strip())
        lines.append("")
    return "\n".join(lines)


def render_json(segments: Sequence[Segment], language: Optional[str]) -> str:
    payload = {
        "language": language or "unknown",
        "segments": [seg.as_dict() for seg in segments],
    }
    return json.dumps(payload, indent=2, ensure_ascii=False)


def write_exports(base_path: Path, segments: Sequence[Segment], language: Optional[str], formats: Sequence[str]) -> Dict[str, Path]:
    outputs: Dict[str, Path] = {}
    for fmt in formats:
        fmt = fmt.lower()
        if fmt not in EXPORT_FORMAT_LABELS:
            continue
        if fmt == "txt":
            target = base_path.with_suffix(".txt")
            with target.open("w", encoding="utf-8") as fh:
                for seg in segments:
                    speaker = seg.speaker or "SPEAKER"
                    fh.write(f"[{seg.start:.2f} - {seg.end:.2f}] {speaker}: {seg.text}\n")
            outputs[fmt] = target
        elif fmt == "srt":
            target = base_path.with_suffix(".srt")
            target.write_text(render_srt(segments), encoding="utf-8")
            outputs[fmt] = target
        elif fmt == "vtt":
            target = base_path.with_suffix(".vtt")
            target.write_text(render_vtt(segments), encoding="utf-8")
            outputs[fmt] = target
        elif fmt == "json":
            target = base_path.with_suffix(".json")
            target.write_text(render_json(segments, language), encoding="utf-8")
            outputs[fmt] = target
    return outputs


# ---------------------------------------------------------------------------
# WhisperX worker thread
# ---------------------------------------------------------------------------
class WhisperXWorker(threading.Thread):
    """Background worker that performs the heavy transcription lifting."""

    def __init__(
        self,
        files: Sequence[Path],
        settings: TranscriptionSettings,
        ui_queue: "queue.Queue[Tuple[str, object]]",
        cancel_event: threading.Event,
        logger: logging.Logger,
    ) -> None:
        super().__init__(daemon=True, name="WhisperXWorker")
        self.files = list(files)
        self.settings = settings
        self.ui_queue = ui_queue
        self.cancel_event = cancel_event
        self.logger = logger
        self.align_cache: Dict[str, Tuple[object, object]] = {}

    # ----------------------------- helpers -----------------------------
    def _load_model(self) -> object:
        device = "cuda" if torch is not None and torch.cuda.is_available() else "cpu"
        compute_type = self.settings.compute_type
        try:
            model = whisperx.load_model(self.settings.model_size, device, compute_type=compute_type)
        except Exception:
            model = whisperx.load_model(self.settings.model_size, device, compute_type="float32")
        return model

    def _load_align(self, language: str, device: str) -> Tuple[object, object]:
        if language in self.align_cache:
            return self.align_cache[language]
        model_a, metadata = whisperx.load_align_model(language_code=language, device=device)
        self.align_cache[language] = (model_a, metadata)
        return model_a, metadata

    def _load_diarization(self, device: str) -> Optional[object]:
        if not self.settings.diarize:
            return None
        token = self.settings.hf_token or os.environ.get("HUGGINGFACE_TOKEN", "")
        if not token:
            return None
        try:
            if hasattr(whisperx, "DiarizationPipeline"):
                return whisperx.DiarizationPipeline(use_auth_token=token, device=device)
            from pyannote.audio import Pipeline as _PyannotePipeline  # type: ignore

            pipeline = _PyannotePipeline.from_pretrained(
                "pyannote/speaker-diarization-3.1", use_auth_token=token
            )
            try:
                pipeline.to(device)
            except Exception:
                pass
            return pipeline
        except Exception as exc:
            self.logger.error("Failed to initialise diarization pipeline: %s", exc)
            return None

    # --------------------- diarization fallbacks ---------------------
    def _norm_speaker(self, label: object) -> str:
        """Normalise speaker labels to a consistent form like SPEAKER_00.

        Accepts any object and tries to coerce to a stable label. If the
        label contains a number, zero-pad to two digits.
        """
        try:
            text = str(label or "").strip()
            if not text:
                return "SPEAKER_00"
            import re as _re

            m = _re.search(r"(\d+)$", text)
            if m:
                return f"SPEAKER_{int(m.group(1)):02d}"
            if text.upper().startswith("SPEAKER_"):
                # Keep as-is to avoid surprising users
                return text
            return text
        except Exception:
            return "SPEAKER_00"

    def _extract_diar_spans(self, diarize_result: object) -> List[Tuple[float, float, str]]:
        """Extract diarization spans as (start, end, speaker).

        Supports pyannote Annotation objects and simple dict/list formats.
        """
        spans: List[Tuple[float, float, str]] = []

        # pyannote.core.Annotation: prefer itertracks with labels
        try:
            if hasattr(diarize_result, "itertracks"):
                for seg, _track, label in diarize_result.itertracks(yield_label=True):  # type: ignore[attr-defined]
                    start = float(getattr(seg, "start", 0.0))
                    end = float(getattr(seg, "end", start))
                    spans.append((start, end, self._norm_speaker(label)))
        except Exception:
            pass

        # Some pipelines may expose .get_timeline / .itersegments without labels
        if not spans:
            try:
                if hasattr(diarize_result, "itersegments"):
                    for seg in diarize_result.itersegments():  # type: ignore[attr-defined]
                        start = float(getattr(seg, "start", 0.0))
                        end = float(getattr(seg, "end", start))
                        spans.append((start, end, "SPEAKER_00"))
            except Exception:
                pass

        # Dict format: {"segments": [{start, end, speaker?}, ...]}
        if not spans and isinstance(diarize_result, dict):
            items = diarize_result.get("segments")
            if isinstance(items, list):
                for it in items:
                    try:
                        start = float(it.get("start", 0.0))
                        end = float(it.get("end", start))
                        speaker = self._norm_speaker(it.get("speaker"))
                        spans.append((start, end, speaker))
                    except Exception:
                        continue

        # Simple list of segments [{start,end,speaker}]
        if not spans and isinstance(diarize_result, list):
            for it in diarize_result:
                try:
                    start = float(getattr(it, "start", it.get("start", 0.0)))  # type: ignore[union-attr]
                    end = float(getattr(it, "end", it.get("end", start)))  # type: ignore[union-attr]
                    speaker = self._norm_speaker(getattr(it, "speaker", it.get("speaker", None)))  # type: ignore[union-attr]
                    spans.append((start, end, speaker))
                except Exception:
                    continue

        # Sort for binary-search like lookups later
        spans.sort(key=lambda x: (x[0], x[1]))
        return spans

    def _assign_speakers_fallback(self, aligned: dict, spans: Sequence[Tuple[float, float, str]]) -> dict:
        """Attach speakers to words/segments based on diarization spans.

        Strategy: assign by word midpoint to containing diarization span.
        """
        if not spans:
            return aligned

        def lookup_speaker(ts: float) -> str:
            # Linear scan is fine for typical segment counts; could binary-search if large
            for s, e, spk in spans:
                if s <= ts <= e:
                    return spk
            return "SPEAKER_00"

        diarized = {k: v for k, v in aligned.items()}
        new_segments: List[dict] = []
        for seg in aligned.get("segments", []):
            seg_start = float(seg.get("start", 0.0))
            seg_end = float(seg.get("end", seg_start))
            words = seg.get("words") or []
            seg_copy = dict(seg)
            if words:
                new_words = []
                speaker_counts: Dict[str, int] = {}
                for w in words:
                    try:
                        ws = float(w.get("start", seg_start))
                        we = float(w.get("end", seg_end))
                        mid = (ws + we) / 2.0
                        spk = lookup_speaker(mid)
                        speaker_counts[spk] = speaker_counts.get(spk, 0) + 1
                        w2 = dict(w)
                        w2["speaker"] = spk
                        new_words.append(w2)
                    except Exception:
                        new_words.append(w)
                # Majority vote for segment-level speaker
                seg_speaker = max(speaker_counts.items(), key=lambda kv: kv[1])[0] if speaker_counts else "SPEAKER_00"
                seg_copy["words"] = new_words
                seg_copy["speaker"] = seg_copy.get("speaker") or seg_speaker
            else:
                # No words: assign based on segment midpoint
                mid = (seg_start + seg_end) / 2.0
                seg_copy["speaker"] = seg_copy.get("speaker") or lookup_speaker(mid)
            new_segments.append(seg_copy)

        diarized["segments"] = new_segments
        return diarized

    def _try_assign_speakers(self, diarize_result: object, aligned: dict) -> Optional[dict]:
        """Try whisperx assignment, then custom fallback. Returns None on failure."""
        try:
            return whisperx.assign_word_speakers(diarize_result, aligned)  # type: ignore[no-any-return]
        except Exception as exc:
            self.logger.error("Failed to assign diarized speakers (whisperx): %s", exc)
            try:
                spans = self._extract_diar_spans(diarize_result)
                if not spans:
                    return None
                return self._assign_speakers_fallback(aligned, spans)
            except Exception as exc2:
                self.logger.error("Fallback speaker assignment failed: %s", exc2)
                return None

    def _yield_segments(self, diarized_result: dict) -> List[Segment]:
        segments: List[Segment] = []
        for seg in diarized_result.get("segments", []):
            seg_start = float(seg.get("start", 0.0))
            seg_end = float(seg.get("end", seg_start))
            seg_speaker = seg.get("speaker") or "SPEAKER_00"
            words = seg.get("words") or []
            if words:
                current_speaker = None
                current_tokens: List[str] = []
                current_start = seg_start
                current_end = seg_end

                def flush() -> None:
                    if not current_tokens:
                        return
                    text = " ".join(current_tokens).strip()
                    segments.append(
                        Segment(start=current_start, end=current_end, speaker=current_speaker or seg_speaker, text=text)
                    )

                for word in words:
                    w_speaker = word.get("speaker") or seg_speaker
                    w_text = (word.get("word") or word.get("text") or "").strip()
                    if not w_text:
                        continue
                    w_start = float(word.get("start", seg_start))
                    w_end = float(word.get("end", seg_end))
                    if current_speaker is None:
                        current_speaker = w_speaker
                        current_tokens = [w_text]
                        current_start = w_start
                        current_end = w_end
                        continue
                    if w_speaker == current_speaker:
                        current_tokens.append(w_text)
                        current_end = w_end
                    else:
                        flush()
                        current_speaker = w_speaker
                        current_tokens = [w_text]
                        current_start = w_start
                        current_end = w_end
                flush()
            else:
                text = (seg.get("text") or "").strip()
                segments.append(Segment(start=seg_start, end=seg_end, speaker=seg_speaker, text=text))
        return segments

    # ------------------------------ run -------------------------------
    def run(self) -> None:  # pragma: no cover - requires whisperx runtime
        if not WHISPERX_AVAILABLE:
            self.ui_queue.put(
                (
                    "fatal",
                    f"WhisperX or Torch is not installed. Import error: {WHISPERX_IMPORT_ERROR}",
                )
            )
            return

        start_time = time.time()
        device = "cuda" if torch is not None and torch.cuda.is_available() else "cpu"
        self.ui_queue.put(("status", f"Loading WhisperX model ({self.settings.model_size}) on {device}..."))
        try:
            model = self._load_model()
        except Exception as exc:  # pragma: no cover - runtime failure
            self.logger.exception("Failed to load WhisperX model")
            self.ui_queue.put(("fatal", f"Failed to load WhisperX model: {exc}"))
            return

        diarization_pipeline = self._load_diarization(device)
        if self.settings.diarize and diarization_pipeline is None:
            self.ui_queue.put(("warning", "Diarization pipeline could not be initialised; continuing without it."))

        processed: List[TranscriptionResult] = []
        for index, audio_path in enumerate(self.files, start=1):
            if self.cancel_event.is_set():
                break
            progress = index - 1
            self.ui_queue.put(("progress", (progress, len(self.files), time.time() - start_time)))
            self.ui_queue.put(("status", f"Processing {audio_path.name} ({index}/{len(self.files)})"))
            prepared_path: Optional[Path] = None
            try:
                prepared_path, warn_msg = ensure_supported_audio(audio_path, self.logger)
                if warn_msg:
                    self.ui_queue.put(("warning", warn_msg))
                if prepared_path is None:
                    raise RuntimeError(warn_msg or "Unsupported audio format")
                self.logger.info("Transcribing %s", audio_path)
                audio = whisperx.load_audio(str(prepared_path))
                result = model.transcribe(audio, batch_size=self.settings.batch_size)

                language = result.get("language") or "en"
                model_a, metadata = self._load_align(language, device)
                aligned = whisperx.align(
                    result["segments"], model_a, metadata, audio, device, return_char_alignments=False
                )

                diarized = aligned
                if diarization_pipeline is not None:
                    diarize_kwargs = {}
                    if self.settings.min_speakers is not None:
                        diarize_kwargs["min_speakers"] = self.settings.min_speakers
                    if self.settings.max_speakers is not None:
                        diarize_kwargs["max_speakers"] = self.settings.max_speakers
                    try:
                        diarize_result = diarization_pipeline(str(prepared_path), **diarize_kwargs)
                    except TypeError:
                        diarize_result = diarization_pipeline(str(prepared_path))

                    assigned = self._try_assign_speakers(diarize_result, aligned)
                    if assigned is None:
                        self.ui_queue.put(("warning", f"Speaker assignment failed for {audio_path.name}; continuing without labels."))
                        diarized = aligned
                    else:
                        diarized = assigned

                segments = self._yield_segments(diarized)
                base_name = audio_path.stem
                output_dir = audio_path.parent
                transcript_path = output_dir / f"{base_name}_transcript.txt"
                segment_path = output_dir / f"{base_name}_segments.txt"

                transcript_header = (
                    f"===== Transcription for {audio_path.name} - {time.strftime('%Y-%m-%d %H:%M:%S')} =====\n\n"
                )
                with transcript_path.open("w", encoding="utf-8") as handle:
                    handle.write(transcript_header)
                    for seg in segments:
                        handle.write(f"[{seg.start:.2f} - {seg.end:.2f}] {seg.speaker}: {seg.text}\n")
                with segment_path.open("w", encoding="utf-8") as handle:
                    for seg in segments:
                        handle.write(f"[{seg.start:.2f} - {seg.end:.2f}] {seg.speaker}: {seg.text}\n")

                export_paths = write_exports(
                    output_dir / base_name, segments, language, self.settings.export_formats
                )
                processed.append(
                    TranscriptionResult(
                        audio_path=audio_path,
                        transcript_path=transcript_path,
                        segment_path=segment_path,
                        export_paths=export_paths,
                        segments=segments,
                        language=language,
                    )
                )
                self.ui_queue.put(("file-complete", processed[-1]))
                self.ui_queue.put(("progress", (index, len(self.files), time.time() - start_time)))
            except Exception as exc:  # pragma: no cover - runtime failure
                self.logger.exception("Transcription failed for %s", audio_path)
                processed.append(TranscriptionResult(audio_path=audio_path, error=str(exc)))
                self.ui_queue.put(("error", (audio_path, str(exc), traceback.format_exc())))
            finally:
                if prepared_path is not None and prepared_path != audio_path and prepared_path.exists():
                    try:
                        prepared_path.unlink()
                    except Exception:
                        pass

        self.ui_queue.put(("progress", (len(processed), len(self.files), time.time() - start_time)))
        if self.settings.combine_transcripts:
            combined_segments: List[Segment] = [seg for result in processed if result.success for seg in result.segments]
            if combined_segments:
                combined_dir = self.files[0].parent
                timestamp = time.strftime("%Y%m%d_%H%M%S")
                combined_base = combined_dir / f"combined_transcript_{timestamp}"
                combined_txt = combined_base.with_suffix(".txt")
                with combined_txt.open("w", encoding="utf-8") as fh:
                    fh.write("===== Combined transcript =====\n\n")
                    for seg in combined_segments:
                        fh.write(f"[{seg.start:.2f} - {seg.end:.2f}] {seg.speaker}: {seg.text}\n")
                other_formats = [fmt for fmt in self.settings.export_formats if fmt != "txt"]
                combined_exports = write_exports(combined_base, combined_segments, None, other_formats)
                combined_exports["txt"] = combined_txt
                self.ui_queue.put(("combined", combined_exports))
        duration = time.time() - start_time
        self.ui_queue.put(("completed", (processed, duration)))


# ---------------------------------------------------------------------------
# Segment parsing utilities
# ---------------------------------------------------------------------------
def parse_segment_lines(lines: Iterable[str]) -> List[Segment]:
    segments: List[Segment] = []
    pattern = re.compile(
        r"\[(?P<start>[0-9]+(?:\.[0-9]+)?)\s*-\s*(?P<end>[0-9]+(?:\.[0-9]+)?)\]\s*(?:(?P<speaker>[^:]+):)?\s*(?P<text>.*)"
    )
    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            continue
        match = pattern.match(line)
        if not match:
            continue
        try:
            start = float(match.group("start"))
            end = float(match.group("end"))
            if end <= start:
                continue
        except (TypeError, ValueError):
            continue
        speaker = (match.group("speaker") or "").strip()
        text = (match.group("text") or "").strip()
        segments.append(Segment(start=start, end=end, speaker=speaker, text=text))
    return segments


def merge_segments(segments: Sequence[Segment], settings: ParserSettings) -> List[Segment]:
    if not segments:
        return []
    merged: List[Segment] = []
    current: Optional[Segment] = dataclasses.replace(segments[0])

    def eligible(seg: Segment) -> bool:
        if settings.speaker_filter and settings.speaker_filter.lower() not in seg.speaker.lower():
            return False
        duration = seg.end - seg.start
        return duration >= settings.min_duration

    if current is not None and not eligible(current):
        current = None

    for next_seg in segments[1:]:
        if current is not None:
            gap = next_seg.start - current.end
            same_speaker = (current.speaker == next_seg.speaker) or not settings.keep_speaker_prefix
            if gap <= settings.merge_threshold and same_speaker:
                current.end = next_seg.end
                if next_seg.text:
                    current.text = (current.text + " " + next_seg.text).strip()
                continue
            if eligible(current):
                merged.append(dataclasses.replace(current))
            current = dataclasses.replace(next_seg)
        else:
            current = dataclasses.replace(next_seg)
    if current is not None and eligible(current):
        merged.append(current)
    if not settings.keep_speaker_prefix:
        for seg in merged:
            seg.speaker = ""
    return merged


# ---------------------------------------------------------------------------
# UI application class
# ---------------------------------------------------------------------------
class WhisperXApp:
    """Tkinter based desktop application for WhisperX transcription."""

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.logger = LOGGER
        self.logger.info("Starting WhisperX UI")
        self.progress_queue: "queue.Queue[Tuple[str, object]]" = queue.Queue()
        self.cancel_event = threading.Event()
        self.worker: Optional[WhisperXWorker] = None

        self.selected_files: List[Path] = []
        self._audio_preview_wave: Optional[_simpleaudio.PlayObject] = None
        self._build_style()
        self._build_variables()
        self._build_layout()
        self._poll_queue()

    # ------------------------------------------------------------------
    # UI construction helpers
    # ------------------------------------------------------------------
    def _build_style(self) -> None:
        self.root.title("WhisperX Diarizing Transcriber")
        self.root.minsize(940, 640)
        if TKDND_AVAILABLE:
            self.root = self.root  # type: ignore[self-assign]
        if TTKB_AVAILABLE:
            self.style = tb.Style("darkly")
        else:
            self.style = ttk.Style()
            try:
                self.style.theme_use("clam")
            except Exception:
                pass
        for i in range(4):
            self.root.grid_columnconfigure(i, weight=1)
        for i in range(3):
            self.root.grid_rowconfigure(i, weight=1)

    def _build_variables(self) -> None:
        default_token = os.environ.get("HUGGINGFACE_TOKEN", HF_TOKEN_DEFAULT)
        self.model_size = tk.StringVar(value="large-v2")
        self.combine_var = tk.BooleanVar(value=False)
        self.diarize_var = tk.BooleanVar(value=True)
        self.hf_token_var = tk.StringVar(value=default_token)
        self.min_speakers_var = tk.StringVar()
        self.max_speakers_var = tk.StringVar()
        self.batch_size_var = tk.StringVar(value="16")
        self.compute_type_var = tk.StringVar(value="float16")

        self.merge_threshold_var = tk.StringVar(value="1.0")
        self.min_duration_var = tk.StringVar(value="0.4")
        self.speaker_filter_var = tk.StringVar()
        self.keep_speaker_prefix_var = tk.BooleanVar(value=True)

        self.status_var = tk.StringVar(value="Select audio files to begin")
        self.eta_var = tk.StringVar(value="ETA: --")
        self.transcript_path_var = tk.StringVar()
        self.segment_path_var = tk.StringVar()
        self.parsed_segment_path_var = tk.StringVar()
        self.combined_path_var = tk.StringVar()

        self.export_format_vars: Dict[str, tk.BooleanVar] = {
            fmt: tk.BooleanVar(value=(fmt == "txt")) for fmt in EXPORT_FORMAT_LABELS
        }

    def _build_layout(self) -> None:
        container = ttk.Frame(self.root, padding=12)
        container.grid(row=0, column=0, sticky="nsew")
        container.grid_columnconfigure(0, weight=1)
        container.grid_rowconfigure(1, weight=1)

        header = ttk.Frame(container)
        header.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        header.grid_columnconfigure(1, weight=1)

        title_lbl = ttk.Label(
            header,
            text="WhisperX Diarizing Transcriber",
            font=("Segoe UI", 16, "bold"),
        )
        title_lbl.grid(row=0, column=0, sticky="w")

        theme_btn = ttk.Button(header, text="Switch Theme", command=self._switch_theme)
        theme_btn.grid(row=0, column=1, sticky="e")

        notebook = ttk.Notebook(container)
        notebook.grid(row=1, column=0, sticky="nsew")

        transcribe_tab = ttk.Frame(notebook, padding=10)
        parser_tab = ttk.Frame(notebook, padding=10)
        logs_tab = ttk.Frame(notebook, padding=10)
        notebook.add(transcribe_tab, text="Transcription")
        notebook.add(parser_tab, text="Segment Parser")
        notebook.add(logs_tab, text="Logs & Settings")

        self._build_transcription_tab(transcribe_tab)
        self._build_parser_tab(parser_tab)
        self._build_logs_tab(logs_tab)

    def _build_transcription_tab(self, parent: ttk.Frame) -> None:
        parent.grid_columnconfigure(0, weight=1)
        parent.grid_columnconfigure(1, weight=1)
        parent.grid_rowconfigure(3, weight=1)

        # Model & diarization configuration -------------------------------------------------
        model_frame = ttk.LabelFrame(parent, text="Model", padding=10)
        model_frame.grid(row=0, column=0, columnspan=2, sticky="ew")
        model_frame.grid_columnconfigure(1, weight=1)

        ttk.Label(model_frame, text="Model size:").grid(row=0, column=0, sticky="w")
        ttk.Combobox(
            model_frame,
            textvariable=self.model_size,
            values=["tiny", "base", "small", "medium", "large-v2", "large"],
            state="readonly",
            width=12,
        ).grid(row=0, column=1, sticky="w", padx=(4, 20))

        ttk.Label(model_frame, text="Batch size:").grid(row=0, column=2, sticky="w")
        ttk.Spinbox(
            model_frame,
            from_=4,
            to=64,
            increment=4,
            textvariable=self.batch_size_var,
            width=6,
        ).grid(row=0, column=3, sticky="w", padx=(4, 20))

        ttk.Label(model_frame, text="Compute type:").grid(row=0, column=4, sticky="w")
        ttk.Combobox(
            model_frame,
            textvariable=self.compute_type_var,
            values=["float16", "float32", "int8"],
            state="readonly",
            width=8,
        ).grid(row=0, column=5, sticky="w", padx=(4, 0))

        ttk.Checkbutton(
            model_frame,
            text="Combine transcripts",
            variable=self.combine_var,
        ).grid(row=1, column=0, columnspan=2, sticky="w", pady=(6, 0))

        ttk.Checkbutton(
            model_frame,
            text="Enable diarization",
            variable=self.diarize_var,
        ).grid(row=1, column=2, sticky="w", pady=(6, 0))

        ttk.Label(model_frame, text="HF token:").grid(row=2, column=0, sticky="w", pady=(6, 0))
        ttk.Entry(model_frame, textvariable=self.hf_token_var, width=48).grid(
            row=2, column=1, columnspan=5, sticky="ew", pady=(6, 0)
        )

        ttk.Label(model_frame, text="Min speakers:").grid(row=3, column=0, sticky="w", pady=(6, 0))
        ttk.Entry(model_frame, textvariable=self.min_speakers_var, width=6).grid(row=3, column=1, sticky="w")
        ttk.Label(model_frame, text="Max speakers:").grid(row=3, column=2, sticky="w")
        ttk.Entry(model_frame, textvariable=self.max_speakers_var, width=6).grid(row=3, column=3, sticky="w")

        # File selection -------------------------------------------------------------------
        files_frame = ttk.LabelFrame(parent, text="Audio files", padding=10)
        files_frame.grid(row=1, column=0, sticky="nsew", pady=(10, 0))
        files_frame.grid_rowconfigure(1, weight=1)
        files_frame.grid_columnconfigure(0, weight=1)

        btn_frame = ttk.Frame(files_frame)
        btn_frame.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        ttk.Button(btn_frame, text="Add files", command=self._browse_audio).grid(row=0, column=0, padx=(0, 6))
        ttk.Button(btn_frame, text="Clear list", command=self._clear_files).grid(row=0, column=1)
        ttk.Button(btn_frame, text="Remove selected", command=self._remove_selected).grid(row=0, column=2, padx=(6, 0))
        ttk.Button(
            btn_frame,
            text="Preview",
            command=self._preview_selected,
            state=tk.NORMAL if (SIMPLEAUDIO_AVAILABLE or WINSOUND_AVAILABLE) else tk.DISABLED,
        ).grid(row=0, column=3, padx=(6, 0))

        files_container = tk.Frame(files_frame, bd=1, relief=tk.SOLID)
        files_container.grid(row=1, column=0, sticky="nsew")
        files_container.grid_rowconfigure(0, weight=1)
        files_container.grid_columnconfigure(0, weight=1)

        self.file_list = tk.Listbox(files_container, selectmode=tk.EXTENDED)
        self.file_list.grid(row=0, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(files_container, orient="vertical", command=self.file_list.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.file_list.configure(yscrollcommand=scrollbar.set)
        if TKDND_AVAILABLE:
            for widget in (files_container, self.file_list):
                widget.drop_target_register(DND_FILES)
                widget.dnd_bind("<<Drop>>", self._on_drop_files)
                widget.dnd_bind("<<DragEnter>>", self._on_drag_enter)
                widget.dnd_bind("<<DragLeave>>", self._on_drag_leave)

        # Progress -------------------------------------------------------------------------
        progress_frame = ttk.LabelFrame(parent, text="Progress", padding=10)
        progress_frame.grid(row=1, column=1, sticky="nsew", padx=(10, 0), pady=(10, 0))
        progress_frame.grid_columnconfigure(0, weight=1)

        ttk.Button(progress_frame, text="Start transcription", command=self._start_transcription).grid(
            row=0, column=0, sticky="ew"
        )
        ttk.Button(progress_frame, text="Cancel", command=self._cancel_transcription).grid(
            row=0, column=1, sticky="ew", padx=(8, 0)
        )

        self.progress_bar = ttk.Progressbar(progress_frame, maximum=100)
        self.progress_bar.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(10, 4))

        self.status_label = ttk.Label(progress_frame, textvariable=self.status_var, wraplength=320)
        self.status_label.grid(row=2, column=0, columnspan=2, sticky="w")
        ttk.Label(progress_frame, textvariable=self.eta_var).grid(row=3, column=0, columnspan=2, sticky="w")

        ttk.Label(progress_frame, text="Transcript file:").grid(row=4, column=0, sticky="w", pady=(12, 0))
        ttk.Entry(progress_frame, textvariable=self.transcript_path_var, state="readonly").grid(
            row=4, column=1, sticky="ew", pady=(12, 0)
        )
        ttk.Label(progress_frame, text="Segments file:").grid(row=5, column=0, sticky="w", pady=(6, 0))
        ttk.Entry(progress_frame, textvariable=self.segment_path_var, state="readonly").grid(
            row=5, column=1, sticky="ew", pady=(6, 0)
        )

        ttk.Label(progress_frame, text="Combined output:").grid(row=6, column=0, sticky="w", pady=(6, 0))
        ttk.Entry(progress_frame, textvariable=self.combined_path_var, state="readonly").grid(
            row=6, column=1, sticky="ew", pady=(6, 0)
        )

        ttk.Button(progress_frame, text="Open output folder", command=self._open_output_directory).grid(
            row=7, column=0, columnspan=2, sticky="ew", pady=(10, 0)
        )

        # Export format controls -----------------------------------------------------------
        export_frame = ttk.LabelFrame(parent, text="Export formats", padding=10)
        export_frame.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        for idx, (fmt, label) in enumerate(EXPORT_FORMAT_LABELS.items()):
            ttk.Checkbutton(export_frame, text=label, variable=self.export_format_vars[fmt]).grid(
                row=0, column=idx, padx=(0, 12), sticky="w"
            )

    def _build_parser_tab(self, parent: ttk.Frame) -> None:
        parent.grid_columnconfigure(0, weight=1)
        parent.grid_rowconfigure(2, weight=1)

        controls = ttk.Frame(parent)
        controls.grid(row=0, column=0, sticky="ew")
        controls.grid_columnconfigure(8, weight=1)

        ttk.Label(controls, text="Segments file:").grid(row=0, column=0, sticky="w")
        ttk.Entry(controls, textvariable=self.segment_path_var, state="readonly").grid(
            row=0, column=1, columnspan=4, sticky="ew", padx=(4, 6)
        )
        ttk.Button(controls, text="Browse", command=self._browse_segments_file).grid(row=0, column=5)

        ttk.Label(controls, text="Merge gap (s):").grid(row=1, column=0, sticky="w", pady=(8, 0))
        ttk.Entry(controls, textvariable=self.merge_threshold_var, width=6).grid(
            row=1, column=1, sticky="w", pady=(8, 0)
        )
        ttk.Label(controls, text="Min duration (s):").grid(row=1, column=2, sticky="w", pady=(8, 0))
        ttk.Entry(controls, textvariable=self.min_duration_var, width=6).grid(
            row=1, column=3, sticky="w", pady=(8, 0)
        )
        ttk.Label(controls, text="Speaker filter:").grid(row=1, column=4, sticky="w", pady=(8, 0))
        ttk.Entry(controls, textvariable=self.speaker_filter_var, width=12).grid(
            row=1, column=5, sticky="w", pady=(8, 0)
        )
        ttk.Checkbutton(
            controls,
            text="Keep speaker prefix",
            variable=self.keep_speaker_prefix_var,
        ).grid(row=1, column=6, padx=(10, 0), sticky="w", pady=(8, 0))

        ttk.Button(controls, text="Parse segments", command=self._parse_segments).grid(
            row=1, column=7, padx=(10, 0), pady=(8, 0)
        )

        output_frame = ttk.Frame(parent)
        output_frame.grid(row=2, column=0, sticky="nsew", pady=(10, 0))
        output_frame.grid_rowconfigure(0, weight=1)
        output_frame.grid_columnconfigure(0, weight=1)

        self.parser_output = tk.Text(output_frame, wrap="word")
        self.parser_output.grid(row=0, column=0, sticky="nsew")
        ttk.Scrollbar(output_frame, orient="vertical", command=self.parser_output.yview).grid(
            row=0, column=1, sticky="ns"
        )
        self.parser_output.configure(state="disabled")

        ttk.Entry(parent, textvariable=self.parsed_segment_path_var, state="readonly").grid(
            row=3, column=0, sticky="ew", pady=(10, 0)
        )

    def _build_logs_tab(self, parent: ttk.Frame) -> None:
        parent.grid_columnconfigure(0, weight=1)
        parent.grid_rowconfigure(0, weight=1)

        text = tk.Text(parent, wrap="word", height=10)
        text.grid(row=0, column=0, sticky="nsew")
        scroll = ttk.Scrollbar(parent, orient="vertical", command=text.yview)
        scroll.grid(row=0, column=1, sticky="ns")
        text.configure(yscrollcommand=scroll.set, state="disabled")
        self.log_view = text

        button_frame = ttk.Frame(parent)
        button_frame.grid(row=1, column=0, sticky="ew", pady=(8, 0))
        ttk.Button(button_frame, text="Refresh logs", command=self._refresh_logs).grid(row=0, column=0)
        ttk.Button(button_frame, text="Open log file", command=self._open_log_file).grid(row=0, column=1, padx=(8, 0))
        ttk.Button(button_frame, text="Copy debug info", command=self._copy_debug_info).grid(row=0, column=2, padx=(8, 0))

        self._refresh_logs()

    # ------------------------------------------------------------------
    # Event handlers and helpers
    # ------------------------------------------------------------------
    def _switch_theme(self) -> None:
        if not TTKB_AVAILABLE:
            messagebox.showinfo("Theme", "Install ttkbootstrap to unlock additional themes.")
            return
        themes = self.style.theme_names()
        current = self.style.theme.name
        try:
            next_index = (themes.index(current) + 1) % len(themes)
        except ValueError:
            next_index = 0
        self.style.theme_use(themes[next_index])

    def _browse_audio(self) -> None:
        paths = filedialog.askopenfilenames(
            title="Select audio files",
            filetypes=[("Audio", " ".join(f"*{ext}" for ext in SUPPORTED_AUDIO_EXTENSIONS))],
        )
        if not paths:
            return
        for path in map(Path, paths):
            if path not in self.selected_files:
                self.selected_files.append(path)
        self._refresh_file_list()

    def _remove_selected(self) -> None:
        selection = list(self.file_list.curselection())
        if not selection:
            return
        for index in reversed(selection):
            try:
                del self.selected_files[index]
            except IndexError:
                continue
        self._refresh_file_list()

    def _clear_files(self) -> None:
        self.selected_files.clear()
        self._refresh_file_list()

    def _refresh_file_list(self) -> None:
        self.file_list.delete(0, tk.END)
        for path in self.selected_files:
            self.file_list.insert(tk.END, path.name)
        self.status_var.set(f"{len(self.selected_files)} file(s) ready for transcription")

    def _on_drag_enter(self, event: tk.Event) -> None:
        event.widget.configure(bg="#eaf7ff")

    def _on_drag_leave(self, event: tk.Event) -> None:
        event.widget.configure(bg=self.root.cget("bg"))

    def _on_drop_files(self, event: tk.Event) -> None:
        event.widget.configure(bg=self.root.cget("bg"))
        raw = event.data
        if not raw:
            return
        candidates = re.findall(r"\{.*?\}|[^\s]+", raw)
        new_files = []
        for candidate in candidates:
            candidate = candidate.strip("{}")
            path = Path(candidate)
            if path.is_file() and path.suffix.lower() in SUPPORTED_AUDIO_EXTENSIONS:
                new_files.append(path)
        for path in new_files:
            if path not in self.selected_files:
                self.selected_files.append(path)
        if new_files:
            self._refresh_file_list()

    def _preview_selected(self) -> None:
        # Stop any currently playing audio
        if self._audio_preview_wave is not None:
            try:
                self._audio_preview_wave.stop()
            except Exception:
                pass
            self._audio_preview_wave = None
        elif 'WINSOUND_AVAILABLE' in globals() and WINSOUND_AVAILABLE:
            try:
                winsound.PlaySound(None, winsound.SND_PURGE)
            except Exception:
                pass
        selection = self.file_list.curselection()
        if not selection:
            messagebox.showinfo("Preview", "Select an audio file to preview.")
            return
        path = self.selected_files[selection[0]]
        prepared_path, warn = ensure_supported_audio(path, self.logger)
        if warn:
            self.status_var.set(warn)
        if prepared_path is None or not prepared_path.exists():
            messagebox.showerror("Preview", f"Cannot preview {path.name} (conversion failed).")
            return
        # Play using available backend
        try:
            if SIMPLEAUDIO_AVAILABLE:
                import wave

                with wave.open(str(prepared_path), "rb") as wav:
                    audio_data = wav.readframes(wav.getnframes())
                    play_obj = _simpleaudio.play_buffer(
                        audio_data,
                        num_channels=wav.getnchannels(),
                        bytes_per_sample=wav.getsampwidth(),
                        sample_rate=wav.getframerate(),
                    )
                    self._audio_preview_wave = play_obj
            elif WINSOUND_AVAILABLE:
                winsound.PlaySound(
                    str(prepared_path), winsound.SND_FILENAME | winsound.SND_ASYNC
                )
            else:
                messagebox.showinfo(
                    "Preview",
                    "Audio preview requires 'simpleaudio' (not installed) and no Windows fallback available.",
                )
                return
        except Exception as exc:
            messagebox.showerror("Preview", f"Preview failed: {exc}")
        finally:
            if prepared_path != path and prepared_path.exists():
                try:
                    prepared_path.unlink()
                except Exception:
                    pass

    def _parse_segments(self) -> None:
        segment_path = self.segment_path_var.get()
        if not segment_path:
            messagebox.showerror("Parser", "Select a segments file first.")
            return
        try:
            merge_threshold = float(self.merge_threshold_var.get())
            min_duration = float(self.min_duration_var.get())
        except ValueError:
            messagebox.showerror("Parser", "Merge gap and minimum duration must be numeric values.")
            return
        settings = ParserSettings(
            merge_threshold=merge_threshold,
            min_duration=min_duration,
            speaker_filter=self.speaker_filter_var.get().strip() or None,
            keep_speaker_prefix=self.keep_speaker_prefix_var.get(),
        )
        try:
            with open(segment_path, "r", encoding="utf-8") as fh:
                segments = parse_segment_lines(fh.readlines())
        except FileNotFoundError:
            messagebox.showerror("Parser", f"File not found: {segment_path}")
            return
        merged = merge_segments(segments, settings)
        if not merged:
            messagebox.showwarning("Parser", "No segments matched the requested filters.")
            return
        output_path = Path(segment_path).with_name(
            f"{Path(segment_path).stem}_parsed_{merge_threshold:.2f}.txt"
        )
        with output_path.open("w", encoding="utf-8") as fh:
            for seg in merged:
                prefix = f"{seg.speaker}: " if seg.speaker and settings.keep_speaker_prefix else ""
                fh.write(f"[{seg.start:.2f} - {seg.end:.2f}] {prefix}{seg.text}\n")
        self.parsed_segment_path_var.set(str(output_path))
        self.parser_output.configure(state="normal")
        self.parser_output.delete("1.0", tk.END)
        for seg in merged:
            speaker = f"{seg.speaker}: " if seg.speaker else ""
            self.parser_output.insert(tk.END, f"[{seg.start:.2f}-{seg.end:.2f}] {speaker}{seg.text}\n")
        self.parser_output.configure(state="disabled")
        messagebox.showinfo("Parser", f"Parsed segments saved to {output_path}")

    def _browse_segments_file(self) -> None:
        path = filedialog.askopenfilename(
            title="Select segments file",
            filetypes=[("Text", "*.txt"), ("All", "*.*")],
        )
        if path:
            self.segment_path_var.set(path)

    def _start_transcription(self) -> None:
        if self.worker and self.worker.is_alive():
            messagebox.showinfo("Transcription", "A transcription is already running.")
            return
        if not self.selected_files:
            messagebox.showerror("Transcription", "Add at least one audio file.")
            return
        try:
            min_speakers = int(self.min_speakers_var.get()) if self.min_speakers_var.get() else None
        except ValueError:
            messagebox.showerror("Transcription", "Minimum speakers must be an integer.")
            return
        try:
            max_speakers = int(self.max_speakers_var.get()) if self.max_speakers_var.get() else None
        except ValueError:
            messagebox.showerror("Transcription", "Maximum speakers must be an integer.")
            return
        try:
            batch_size = int(self.batch_size_var.get())
            if batch_size <= 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Transcription", "Batch size must be a positive integer.")
            return

        export_formats = [fmt for fmt, var in self.export_format_vars.items() if var.get()]
        if not export_formats:
            messagebox.showwarning(
                "Transcription",
                "Select at least one export format. Defaulting to plain text.",
            )
            export_formats = ["txt"]

        settings = TranscriptionSettings(
            model_size=self.model_size.get(),
            combine_transcripts=self.combine_var.get(),
            diarize=self.diarize_var.get(),
            hf_token=self.hf_token_var.get().strip(),
            min_speakers=min_speakers,
            max_speakers=max_speakers,
            export_formats=export_formats,
            batch_size=batch_size,
            compute_type=self.compute_type_var.get(),
        )

        self.progress_bar.configure(value=0, maximum=len(self.selected_files))
        self.status_var.set("Initialising transcription...")
        self.eta_var.set("ETA: calculating")
        self.transcript_path_var.set("")
        self.segment_path_var.set("")
        self.combined_path_var.set("")
        self.cancel_event.clear()
        self.worker = WhisperXWorker(self.selected_files, settings, self.progress_queue, self.cancel_event, self.logger)
        self.worker.start()

    def _cancel_transcription(self) -> None:
        if self.worker and self.worker.is_alive():
            self.cancel_event.set()
            self.status_var.set("Cancellation requested – finishing current file...")

    def _open_output_directory(self) -> None:
        if not self.selected_files:
            messagebox.showinfo("Output", "No audio files selected yet.")
            return
        directory = self.selected_files[0].parent
        try:
            if sys.platform.startswith("win"):
                os.startfile(str(directory))
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(directory)])
            else:
                subprocess.Popen(["xdg-open", str(directory)])
        except Exception as exc:
            messagebox.showerror("Output", f"Failed to open directory: {exc}")

    def _refresh_logs(self) -> None:
        if not LOG_PATH.exists():
            return
        self.log_view.configure(state="normal")
        self.log_view.delete("1.0", tk.END)
        try:
            with LOG_PATH.open("r", encoding="utf-8", errors="ignore") as fh:
                self.log_view.insert(tk.END, fh.read())
        finally:
            self.log_view.configure(state="disabled")

    def _open_log_file(self) -> None:
        if not LOG_PATH.exists():
            messagebox.showinfo("Logs", "Log file does not exist yet.")
            return
        try:
            if sys.platform.startswith("win"):
                os.startfile(str(LOG_PATH))
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(LOG_PATH)])
            else:
                subprocess.Popen(["xdg-open", str(LOG_PATH)])
        except Exception as exc:
            messagebox.showerror("Logs", f"Could not open log file: {exc}")

    def _copy_debug_info(self) -> None:
        info = {
            "python": sys.version,
            "platform": sys.platform,
            "whisperx_available": WHISPERX_AVAILABLE,
            "torch_version": getattr(torch, "__version__", "n/a") if torch else "n/a",
            "selected_files": [str(p) for p in self.selected_files],
        }
        self.root.clipboard_clear()
        self.root.clipboard_append(json.dumps(info, indent=2))
        messagebox.showinfo("Logs", "Debug information copied to clipboard.")

    # ------------------------------------------------------------------
    # Queue processing
    # ------------------------------------------------------------------
    def _poll_queue(self) -> None:
        try:
            while True:
                event, payload = self.progress_queue.get_nowait()
                if event == "status":
                    self.status_var.set(str(payload))
                elif event == "progress":
                    done, total, *rest = payload  # type: ignore[assignment]
                    elapsed = rest[0] if rest else None
                    self.progress_bar.configure(maximum=total, value=done)
                    if elapsed is not None and done:
                        avg = elapsed / max(done, 1)
                        remaining = max(total - done, 0)
                        eta_seconds = int(avg * remaining)
                        minutes, seconds = divmod(eta_seconds, 60)
                        self.eta_var.set(f"ETA: {minutes:02d}:{seconds:02d}")
                    elif done >= total:
                        self.eta_var.set("ETA: completed")
                elif event == "warning":
                    self.logger.warning(str(payload))
                    self.status_var.set(str(payload))
                elif event == "error":
                    audio_path, message, tb_str = payload  # type: ignore[misc]
                    self.logger.error("Transcription error for %s: %s", audio_path, message)
                    self.logger.debug(tb_str)
                    messagebox.showerror(
                        "Transcription error",
                        f"{audio_path.name} failed: {message}\nSee logs for details.",
                    )
                elif event == "fatal":
                    messagebox.showerror("Fatal", str(payload))
                elif event == "file-complete":
                    result: TranscriptionResult = payload  # type: ignore[assignment]
                    if result.transcript_path:
                        self.transcript_path_var.set(str(result.transcript_path))
                    if result.segment_path:
                        self.segment_path_var.set(str(result.segment_path))
                    self.status_var.set(f"Finished {result.audio_path.name}")
                elif event == "combined":
                    combined_paths: Dict[str, Path] = payload  # type: ignore[assignment]
                    preferred = combined_paths.get("txt") or next(iter(combined_paths.values()))
                    self.combined_path_var.set(str(preferred))
                    self.status_var.set("Combined transcript updated")
                elif event == "completed":
                    results, duration = payload  # type: ignore[misc]
                    success_count = sum(1 for res in results if res.success)
                    failures = [res for res in results if not res.success]
                    summary = f"Completed {success_count}/{len(results)} files in {duration/60:.1f} min"
                    self.status_var.set(summary)
                    self.eta_var.set("ETA: done")
                    if failures:
                        details = "\n".join(f"{res.audio_path.name}: {res.error}" for res in failures)
                        messagebox.showwarning("Transcription completed with errors", details)
                    else:
                        messagebox.showinfo("Transcription", summary)
                self.progress_queue.task_done()
        except queue.Empty:
            pass
        self.root.after(150, self._poll_queue)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def launch_app() -> None:
    """Launch the WhisperX GUI application."""

    if TKDND_AVAILABLE:
        root = TkinterDnD.Tk()
    else:
        root = tk.Tk()
    WhisperXApp(root)
    root.mainloop()


if __name__ == "__main__":  # pragma: no cover - interactive component
    launch_app()
