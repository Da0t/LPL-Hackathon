"""Optional Amazon Transcribe Streaming support (stretch, after Bedrock works).

The judged, must-work path is **typed** intake. Voice is additive and on-thesis
for the older-investor persona, but live streaming is the biggest reliability
risk, so this module is intentionally a thin, dependency-guarded wrapper that
never breaks the app when the optional dependency or credentials are absent.

Two honest options for the demo, in order of reliability:

1. **Browser speech recognition** (Web Speech API) in the client page. No AWS
   dependency; label it accurately as a browser feature in the presentation.
2. **Amazon Transcribe Streaming** via the ``amazon-transcribe`` async SDK
   (HTTP/2). Enable by installing that package and calling
   :func:`stream_microphone` from an async context. No S3 is required for
   streaming; if audio is ever persisted, the bucket must stay private.

Usage::

    from backend.aws import transcribe
    if transcribe.available():
        text = await transcribe.transcribe_pcm_chunks(chunks, region="us-east-1")
"""

from __future__ import annotations

import os

REGION = os.environ.get("AWS_REGION", "us-east-1")


def available() -> bool:
    """True only if the optional Transcribe streaming SDK is importable."""
    try:
        import amazon_transcribe  # noqa: F401
    except Exception:
        return False
    return True


async def transcribe_pcm_chunks(
    chunks,
    *,
    region: str | None = None,
    sample_rate_hz: int = 16000,
    language_code: str = "en-US",
) -> str:
    """Transcribe an async iterable of 16-bit PCM audio chunks to text.

    Raises :class:`RuntimeError` with setup guidance if the optional dependency
    is not installed, so callers can fall back to the typed path cleanly.
    """
    if not available():
        raise RuntimeError(
            "Transcribe streaming is optional and not installed. Add "
            "'amazon-transcribe' to the environment or use the typed path / "
            "browser speech recognition instead."
        )

    from amazon_transcribe.client import TranscribeStreamingClient
    from amazon_transcribe.handlers import TranscriptResultStreamHandler
    from amazon_transcribe.model import TranscriptEvent

    collected: list[str] = []

    class _Handler(TranscriptResultStreamHandler):
        async def handle_transcript_event(self, event: TranscriptEvent):
            for result in event.transcript.results:
                if result.is_partial:
                    continue
                for alt in result.alternatives:
                    collected.append(alt.transcript)

    client = TranscribeStreamingClient(region=region or REGION)
    stream = await client.start_stream_transcription(
        language_code=language_code,
        media_sample_rate_hz=sample_rate_hz,
        media_encoding="pcm",
    )

    async def _write():
        async for chunk in chunks:
            await stream.input_stream.send_audio_event(audio_chunk=chunk)
        await stream.input_stream.end_stream()

    handler = _Handler(stream.output_stream)
    import asyncio

    await asyncio.gather(_write(), handler.handle_events())
    return " ".join(collected).strip()
