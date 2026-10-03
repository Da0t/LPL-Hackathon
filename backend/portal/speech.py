"""Authenticated, bounded Polly speech; text/audio are not persisted or logged."""

import os
import threading
import time
from functools import lru_cache
import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError
from backend.errors import ApiError

_lock = threading.Lock()
_requests = {}


@lru_cache(maxsize=1)
def polly():
    return boto3.client(
        "polly",
        region_name=os.getenv("AWS_REGION", "us-east-1"),
        config=Config(connect_timeout=4, read_timeout=12, retries={"max_attempts": 1}),
    )


def speak(client_id, text):
    now = time.monotonic()
    with _lock:
        recent = [t for t in _requests.get(client_id, []) if now - t < 60]
        if len(recent) >= 15:
            raise ApiError(
                429, "SPEECH_LIMIT", "Please wait a moment before reading aloud again."
            )
        _requests[client_id] = recent + [now]
    try:
        response = polly().synthesize_speech(
            Text=text,
            TextType="text",
            OutputFormat="mp3",
            VoiceId="Joanna",
            Engine="neural",
        )
        with response["AudioStream"] as stream:
            return stream.read()
    except (BotoCoreError, ClientError):
        raise ApiError(
            503,
            "SPEECH_UNAVAILABLE",
            "Read-aloud is unavailable right now. Your text is still here and you can continue by typing.",
        ) from None
