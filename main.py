import os

import numpy as np
from openwakeword import utils
from openwakeword.model import Model

from core.audio.audio_player import AudioPlayer
from core.audio.audio_recorder import AudioRecorder
from core.audio.transcriber import Transcriber
from core.logger import log
from core.chat_assistant import ChatAssistant
from core.text_to_speech import TextToSpeech

# Constants
MODEL_PATH = "alexa"
INFERENCE_FRAMEWORK = "onnx"

# One-time download of all pre-trained models
utils.download_models()

owwModel = Model(wakeword_models=[MODEL_PATH], inference_framework=INFERENCE_FRAMEWORK)


class ConversationalAssistant:
    def __init__(self):
        self.recorder = AudioRecorder()
        self.player = AudioPlayer()
        self.transcriber = Transcriber()

        self.processor = ChatAssistant()
        self.speech_generator = TextToSpeech()

    def conversational_mode(self):
        self.recorder.play_beep(100, 300)
        """Handle conversational interactions with advanced features."""
        while True:
            audio_data = np.frombuffer(self.recorder.read_chunk(), dtype=np.int16)
            prediction = owwModel.predict(audio_data)

            # Check if any score exceeds 0.5
            if any(max(score) > 0.5 for score in owwModel.prediction_buffer.values()):
                output_filename = self.recorder.record_audio()
                owwModel.reset()
                transcription_text = self.transcriber.transcribe_file(output_filename)
                response_text = self.processor.process_text_with_openai(
                    transcription_text
                )
                speech_file_path = self.speech_generator.generate_speech_ttsopenai(
                    response_text
                )

                audio_player = self.player.play_audio(speech_file_path)
                while audio_player.is_playing():
                    self.recorder.mic_stream.stop_stream()
                    pass
                self.recorder.mic_stream.start_stream()
                os.remove(speech_file_path)


if __name__ == "__main__":
    log.info("Starting Conversational Assistant")
    assistant = ConversationalAssistant()
    assistant.conversational_mode()
