from concurrent.futures import ThreadPoolExecutor, as_completed
import logging
import os
import re
import time
import wave
from pathlib import Path
from typing import List

import numpy as np
import pyaudio
import requests
import simpleaudio as sa
from dotenv import load_dotenv
from elevenlabs import save
from elevenlabs.client import ElevenLabs
from groq import Groq
from openai import OpenAI
from openai.types.chat import ChatCompletionMessageToolCall
from openwakeword import utils
from openwakeword.model import Model
from pydub import AudioSegment
from pydub.generators import Sine
from pydub.playback import _play_with_simpleaudio

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


class AudioRecorder:
    def __init__(self):
        self.audio = pyaudio.PyAudio()
        self.mic_stream = self.audio.open(
            format=FORMAT,
            channels=CHANNELS,
            rate=RATE,
            input=True,
            frames_per_buffer=CHUNK,
        )
        self.file_index = 0

    def play_beep(self, duration_ms=100, frequency=500):
        """Play a beep sound using simpleaudio."""

        beep = Sine(frequency).to_audio_segment(duration=duration_ms)
        audio_data = beep.raw_data
        playback_obj = sa.play_buffer(
            audio_data,
            num_channels=beep.channels,
            bytes_per_sample=beep.sample_width,
            sample_rate=beep.frame_rate,
        )
        playback_obj.wait_done()

    def is_silent(self, data):
        """Determine if the audio data is silent."""
        return np.max(np.abs(data)) < SILENCE_THRESHOLD

    def amplify_audio(self, data):
        """Amplify the audio data."""
        audio_data = np.frombuffer(data, dtype=np.int16)
        amplified_data = np.clip(audio_data * GAIN_FACTOR, -32768, 32767)
        return amplified_data.astype(np.int16)

    def record_audio(self):
        """Record audio from the microphone and save it to a file."""
        logging.info("Recording...")
        self.play_beep(100, 800)
        frames = []
        silence_start = None

        while True:
            data = self.mic_stream.read(CHUNK, exception_on_overflow=False)
            amplified_data = self.amplify_audio(data)
            frames.append(amplified_data)

            audio_data = np.frombuffer(data, dtype=np.int16)
            if self.is_silent(audio_data):
                if silence_start is None:
                    silence_start = time.time()
                elif time.time() - silence_start > SILENCE_DURATION:
                    break
            else:
                silence_start = None

        logging.info("Finished recording")
        self.play_beep(100, 250)

        output_filename = OUTPUT_FILENAME_TEMPLATE.format(index=self.file_index)
        with wave.open(output_filename, "wb") as wf:
            wf.setnchannels(CHANNELS)
            wf.setsampwidth(self.audio.get_sample_size(FORMAT))
            wf.setframerate(RATE)
            wf.writeframes(b"".join(frames))
        logging.info(f"Audio saved as {output_filename}")

        self.file_index += 1
        return output_filename


class SpeechProcessor:
    def __init__(self):
        self.client = OpenAI()
        self.text_to_speech_client = ElevenLabs()
        self.speech_to_text_client = Groq()
        self.conversation_history = []

        self.system_prompt = "Du bist die Hilfreiche Schuppen KI Assistentin. Du verhältst dich wie eine normale Person die Mitglied des Schuppens ist. Deine Antworten enthalten immer einen leichten Unterton von Sarkasmus und Ironie."

    def transcribe_audio(self, filename):
        """Transcribe audio using OpenAI's Whisper model."""
        with open(filename, "rb") as file:
            transcription = self.speech_to_text_client.audio.transcriptions.create(
                file=(filename, file.read()),
                model="whisper-large-v3",
                prompt="Specify context or spelling",
                response_format="json",
            )
        os.remove(filename)
        logging.info(f"Transcription: {transcription.text}")
        return transcription.text

    def process_text_with_openai(self, text):
        """Process text with OpenAI's chat model, maintaining conversation history."""
        self.conversation_history.append({"role": "user", "content": text})

        tools = [
            {
                "type": "function",
                "function": {
                    "name": "clear_conversation_history",
                    "description": "Clear the entire conversation history.",
                    "parameters": {
                        "type": "object",
                        "properties": {},
                    },
                },
            }
        ]

        response = self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "system", "content": self.system_prompt}]
            + self.conversation_history,
            tools=tools,
            temperature=0.7,
            tool_choice="auto",
        )

        response_message = response.choices[0].message
        tool_calls: List[ChatCompletionMessageToolCall] | None = (
            response_message.tool_calls
        )

        if tool_calls:
            # Append the tool response to the conversation history
            self.conversation_history.append(response_message)
            return self.handle_function_calls(tool_calls, response_message)
        else:
            self.conversation_history.append(
                {"role": "assistant", "content": response_message.content}
            )
            logging.info("Response: %s", response_message.content)
            return response_message.content

    def handle_function_calls(
        self, tool_calls: List[ChatCompletionMessageToolCall], response_message
    ):
        """Handle tool calls from OpenAI response."""
        available_functions = {
            "clear_conversation_history": self.clear_conversation_history,
        }
        logging.info(f"Found {len(tool_calls)} tool calls.")

        old_history = self.conversation_history.copy()
        for tool_call in tool_calls:
            function_name = tool_call.function.name
            function_to_call = available_functions.get(function_name)
            if function_to_call:
                logging.info(f"Calling function '{function_name}'...")
                function_to_call()

                # Append the tool response to the conversation history
                old_history.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "name": function_name,
                        "content": "Function executed.",
                    }
                )
            else:
                logging.warning(f"Function '{function_name}' not found.")

        # Request a new response considering the function calls
        second_response = self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "system", "content": self.system_prompt}] + old_history,
        )
        return second_response.choices[0].message.content

    def clear_conversation_history(self):
        """Clear the conversation history."""
        self.conversation_history.clear()
        logging.info("Conversation history cleared.")
        return True


