"""Optional Amazon Transcribe speech-to-text with a financial custom vocabulary.

The judged, must-work path is typed intake, and the client page already offers
browser speech recognition. This module adds the AWS-native voice path:

* A **custom vocabulary** of financial terms (ROI, Roth IRA, RMD, 1099-R, ...)
  biases Transcribe toward the right words. Combined with the intake agent's
  term normalization, spoken shorthand resolves to approved terms. No S3 is
  needed; the vocabulary is created from an inline phrase list.
* ``transcribe_wav`` transcribes a recorded clip (easy to test on the presenting
  machine); ``transcribe_pcm_chunks`` streams live microphone audio.

Vocabulary management uses boto3 (always available). Live streaming additionally
needs the ``amazon-transcribe`` package (see requirements-aws.txt); the typed and
browser-speech paths keep working if it is absent.
"""

from __future__ import annotations

import os
import time

REGION = os.environ.get("AWS_REGION", "us-east-1")
FINANCIAL_VOCAB_NAME = os.environ.get("TRANSCRIBE_VOCAB_NAME", "samepage-financial-terms")

# Inline phrases (letters + hyphens only, per Transcribe rules). Multi-word terms
# are hyphen-joined. These bias recognition toward financial vocabulary.
FINANCIAL_VOCAB_PHRASES = [
    "ROI", "Roth-IRA", "rollover-IRA", "traditional-IRA", "IRA",
    "RMD", "required-minimum-distribution", "distribution", "withdrawal",
    "dividend", "dividends", "capital-gains", "beneficiary", "brokerage",
    "transfer", "ten-ninety-nine", "trusted-contact",
]


def available() -> bool:
    """True only if the optional Transcribe streaming SDK is importable."""
    try:
        import amazon_transcribe  # noqa: F401
    except Exception:
        return False
    return True


def ensure_financial_vocabulary(region: str | None = None, wait: bool = True) -> str:
    """Create or update the financial custom vocabulary. Returns its state.

    Idempotent: creates it if missing, updates it if it already exists. Uses
    boto3 (no streaming SDK needed). When ``wait`` is True, blocks until the
    vocabulary reaches READY or FAILED.
    """
    import boto3
    from botocore.exceptions import ClientError

    tc = boto3.client("transcribe", region_name=region or REGION)
    try:
        tc.create_vocabulary(
            VocabularyName=FINANCIAL_VOCAB_NAME,
            LanguageCode="en-US",
            Phrases=FINANCIAL_VOCAB_PHRASES,
        )
    except ClientError as exc:
        if exc.response.get("Error", {}).get("Code") == "ConflictException":
            tc.update_vocabulary(
                VocabularyName=FINANCIAL_VOCAB_NAME,
                LanguageCode="en-US",
                Phrases=FINANCIAL_VOCAB_PHRASES,
            )
        else:
            raise

    state = "PENDING"
    while wait:
        info = tc.get_vocabulary(VocabularyName=FINANCIAL_VOCAB_NAME)
        state = info["VocabularyState"]
        if state in ("READY", "FAILED"):
            break
        time.sleep(5)
    return state


async def transcribe_pcm_chunks(
    chunks,
    *,
    region: str | None = None,
    sample_rate_hz: int = 16000,
    language_code: str = "en-US",
    vocabulary_name: str | None = FINANCIAL_VOCAB_NAME,
) -> str:
    """Transcribe an async iterable of 16-bit PCM audio chunks to text.

    Raises :class:`RuntimeError` with setup guidance if the optional dependency
    is not installed, so callers can fall back to the typed path cleanly.
    """
    if not available():
        raise RuntimeError(
            "Transcribe streaming is optional and not installed. Add "
            "'amazon-transcribe' to the environment, or use the typed path / "
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
    kwargs = dict(
        language_code=language_code,
        media_sample_rate_hz=sample_rate_hz,
        media_encoding="pcm",
    )
    if vocabulary_name:
        kwargs["vocabulary_name"] = vocabulary_name
    stream = await client.start_stream_transcription(**kwargs)

    async def _write():
        async for chunk in chunks:
            await stream.input_stream.send_audio_event(audio_chunk=chunk)
        await stream.input_stream.end_stream()

    handler = _Handler(stream.output_stream)
    import asyncio

    await asyncio.gather(_write(), handler.handle_events())
    return " ".join(collected).strip()


async def transcribe_wav(path: str, *, region: str | None = None,
                         vocabulary_name: str | None = FINANCIAL_VOCAB_NAME) -> str:
    """Transcribe a 16-bit PCM mono WAV file (easy to test a recorded clip)."""
    import wave

    with wave.open(path, "rb") as wav:
        rate = wav.getframerate()
        frames = wav.readframes(wav.getnframes())

    async def _chunks():
        step = 1024 * 8
        for i in range(0, len(frames), step):
            yield frames[i:i + step]

    return await transcribe_pcm_chunks(
        _chunks(), region=region, sample_rate_hz=rate, vocabulary_name=vocabulary_name
    )


if __name__ == "__main__":
    # Create/refresh the financial custom vocabulary from the command line:
    #   AWS_PROFILE=lpl-hackathon python -m backend.aws.transcribe
    print(f"Ensuring Transcribe vocabulary '{FINANCIAL_VOCAB_NAME}' in {REGION} ...")
    print("state:", ensure_financial_vocabulary())
