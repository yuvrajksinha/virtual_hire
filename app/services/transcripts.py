"""Transcript ingestion: get interview transcript text into Postgres,
regardless of source - a platform-provided transcript submitted directly
as text, or an interview audio recording transcribed via STT
(`app.services.transcription`). Both paths converge on the same
`transcripts.text` write and the same `embed_transcript` enqueue -
"same RAG pipeline" applies to ingestion, not just embedding.

VHIRE-2x (transcript/audio RAG pipeline extension).
"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import TranscriptSource, TranscriptStatus
from app.models.transcript import Transcript
from app.services import transcription
from app.workers.celery_app import celery_app


async def _get_or_create_transcript(
    session: AsyncSession, *, organization_id: uuid.UUID, interview_id: uuid.UUID
) -> Transcript:
    result = await session.execute(select(Transcript).where(Transcript.interview_id == interview_id))
    transcript = result.scalar_one_or_none()
    if transcript is not None:
        return transcript

    transcript = Transcript(organization_id=organization_id, interview_id=interview_id)
    session.add(transcript)
    await session.flush()
    return transcript


async def _finalize_and_enqueue(
    session: AsyncSession, transcript: Transcript, *, organization_id: uuid.UUID
) -> Transcript:
    transcript.status = TranscriptStatus.available
    await session.commit()
    await session.refresh(transcript)

    celery_app.send_task(
        "app.workers.tasks.embedding.embed_transcript",
        kwargs={"transcript_id": str(transcript.id), "organization_id": str(organization_id)},
    )
    return transcript


async def ingest_transcript_text(
    session: AsyncSession,
    *,
    organization_id: uuid.UUID,
    interview_id: uuid.UUID,
    text: str,
    language: str | None = None,
) -> Transcript:
    """Ingest a platform-provided transcript submitted directly as text."""
    transcript = await _get_or_create_transcript(
        session, organization_id=organization_id, interview_id=interview_id
    )
    transcript.text = text
    transcript.language = language
    transcript.source = TranscriptSource.platform_provided
    return await _finalize_and_enqueue(session, transcript, organization_id=organization_id)


async def ingest_transcript_audio(
    session: AsyncSession,
    *,
    organization_id: uuid.UUID,
    interview_id: uuid.UUID,
    filename: str,
    audio_content: bytes,
) -> Transcript:
    """Ingest an interview audio recording: transcribe via STT, then store
    the resulting text exactly like a platform-provided transcript.

    Raises:
        Whatever `app.services.transcription.transcribe_audio` raises on
        STT failure - propagated untouched; no Transcript row is written
        in that case.
    """
    text = await transcription.transcribe_audio(audio_content, filename)

    transcript = await _get_or_create_transcript(
        session, organization_id=organization_id, interview_id=interview_id
    )
    transcript.text = text
    transcript.source = TranscriptSource.generated_stt
    return await _finalize_and_enqueue(session, transcript, organization_id=organization_id)
