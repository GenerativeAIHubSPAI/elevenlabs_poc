"""Health and metadata routes.

This module exposes lightweight endpoints for checking backend availability and
inspecting external ElevenLabs resources such as available models and voices.
These routes are mainly used for operational checks and development validation.
"""

from fastapi import APIRouter

from app.services.elevenlabs import ElevenLabsClient
from app.services.static_kb_jobs import static_kb_health
from typing import Any, Literal

from fastapi import Query


VoiceGender = Literal["male", "female", "neutral"]
VoiceCategory = Literal["premade", "professional", "cloned", "generated"]
router = APIRouter()
eleven = ElevenLabsClient()


@router.get("/health")
async def health():
    """Liveness probe for the ALB and the ECS container health check.

    The HTTP status answers one question -- is this process serving? -- so it is
    200 whenever uvicorn responds. A static topic that failed to load must not
    fail it: replacing the task would not fix S3 or configuration, would loop,
    and would take PDF upload (the default source) down with it.

    The body tells the whole truth instead: "status" is "ok", "loading" (topics
    still loading after startup) or "degraded" (at least one topic cannot
    answer), with the reason per topic under "static_kb".
    """
    static_kb = static_kb_health()

    return {
        "status": static_kb["status"],
        "static_kb": static_kb,
    }


@router.get("/models")
async def models():
    return await eleven.get_models()


@router.get("/voices")
async def voices(
    language: str | None = Query(
        None,
        description=(
            "Filter by supported language or locale. "
            "Examples: 'es', 'en', 'fr', 'es-ES', 'en-US'. "
            "Matches labels.language, fine_tuning.language, and verified_languages."
        ),
        examples=["es"],
    ),
    gender: VoiceGender | None = Query(
        None,
        description="Filter by voice gender. Common values: male, female, neutral.",
        examples=["female"],
    ),
    accent: str | None = Query(
        None,
        description=(
            "Filter by accent label. Examples from current voices: "
            "peninsular, american, british, australian, standard."
        ),
        examples=["peninsular"],
    ),
    use_case: str | None = Query(
        None,
        description=(
            "Filter by intended use case. Examples: conversational, "
            "informative_educational, social_media, narrative_story, "
            "characters_animation, advertisement."
        ),
        examples=["conversational"],
    ),
    category: VoiceCategory | None = Query(
        None,
        description=(
            "Filter by ElevenLabs voice category. "
            "premade = built-in ElevenLabs voices; professional = professional/custom voices; "
            "cloned/generated may appear depending on account/library."
        ),
        examples=["professional"],
    ),
    search: str | None = Query(
        None,
        description=(
            "Free-text search across name, description, category, gender, age, accent, "
            "language, use_case, and descriptive labels."
        ),
        examples=["customer service"],
    ),
    include_raw: bool = Query(
        False,
        description="If true, includes the original ElevenLabs response under 'raw'. Useful for debugging only.",
    ),
):
    return await eleven.get_voices(
        language=language,
        gender=gender,
        accent=accent,
        use_case=use_case,
        category=category,
        search=search,
        include_raw=include_raw,
    )