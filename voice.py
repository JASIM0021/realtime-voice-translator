import os
import time
import threading
import tempfile
import numpy as np
from TTS.api import TTS
import sounddevice as sd
import speech_recognition as sr
from googletrans import Translator

class VoiceAssistant:
    def __init__(self):
        self.recognizer = sr.Recognizer()
        self.translator = Translator()
        self.tts = None
        self.voice_file = "user_voice.wav"
        
        if not os.path.exists(self.voice_file):
            self.create_voice_profile()
            
        # Initialize TTS with cloned voice
        self.tts = TTS("tts_models/multilingual/multi-dataset/your_tts")
            
    def create_voice_profile(self):
        """Record user's voice sample for cloning"""
        print("\nFirst-time setup: Please read this sentence in English:")
        print("'The quick brown fox jumps over the lazy dog'")
        
        with sr.Microphone() as source:
            try:
                audio = self.recognizer.listen(source, timeout=10)
                with open(self.voice_file, "wb") as f:
                    f.write(audio.get_wav_data())
                print("Voice sample saved successfully!")
            except Exception as e:
                print(f"Recording failed: {str(e)}")

    def speak_with_cloned_voice(self, text):
        """Generate speech using cloned voice"""
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as fp:
            self.tts.tts_to_file(
                text=text,
                speaker_wav=self.voice_file,
                file_path=fp.name
            )
            playsound(fp.name)
            os.unlink(fp.name)

# Usage example
if __name__ == "__main__":
    assistant = VoiceAssistant()
    assistant.speak_with_cloned_voice("Hello! This is your cloned voice speaking.")
