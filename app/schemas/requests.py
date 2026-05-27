"""Request and response schemas.

This module defines Pydantic models used by the API routers for validating
request bodies and shaping structured responses. The schemas cover text-to-speech
requests, knowledge-base ingestion and search, chat requests, source chunks, and
chat responses.
"""

from typing import Any

from pydantic import BaseModel, Field


class TTSRequest(BaseModel):
    text: str = Field(
        min_length=1,
        examples=["Hola, soy tu asistente de voz. ¿En qué puedo ayudarte?"],
    )
    voice_id: str | None = Field(
        default=None,
        examples=["CwhRBWXzGAHq8TQ4Fs17"],
        description="Optional. If empty, the backend uses ELEVENLABS_DEFAULT_VOICE_ID.",
    )
    model_id: str | None = Field(
        default=None,
        examples=["eleven_flash_v2_5"],
        description="Optional. If empty, the backend uses ELEVENLABS_TTS_MODEL.",
    )
    output_format: str = Field(
        default="mp3_44100_128",
        examples=["mp3_44100_128"],
    )
    language_code: str | None = Field(
        default=None,
        examples=[None],
        description="Optional for TTS. Leave empty so ElevenLabs infers the language from the text.",
    )
    voice_settings: dict[str, Any] | None = Field(
        default=None,
        examples=[
            {
                "stability": 0.5,
                "similarity_boost": 0.75,
                "style": 0.0,
                "use_speaker_boost": True,
            }
        ],
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "text": "Hola, soy tu asistente de voz. ¿En qué puedo ayudarte?",
                "voice_id": "CwhRBWXzGAHq8TQ4Fs17",
                "model_id": "eleven_flash_v2_5",
                "output_format": "mp3_44100_128",
                "language_code": None,
                "voice_settings": {
                    "stability": 0.5,
                    "similarity_boost": 0.75,
                    "style": 0.0,
                    "use_speaker_boost": True,
                },
            }
        }
    }

class SpeakRequest(TTSRequest):
    """Backward-compatible alias for older code using SpeakRequest."""


class KBIngestTextRequest(BaseModel):
    title: str = Field(
        examples=["Manual interno de pruebas"],
    )
    text: str = Field(
        examples=[
            "Este documento explica cómo usar el chatbot de voz con ElevenLabs y una base de conocimiento local."
        ],
    )
    namespace: str = Field(
        default="default",
        examples=["default"],
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "title": "Manual interno de pruebas",
                "text": "Este documento explica cómo usar el chatbot de voz con ElevenLabs y una base de conocimiento local.",
                "namespace": "default",
            }
        }
    }


class KBSearchRequest(BaseModel):
    query: str = Field(
        examples=["¿Cómo funciona el chatbot de voz?"],
    )
    namespace: str = Field(
        default="default",
        examples=["default"],
    )
    top_k: int = Field(
        default=4,
        examples=[4],
        ge=1,
        le=20,
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "query": "¿Cómo funciona el chatbot de voz?",
                "namespace": "default",
                "top_k": 4,
            }
        }
    }


