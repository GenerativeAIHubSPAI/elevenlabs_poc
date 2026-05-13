from elevenlabs import ElevenLabs
from os import getenv
import wave
import io

class TextToSpeechClient():

    def __init__(self, options=None):
        pass

    def generate_audio_response(self, options=None):
        pass


class ElevenLabsTTS(TextToSpeechClient):

    def __init__(self, options=None):
        self.client = ElevenLabs(api_key=getenv('ELEVENLABS_API_KEY'))
        

    def generate_audio_response(self, message, options={}):
        voice_id = options.get("voice_id") or 'UOIqAnmS11Reiei1Ytkc'
        out =  self.client.text_to_speech.convert(voice_id=voice_id, text=message, model_id='eleven_turbo_v2_5', output_format='pcm_24000')

        audio = b''.join(out)

        wav_buffer = io.BytesIO()

        # Create WAV file with proper parameters
        with wave.open(wav_buffer, "wb") as wav_file:
            wav_file.setnchannels(1)  # mono
            wav_file.setsampwidth(2)  # 2 bytes per sample (16-bit)
            wav_file.setframerate(24000)  # sample rate (24kHz PCM)
            wav_file.writeframes(audio)

        # Reset buffer position
        wav_buffer.seek(0)
        frames = wav_file.getnframes()
        rate = wav_file.getframerate()

        duration = frames / float(rate)

        return wav_buffer.getvalue()
