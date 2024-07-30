import os

from groq import Groq

from core.logger import log


class Transcriber:
    def __init__(self):
        self.speech_to_text_client = Groq()

    def transcribe_file(self, filename):
        """Transcribe audio using OpenAI's Whisper model."""
        log.debug(f"Transcribing file: {filename}")
        with open(filename, "rb") as file:
            transcription = self.speech_to_text_client.audio.transcriptions.create(
                file=(filename, file.read()),
                model="whisper-large-v3",
                prompt="Specify context or spelling",
                response_format="json",
            )
        os.remove(filename)
        log.info(f"Transcription: {transcription.text}")
        return transcription.text
