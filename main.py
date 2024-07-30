import logging
import os

import numpy as np
import pyaudio
from dotenv import load_dotenv
from openwakeword import utils
from openwakeword.model import Model

from core.audio_player import AudioPlayer
from core.audio_recorder import AudioRecorder
from core.speech_processor import SpeechProcessor
from core.text_to_speech import TextToSpeech

load_dotenv()  # Load environment variables from .env

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO,
    handlers=[logging.StreamHandler()],
)

# Constants
MODEL_PATH = "alexa"
ELVEN_LABS_VOICE_ID = "cgSgspJ2msm6clMCkdW9"
INFERENCE_FRAMEWORK = "onnx"
SILENCE_THRESHOLD = 1500
SILENCE_DURATION = 1
OUTPUT_FILENAME_TEMPLATE = "recorded_audio_{index}.wav"
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000
CHUNK = 4096
GAIN_FACTOR = 1.5  # Factor to amplify the audio

# One-time download of all pre-trained models
utils.download_models()

owwModel = Model(wakeword_models=[MODEL_PATH], inference_framework=INFERENCE_FRAMEWORK)


class ConversationalAssistant:
    def __init__(self):
        self.recorder = AudioRecorder()
        self.player = AudioPlayer()

        self.processor = SpeechProcessor()
        self.speech_generator = TextToSpeech()

    def conversational_mode(self):
        self.recorder.play_beep(100, 300)
        """Handle conversational interactions with advanced features."""
        while True:
            audio_data = np.frombuffer(
                self.recorder.mic_stream.read(CHUNK), dtype=np.int16
            )
            prediction = owwModel.predict(audio_data)

            # Check if any score exceeds 0.5
            if any(max(score) > 0.5 for score in owwModel.prediction_buffer.values()):
                output_filename = self.recorder.record_audio()
                owwModel.reset()
                transcription_text = self.processor.transcribe_audio(output_filename)
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
    logging.info("\n\n")
    logging.info("#" * 100)
    logging.info("Listening for wakewords...")
    logging.info("#" * 100)

    assistant = ConversationalAssistant()
    assistant.conversational_mode()
