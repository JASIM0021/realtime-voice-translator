import time
import threading
import tempfile
import os
import sys
import speech_recognition as sr
from googletrans import Translator
from gtts import gTTS
from playsound import playsound

# Global flag for animation
listening = False
processing = False

recognizer = sr.Recognizer()
translator = Translator()

# Adjust recognizer parameters for faster response
recognizer.pause_threshold = 0.5  # Shorter silence to end phrase
recognizer.energy_threshold = 4000  # Adjust based on your microphone
recognizer.dynamic_energy_threshold = True

def animate_listening():
    global listening
    while listening:
        sys.stdout.write('\rListening...   ')
        time.sleep(0.3)
        sys.stdout.write('\rListening..  ')
        time.sleep(0.3)
        sys.stdout.write('\rListening. ')
        time.sleep(0.3)
        sys.stdout.write('\rListening   ')
        time.sleep(0.3)
    sys.stdout.write('\r             \r')  # Clear line

def animate_processing():
    global processing
    chars = ['|', '/', '-', '\\']
    i = 0
    while processing:
        sys.stdout.write(f'\rProcessing {chars[i]}')
        i = (i + 1) % 4
        time.sleep(0.1)
    sys.stdout.write('\r             \r')  # Clear line

def speak_text_gtts(text, lang='en'):
    try:
        tts = gTTS(text=text, lang=lang)
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as fp:
            temp_filename = fp.name
        tts.save(temp_filename)
        playsound(temp_filename)
        os.remove(temp_filename)
    except Exception as e:
        print("TTS error:", e)

def process_audio(audio):
    global processing
    try:
        processing = True
        threading.Thread(target=animate_processing).start()
        
        # Faster recognition with shorter timeout
        bengali_text = recognizer.recognize_google(audio, language="bn-BD", show_all=False)
        sys.stdout.write('\r\033[K')  # Clear current line
        print(f"\rBengali: {bengali_text}")
        
        translation = translator.translate(bengali_text, src='bn', dest='en')
        english_text = translation.text
        print(f"English: {english_text}\n")
        
        # Speak in separate thread to avoid blocking
        threading.Thread(target=speak_text_gtts, args=(english_text, 'en')).start()
        
    except sr.UnknownValueError:
        print("\rCould not understand audio")
    except Exception as e:
        print(f"\rError: {str(e)}")
    finally:
        processing = False

def audio_callback(recognizer, audio):
    global listening
    listening = False
    threading.Thread(target=process_audio, args=(audio,)).start()

# Start listening
mic = sr.Microphone()
with mic as source:
    print("Calibrating microphone...")
    recognizer.adjust_for_ambient_noise(source, duration=1)
    print("Ready!")

def start_listening():
    global listening
    while True:
        try:
            with mic as source:
                listening = True
                threading.Thread(target=animate_listening).start()
                audio = recognizer.listen(source, timeout=2, phrase_time_limit=5)
                listening = False
                audio_callback(recognizer, audio)
        except sr.WaitTimeoutError:
            continue
        except Exception as e:
            print(f"Error: {str(e)}")
            break

# Start main thread
listening_thread = threading.Thread(target=start_listening)
listening_thread.daemon = True
listening_thread.start()

try:
    while True: 
        time.sleep(0.1)
except KeyboardInterrupt:
    print("\nExiting...")
    sys.exit(0)
