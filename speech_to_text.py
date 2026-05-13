from os import getenv
from elevenlabs import ElevenLabs
from openai import AzureOpenAI

class SpeechToTextClient():
    def __init__(self, options=None):
        pass

    def generate_transcription(self, audio_buffer, options=None):
        pass


class ElevenLabsSTT(SpeechToTextClient):
    def __init__(self, options=None):
        self.client = ElevenLabs(api_key=getenv('ELEVENLABS_API_KEY'))

    def generate_transcription(self, audio_buffer, options={}):
        language = options.get("language")
        return self.client.speech_to_text.convert(file=audio_buffer.getvalue(), model_id='scribe_v1', language_code=language)

class OpenAISTT(SpeechToTextClient):
    def __init__(self, options=None):
        self.client = AzureOpenAI(
            azure_endpoint=getenv("AZURE_OPENAI_ENDPOINT"),
            api_key=getenv("AZURE_OPENAI_KEY"),
            azure_deployment="gpt-4o-mini-transcribe",
            api_version="2025-03-01-preview"
        )

    def generate_transcription(self, audio_buffer, options={}):
        language = options.get("language")
        return self.client.audio.transcriptions.create(model="gpt-4o-mini-transcribe", file=audio_buffer, language=language)
    
