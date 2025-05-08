import time
import threading
import tempfile
import os
import speech_recognition as sr
from googletrans import Translator
from gtts import gTTS
from playsound import playsound

recognizer = sr.Recognizer()
translator = Translator()

def speak_text_gtts(text, lang='en'):
    try:
        print(f"Speaking: {text}")  # Debug output
        tts = gTTS(text=text, lang=lang)
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as fp:
            temp_filename = fp.name
        tts.save(temp_filename)
        playsound(temp_filename)
        os.remove(temp_filename)
    except Exception as e:
        print("TTS error:", e)

def process_audio(recognizer, audio):
    try:
        print("Processing audio...")  # Debug output
        bengali_text = recognizer.recognize_google(audio, language="bn-BD")
        print("Bengali Transcript:", bengali_text)
        
        # Translation step
        translation = translator.translate(bengali_text, src='bn', dest='en')
        english_text = translation.text
        print("English Translation:", english_text)
        
        speak_text_gtts(english_text, lang='en')
    except sr.UnknownValueError:
        print("Could not understand audio.")
    except sr.RequestError as e:
        print(f"Speech recognition request error: {e}")
    except Exception as e:
        print(f"Unexpected error: {e}")  # Catch-all for other exceptions

# Check available microphones (debug step)
print("Available microphones:", sr.Microphone.list_microphone_names())

mic = sr.Microphone()
with mic as source:
    print("Calibrating microphone... Please wait.")
    recognizer.adjust_for_ambient_noise(source, duration=2)
    print("Calibration complete. Start speaking...")

# Verify microphone access
def test_microphone():
    with sr.Microphone() as source:
        print("Testing microphone... Speak now!")
        audio = recognizer.listen(source, timeout=5)
        print("Audio captured for testing")
        try:
            test_text = recognizer.recognize_google(audio)
            print("Test recognition:", test_text)
        except Exception as e:
            print("Test recognition failed:", e)

# Uncomment to run microphone test
# test_microphone()

stop_listening = recognizer.listen_in_background(mic, process_audio)
print("Listening continuously. Press Ctrl+C to exit.")

try:
    while True:
        time.sleep(0.1)
except KeyboardInterrupt:
    print("Exiting...")
    stop_listening(wait_for_stop=False)
