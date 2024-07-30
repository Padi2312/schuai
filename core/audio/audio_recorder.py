import logging
import os
import time
import wave

import numpy as np
import pyaudio
import simpleaudio as sa
from pydub.generators import Sine


class AudioRecorder:
    def __init__(
        self,
        RATE=16000,
        CHUNK=4096,
        FORMAT=pyaudio.paInt16,
        CHANNELS=1,
        SILENCE_THRESHOLD=1700,
        SILENCE_DURATION=1,
        GAIN_FACTOR=1.5,
        output_folder="recordings",
    ):
        self.RATE = RATE
        self.CHUNK = CHUNK
        self.GAIN_FACTOR = GAIN_FACTOR
        self.CHANNELS = CHANNELS
        self.FORMAT = FORMAT
        self.SILENCE_THRESHOLD = SILENCE_THRESHOLD
        self.SILENCE_DURATION = SILENCE_DURATION

        self.audio = pyaudio.PyAudio()
        self.mic_stream = self.audio.open(
            format=self.FORMAT,
            channels=self.CHANNELS,
            rate=self.RATE,
            input=True,
            frames_per_buffer=self.CHUNK,
        )
        self.file_index = 0

        self.output_folder = output_folder
        if not os.path.exists(output_folder):
            os.makedirs(output_folder)

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
        return np.max(np.abs(data)) < self.SILENCE_THRESHOLD

    def amplify_audio(self, data):
        """Amplify the audio data."""
        audio_data = np.frombuffer(data, dtype=np.int16)
        amplified_data = np.clip(audio_data * self.GAIN_FACTOR, -32768, 32767)
        return amplified_data.astype(np.int16)

    def record_audio(self):
        """Record audio from the microphone and save it to a file."""
        logging.info("Recording...")
        self.play_beep(100, 800)
        frames = []
        silence_start = None

        while True:
            data = self.mic_stream.read(self.CHUNK, exception_on_overflow=False)
            amplified_data = self.amplify_audio(data)
            frames.append(amplified_data)

            audio_data = np.frombuffer(data, dtype=np.int16)
            if self.is_silent(audio_data):
                if silence_start is None:
                    silence_start = time.time()
                elif time.time() - silence_start > self.SILENCE_DURATION:
                    break
            else:
                silence_start = None

        logging.info("Finished recording")
        self.play_beep(100, 250)

        OUTPUT_FILENAME_TEMPLATE = os.path.join(
            self.output_folder, f"recorded_audio_{self.file_index}.wav"
        )
        output_filename = OUTPUT_FILENAME_TEMPLATE.format(index=self.file_index)
        with wave.open(output_filename, "wb") as wf:
            wf.setnchannels(self.CHANNELS)
            wf.setsampwidth(self.audio.get_sample_size(self.FORMAT))
            wf.setframerate(self.RATE)
            wf.writeframes(b"".join(frames))
        logging.info(f"Audio saved as {output_filename}")

        self.file_index += 1
        return output_filename

    def read_chunk(self):
        """Read a chunk of audio data from the microphone."""
        return self.mic_stream.read(self.CHUNK)
