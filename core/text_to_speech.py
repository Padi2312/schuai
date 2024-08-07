import os
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests
from elevenlabs import save
from elevenlabs.client import ElevenLabs
from pydub import AudioSegment

from core.logger import log


class TextToSpeech:
    def __init__(self, output_folder="recordings"):
        self.ELVEN_LABS_VOICE_ID = "cgSgspJ2msm6clMCkdW9"
        self.client = ElevenLabs()
        self.output_folder = output_folder
        os.makedirs(self.output_folder, exist_ok=True)  # Ensure output folder exists
        log.info(f"Initialized TextToSpeech with output folder: {self.output_folder}")

    def generate_speech(self, text):
        """Generate speech from text using ElevenLabs."""
        speech_file_path = os.path.join(self.output_folder, "speech.mp3")
        log.info("Generating speech using ElevenLabs.")
        response = self.client.generate(
            text=text, voice=self.ELVEN_LABS_VOICE_ID, model="eleven_turbo_v2_5"
        )
        save(response, speech_file_path)
        log.info(f"Speech generated and saved to {speech_file_path}")
        return speech_file_path

    def generate_speech_coqui(self, text):
        """Generate speech from text using Coqui TTS."""
        speech_file_path = Path(self.output_folder) / "speech_coqui.mp3"
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

        log.info("Start generating speech using Coqui TTS")
        response = requests.post(url, headers=headers, json=payload)

        if response.status_code == 200:
            audio_data = response.content
            with open(speech_file_path, "wb") as file:
                file.write(audio_data)
            log.info(f"Coqui TTS speech generated and saved to {speech_file_path}")
            return speech_file_path
        else:
            log.error(
                f"Coqui TTS failed with status {response.status_code} - {response.text}"
            )
            return None

    def generate_audio_chunk(self, url, headers, payload, chunk, index):
        """Generate a single audio chunk."""
        payload["input"] = chunk
        log.debug(
            f"Generating audio chunk {index}: {chunk[:30]}..."
        )  # Log only the first 30 chars
        response = requests.post(url, headers=headers, json=payload)

        if response.status_code == 200:
            temp_file_path = os.path.join(
                self.output_folder, f"temp_speech_{index}.mp3"
            )
            with open(temp_file_path, "wb") as audio_file:
                audio_file.write(response.content)
            log.debug(f"Chunk {index} generated and saved to {temp_file_path}")
            return temp_file_path
        else:
            log.error(
                f"Chunk {index} generation failed with status {response.status_code} - {response.text}"
            )
            return None

    def generate_speech_ttsopenai(self, text):
        """Generate speech from text using TTS OpenAI."""
        speech_file_path = os.path.join(self.output_folder, "speech_openai.mp3")
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

        log.info("Start generating speech")
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
                current_chunk += " " + sentence if current_chunk else sentence
            else:
                if current_chunk:
                    chunks.append(current_chunk)
                current_chunk = sentence

        if current_chunk:
            chunks.append(current_chunk)

        # Generate audio for each chunk and store the temporary file paths
        with ThreadPoolExecutor() as executor:
            futures = {
                executor.submit(
                    self.generate_audio_chunk, url, headers, payload.copy(), chunk, i
                ): i
                for i, chunk in enumerate(chunks)
            }

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
                log.debug(f"Temporary file {audio_file} deleted.")

        end_time = time.time()
        log.info(f"Finished generating speech in {end_time - start_time:.2f}s and saved to {speech_file_path}")
        return speech_file_path