class TextToSpeech:
    def __init__(self):
        self.client = ElevenLabs()

    def generate_speech(self, text):
        """Generate speech from text using ElevenLabs."""
        speech_file_path = Path(__file__).parent / "speech.mp3"
        response = self.client.generate(
            text=text, voice=ELVEN_LABS_VOICE_ID, model="eleven_turbo_v2_5"
        )
        save(response, speech_file_path)
        return speech_file_path

    def generate_speech_coqui(self, text):
        """Generate speech from text using Coqui TTS."""
        speech_file_path = Path(__file__).parent / "speech.mp3"
        url = "https://tts.nc6.conexo.support/api/v1/audio/speech/"
        token = os.getenv("COQUI_TOKEN")
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Basic {token}",
        }
        payload = {
            "text": text,
            "language": "de",
            "speaker": "german_female_anke.wav",
        }
        logging.info(f"Start generating speech for")
        response = requests.post(
            url,
            headers=headers,
            json=payload,
        )
        logging.info(f"Finished generating speech")
        if response.status_code == 200:
            audio_data = response.content

            with open(speech_file_path, "wb") as file:
                file.write(audio_data)

            return speech_file_path
        else:
            logging.error(f"{response.status_code} - {response.text}")
            return None

    def generate_audio_chunk(self, url, headers, payload, chunk, index):
        payload["input"] = chunk
        response = requests.post(url, headers=headers, json=payload)

        if response.status_code == 200:
            temp_file_path = Path(__file__).parent / f"temp_speech_{index}.mp3"
            with open(temp_file_path, "wb") as audio_file:
                audio_file.write(response.content)
            return temp_file_path
        else:
            logging.error(f"{response.status_code} - {response.text}")
            return None

    def generate_speech_ttsopenai(self, text):
        speech_file_path = Path(__file__).parent / "speech.mp3"
        temp_audio_files = []  # To hold paths of temporary audio files

        url = "https://api.ttsopenai.com/api/v1/public/text-to-speech-stream"
        headers = {
            "accept": "application/json",
            "accept-language": "de-DE,de;q=0.7",
            "authorization": "",  # Add your authorization token here
            "content-type": "application/json",
            "origin": "https://ttsopenai.com",
            "priority": "u=1, i",
            "referer": "https://ttsopenai.com/",
            "sec-ch-ua": '"Not)A;Brand";v="99", "Brave";v="127", "Chromium";v="127"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-site",
            "sec-gpc": "1",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
        }
        payload = {"model": "tts-1", "speed": 1, "voice_id": "OA005"}

        logging.info("[TTSOPENAI] Start generating speech")
        start_time = time.time()

        # Split text into sentences
        sentence_pattern = r"(?<=[.!?]) +"
        sentences = re.split(sentence_pattern, text)

        # Prepare chunks and ensure they are in order, without exceeding 500 characters
        chunks = []
        current_chunk = ""

        for sentence in sentences:
            sentence = sentence.strip()
            if len(current_chunk) + len(sentence) + 1 <= 500:
                current_chunk += (" " + sentence if current_chunk else sentence)
            else:
                if current_chunk:
                    chunks.append(current_chunk)
                current_chunk = sentence

        if current_chunk:
            chunks.append(current_chunk)

        # Generate audio for each chunk and store the temporary file paths
        with ThreadPoolExecutor() as executor:
            futures = {executor.submit(self.generate_audio_chunk, url, headers, payload.copy(), chunk, i): i
                       for i, chunk in enumerate(chunks)}

            for future in as_completed(futures):
                index = futures[future]
                temp_audio_file = future.result()
                if temp_audio_file:
                    while len(temp_audio_files) <= index:
                        temp_audio_files.append(None)
                    temp_audio_files[index] = temp_audio_file

        # Combine all audio files in the order they were processed
        combined = AudioSegment.empty()
        for audio_file in temp_audio_files:
            if audio_file:
                combined += AudioSegment.from_file(audio_file)

        # Export the combined audio file
        combined.export(speech_file_path, format="mp3")

        # Clean up temporary files
        for audio_file in temp_audio_files:
            if audio_file and Path(audio_file).exists():
                Path(audio_file).unlink()

        end_time = time.time()
        logging.info(f"[TTSOPENAI] Finished! Time taken: {end_time - start_time:.2f}s")
        return speech_file_path



class AudioPlayer:
    @staticmethod
    def play_audio(file_path):
        """Play audio file using pydub."""
        audio = AudioSegment.from_file(file_path)
        return _play_with_simpleaudio(audio)


class ConversationalAssistant:
    def __init__(self):
        self.recorder = AudioRecorder()
        self.processor = SpeechProcessor()
        self.speech_generator = TextToSpeech()
        self.player = AudioPlayer()

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
                os.remove(speech_file_path)


if __name__ == "__main__":
    logging.info("\n\n")
    logging.info("#" * 100)
    logging.info("Listening for wakewords...")
    logging.info("#" * 100)

    assistant = ConversationalAssistant()
    assistant.conversational_mode()