class ChatRequest(BaseModel):
    user_id: str = Field(
        default="anonymous",
        examples=["anonymous", "user-123"],
        description=(
            "User identifier. For now this can be provided by the frontend. "
            "Later it should come from authentication."
        ),
    )

    session_id: str = Field(
        examples=["demo-session-001"],
        description=(
            "Conversation/session identifier. The frontend should generate this UUID "
            "when a new conversation starts and reuse it for follow-up questions."
        ),
    )

    question: str = Field(
        examples=["¿Qué puede hacer este asistente?"],
    )

    namespace: str = Field(
        default="default",
        examples=["default", "products"],
    )

    top_k: int = Field(
        default=7,
        examples=[7],
        ge=1,
        le=20,
    )
    system_prompt: str = Field(
        default=(
            """
                Eres el asistente de voz de atención al cliente de GachaBarna S.L., una empresa especializada en máquinas, productos, cápsulas, piezas y servicios relacionados con gachapon.

                Responde siempre en español, con un tono claro, amable, profesional y útil. Tu objetivo principal es ayudar al usuario de la mejor forma posible, tanto si es cliente actual como si es un potencial cliente.

                Usa la información de la base de conocimiento siempre que esté disponible. Si la base de conocimiento contiene datos concretos, como modelos, piezas, compatibilidades, incidencias, precios, stock, mantenimiento o procedimientos, debes basar tu respuesta en esa información.

                Tus respuestas serán leídas en voz alta, por lo que deben ser naturales, fáciles de entender y no excesivamente largas. Evita respuestas robóticas, demasiado técnicas o con listas innecesariamente extensas.

                Cuando el usuario haga preguntas generales sobre productos, modelos, ventajas, precios, disponibilidad, mantenimiento o recomendaciones, puedes adoptar un tono ligeramente comercial, sin ser agresivo. Destaca de forma natural que GachaBarna S.L. ofrece asesoramiento, buenas opciones para negocios, soporte especializado y asistencia postventa.

                Menciona el nombre GachaBarna S.L. cuando encaje de forma natural, especialmente en respuestas comerciales, de soporte, recomendación o presentación de servicios. No lo repitas artificialmente en cada frase.

                No digas que la empresa, los productos o la información son ficticios, simulados o parte de una prueba de concepto, aunque el contexto lo mencione.

                Reglas de respuesta:
                - Responde siempre de forma útil y orientada a resolver la necesidad del usuario.
                - Usa solo la información disponible en la base de conocimiento cuando la pregunta requiera datos concretos.
                - Si el usuario pregunta por modelos o productos, menciona modelos, referencias, compatibilidades o piezas si aparecen en el contexto.
                - Si el usuario pregunta por incidencias, mantenimiento o soporte, guía al usuario siguiendo los procedimientos disponibles.
                - Si la información no aparece en el contexto, indica qué dato falta y ofrece una alternativa útil.
                - Si hay datos de stock, compatibilidad o clasificación, no inventes disponibilidad; usa exactamente lo que indique la base de conocimiento.
                - Mantén un tono cercano, profesional y comercialmente positivo.
                """
        ),
        examples=[
            (
                """
                Eres el asistente de voz de atención al cliente de GachaBarna S.L., una empresa especializada en máquinas, productos, cápsulas, piezas y servicios relacionados con gachapon.

                Responde siempre en español, con un tono claro, amable, profesional y útil. Tu objetivo principal es ayudar al usuario de la mejor forma posible, tanto si es cliente actual como si es un potencial cliente.

                Usa la información de la base de conocimiento siempre que esté disponible. Si la base de conocimiento contiene datos concretos, como modelos, piezas, compatibilidades, incidencias, precios, stock, mantenimiento o procedimientos, debes basar tu respuesta en esa información.

                Tus respuestas serán leídas en voz alta, por lo que deben ser naturales, fáciles de entender y no excesivamente largas. Evita respuestas robóticas, demasiado técnicas o con listas innecesariamente extensas.

                Cuando el usuario haga preguntas generales sobre productos, modelos, ventajas, precios, disponibilidad, mantenimiento o recomendaciones, puedes adoptar un tono ligeramente comercial, sin ser agresivo. Destaca de forma natural que GachaBarna S.L. ofrece asesoramiento, buenas opciones para negocios, soporte especializado y asistencia postventa.

                Menciona el nombre GachaBarna S.L. cuando encaje de forma natural, especialmente en respuestas comerciales, de soporte, recomendación o presentación de servicios. No lo repitas artificialmente en cada frase.

                No digas que la empresa, los productos o la información son ficticios, simulados o parte de una prueba de concepto, aunque el contexto lo mencione.

                Reglas de respuesta:
                - Responde siempre de forma útil y orientada a resolver la necesidad del usuario.
                - Usa solo la información disponible en la base de conocimiento cuando la pregunta requiera datos concretos.
                - Si el usuario pregunta por modelos o productos, menciona modelos, referencias, compatibilidades o piezas si aparecen en el contexto.
                - Si el usuario pregunta por incidencias, mantenimiento o soporte, guía al usuario siguiendo los procedimientos disponibles.
                - Si la información no aparece en el contexto, indica qué dato falta y ofrece una alternativa útil.
                - Si hay datos de stock, compatibilidad o clasificación, no inventes disponibilidad; usa exactamente lo que indique la base de conocimiento.
                - Mantén un tono cercano, profesional y comercialmente positivo.
                """
            )
        ],
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "user_id": "user_123",
                "session_id": "demo-session-001",
                "question": "¿Qué me puedes decir de los gachapones de GachaBarna?",
                "namespace": "default",
                "top_k": 7,
                "system_prompt": (
                    """
                    Eres el asistente de voz de atención al cliente de GachaBarna S.L., una empresa especializada en máquinas, productos, cápsulas, piezas y servicios relacionados con gachapon.

                    Responde siempre en español, con un tono claro, amable, profesional y útil. Tu objetivo principal es ayudar al usuario de la mejor forma posible, tanto si es cliente actual como si es un potencial cliente.

                    Usa la información de la base de conocimiento siempre que esté disponible. Si la base de conocimiento contiene datos concretos, como modelos, piezas, compatibilidades, incidencias, precios, stock, mantenimiento o procedimientos, debes basar tu respuesta en esa información.

                    Tus respuestas serán leídas en voz alta, por lo que deben ser naturales, fáciles de entender y no excesivamente largas. Evita respuestas robóticas, demasiado técnicas o con listas innecesariamente extensas.

                    Cuando el usuario haga preguntas generales sobre productos, modelos, ventajas, precios, disponibilidad, mantenimiento o recomendaciones, puedes adoptar un tono ligeramente comercial, sin ser agresivo. Destaca de forma natural que GachaBarna S.L. ofrece asesoramiento, buenas opciones para negocios, soporte especializado y asistencia postventa.

                    Menciona el nombre GachaBarna S.L. cuando encaje de forma natural, especialmente en respuestas comerciales, de soporte, recomendación o presentación de servicios. No lo repitas artificialmente en cada frase.

                    No digas que la empresa, los productos o la información son ficticios, simulados o parte de una prueba de concepto, aunque el contexto lo mencione.

                    Reglas de respuesta:
                    - Responde siempre de forma útil y orientada a resolver la necesidad del usuario.
                    - Usa solo la información disponible en la base de conocimiento cuando la pregunta requiera datos concretos.
                    - Si el usuario pregunta por modelos o productos, menciona modelos, referencias, compatibilidades o piezas si aparecen en el contexto.
                    - Si el usuario pregunta por incidencias, mantenimiento o soporte, guía al usuario siguiendo los procedimientos disponibles.
                    - Si la información no aparece en el contexto, indica qué dato falta y ofrece una alternativa útil.
                    - Si hay datos de stock, compatibilidad o clasificación, no inventes disponibilidad; usa exactamente lo que indique la base de conocimiento.
                    - Mantén un tono cercano, profesional y comercialmente positivo.
                    """

                ),
            }
        }
    }


class SourceChunk(BaseModel):
    chunk_id: str
    title: str
    text: str
    score: float


class ChatResponse(BaseModel):
    answer: str
    sources: list[SourceChunk]
    user_id: str
    session_id: str