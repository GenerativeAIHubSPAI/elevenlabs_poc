from functools import lru_cache
from pathlib import Path

from pydantic import computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
        case_sensitive=True,
    )

    # ElevenLabs
    ELEVENLABS_API_KEY: str
    ELEVENLABS_BASE_URL: str = "https://api.elevenlabs.io"

    ELEVENLABS_VOICE_ID: str | None = None
    ELEVENLABS_DEFAULT_VOICE_ID: str | None = None
    ELEVENLABS_AGENT_ID: str | None = None

    ELEVENLABS_TTS_MODEL: str = "eleven_flash_v2_5"
    ELEVENLABS_STT_MODEL: str = "scribe_v2"
    ELEVENLABS_REALTIME_STT_MODEL: str = "scribe_v2_realtime"

    ELEVENLABS_TTS_OUTPUT_FORMAT: str = "mp3_44100_128"
    ELEVENLABS_STT_AUDIO_FORMAT: str = "pcm_16000"
    ELEVENLABS_STT_SAMPLE_RATE: int = 16000

    # Bedrock
    AWS_REGION: str = "eu-west-1"
    AWS_BEARER_TOKEN_BEDROCK: str | None = None
    BEDROCK_MODEL_ID: str = "amazon.nova-pro-v1:0"
    BEDROCK_MAX_TOKENS: int = 700
    BEDROCK_TEMPERATURE: float = 0.2

    # Application
    OUTPUT_DIR: str = "../output/"

    # Knowledge base
    KB_DEFAULT_NAMESPACE: str = "default"
    KB_CHUNK_SIZE: int = 500
    KB_CHUNK_OVERLAP: int = 80
    KB_TOP_K: int = 4

    @computed_field
    @property
    def BASE_URL(self) -> str:
        return self.ELEVENLABS_BASE_URL.rstrip("/")

    @computed_field
    @property
    def VOICE_ID(self) -> str | None:
        return self.ELEVENLABS_DEFAULT_VOICE_ID or self.ELEVENLABS_VOICE_ID

    @computed_field
    @property
    def OUTPUT_PATH(self) -> Path:
        return Path(self.OUTPUT_DIR)


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()