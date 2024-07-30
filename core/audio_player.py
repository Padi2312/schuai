from pydub import AudioSegment
from pydub.playback import _play_with_simpleaudio


class AudioPlayer:
    @staticmethod
    def play_audio(file_path):
        """Play audio file using pydub."""
        audio = AudioSegment.from_file(file_path)
        return _play_with_simpleaudio(audio)
