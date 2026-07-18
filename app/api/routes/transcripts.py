"""Transcript ingestion route: accepts either a platform-provided
transcript submitted as text, or an interview audio recording (STT via
app.services.transcription) - both converge on the same
`transcripts.text` write and `embed_transcript` enqueue. Org-scoped via
app.api.deps.get_org_scoped_db.
"""

import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_hr_user, get_org_scoped_db
from app.core.security import HRUserClaims
from app.schemas.transcript import TranscriptRead
from app.services import transcripts as transcripts_service

router = APIRouter(prefix="/interviews", tags=["transcripts"])


@router.post("/{interview_id}/transcript", response_model=TranscriptRead, status_code=status.HTTP_202_ACCEPTED)
async def ingest_transcript(
    interview_id: uuid.UUID,
    text: str | None = Form(None),
    language: str | None = Form(None),
    audio_file: UploadFile | None = File(None),
    hr_user: HRUserClaims = Depends(get_current_hr_user),
    session: AsyncSession = Depends(get_org_scoped_db),
) -> TranscriptRead:
    """Ingest a transcript for `interview_id`, from either `text` (a
    platform-provided transcript) or `audio_file` (transcribed via STT).

    Enqueues `embed_transcript` on success - the same chunk/embed/upsert
    pipeline resumes use, per vector.md.

    Raises:
        HTTPException: 400 if neither `text` nor `audio_file` is provided.
    """
    if text is not None:
        return await transcripts_service.ingest_transcript_text(
            session,
            organization_id=hr_user.organization_id,
            interview_id=interview_id,
            text=text,
            language=language,
        )

    if audio_file is not None:
        audio_content = await audio_file.read()
        return await transcripts_service.ingest_transcript_audio(
            session,
            organization_id=hr_user.organization_id,
            interview_id=interview_id,
            filename=audio_file.filename or "interview-audio",
            audio_content=audio_content,
        )

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST, detail="either 'text' or 'audio_file' is required"
    )
