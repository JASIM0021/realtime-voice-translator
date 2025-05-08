import time
import threading
import tempfile
import os
import sys
import queue
import speech_recognition as sr
from googletrans import Translator
from gtts import gTTS
from playsound import playsound
import concurrent.futures

# Global flags
listening = False
processing = False
mic_active = True  # Control mic activation

# Use a thread pool for concurrent operations
executor = concurrent.futures.ThreadPoolExecutor(max_workers=3)

# Create queues for pipeline processing
audio_queue = queue.Queue()
text_queue = queue.Queue()

# Semaphore to avoid audio feedback loops
speaking_lock = threading.Semaphore(1)

# Initialize components with optimized settings
recognizer = sr.Recognizer()
recognizer.pause_threshold = 0.3  # Reduced from 0.5
recognizer.energy_threshold = 4000  # Increased - better for speech detection
recognizer.dynamic_energy_threshold = True
recognizer.non_speaking_duration = 0.3  # Shorter silence detection

# Pre-initialize translator to avoid startup delay
translator = Translator()

def animate_listening():
    global listening
    while listening:
        sys.stdout.write('\rListening...   ')
        time.sleep(0.2)  # Faster animation
        sys.stdout.write('\rListening..  ')
        time.sleep(0.2)
        sys.stdout.write('\rListening. ')
        time.sleep(0.2)
        sys.stdout.write('\rListening   ')
        time.sleep(0.2)
    sys.stdout.write('\r             \r')

def animate_processing():
    global processing
    chars = ['|', '/', '-', '\\']
    i = 0
    while processing:
        sys.stdout.write(f'\rProcessing {chars[i]}')
        i = (i + 1) % 4
        time.sleep(0.1)
    sys.stdout.write('\r             \r')

# Pre-download and cache common responses
tts_cache = {}

def speak_text_gtts(text, lang='en'):
    """Optimized TTS function with caching and mic pause"""
    global listening, mic_active
    
    # Use semaphore to ensure only one speech at a time
    with speaking_lock:
        try:
            # Explicitly disable microphone while speaking
            mic_active = False
            listening = False
            
            # Check cache first
            if text in tts_cache:
                playsound(tts_cache[text])
                return

            # Use lower quality for faster synthesis
            tts = gTTS(text=text, lang=lang, slow=False)
            with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as fp:
                temp_filename = fp.name
            
            tts.save(temp_filename)
            playsound(temp_filename)
            
            # Cache shorter phrases (under 100 chars)
            if len(text) < 100 and len(tts_cache) < 50:  # Limit cache size
                tts_cache[text] = temp_filename
            else:
                os.remove(temp_filename)
        except Exception as e:
            print("TTS error:", e)
        finally:
            # Wait for audio system to fully release
            time.sleep(0.5)
            mic_active = True  # Re-enable microphone

def recognize_audio(audio):
    """Separated function for speech recognition"""
    try:
        # Use timeout to prevent hanging
        print("Recognizing speech...", end="\r")
        bengali_text = recognizer.recognize_google(audio, language="bn-BD", show_all=False)
        print("                      ", end="\r")  # Clear the line
        return bengali_text
    except sr.UnknownValueError:
        print("No Bengali speech detected.", end="\r")
        return None
    except Exception as e:
        print(f"\rRecognition error: {str(e)}")
        return None

def translate_text(bengali_text):
    """Separated function for translation"""
    try:
        translation = translator.translate(bengali_text, src='bn', dest='en')
        return translation.text
    except Exception as e:
        print(f"\rTranslation error: {str(e)}")
        return None

def process_audio(audio):
    global processing, mic_active
    try:
        processing = True
        mic_active = False  # Disable microphone while processing
        threading.Thread(target=animate_processing).start()
        
        # Submit recognition task to thread pool
        future_recognition = executor.submit(recognize_audio, audio)
        bengali_text = future_recognition.result(timeout=8)  # Increased timeout
        
        if not bengali_text:
            print("Speech not recognized. Please try again.")
            processing = False
            mic_active = True  # Re-enable microphone
            return
            
        sys.stdout.write('\r\033[K')  # Clear current line
        print(f"\rBengali: {bengali_text}")
        
        # Submit translation task to thread pool
        print("Translating...", end="\r")
        future_translation = executor.submit(translate_text, bengali_text)
        english_text = future_translation.result(timeout=5)  # Increased timeout
        print("              ", end="\r")  # Clear the line
        
        if not english_text:
            print("\rTranslation failed")
            processing = False
            mic_active = True  # Re-enable microphone
            return
            
        print(f"English: {english_text}\n")
        
        # Pause mic and speak the response
        print("Speaking response...", end="\r")
        speaking_thread = executor.submit(speak_text_gtts, english_text, 'en')
        speaking_thread.result()  # Wait for speaking to complete
        print("                    ", end="\r")  # Clear the line
        
        # Brief pause after speech to avoid cutting off playback
        time.sleep(0.3)
        
    except concurrent.futures.TimeoutError:
        print("\rOperation timed out. The network may be slow.")
    except Exception as e:
        print(f"\rError: {str(e)}")
    finally:
        processing = False
        mic_active = True  # Re-enable microphone

# Flag to control microphone activation
mic_active = True

def audio_callback(recognizer, audio):
    global listening, mic_active
    listening = False
    if mic_active:  # Only process audio when microphone should be active
        executor.submit(process_audio, audio)

def start_listening():
    global listening, mic_active
    
    # Try to use device index for microphone to avoid system audio
    try:
        # List available microphones
        print("Available microphones:")
        mic_list = sr.Microphone.list_microphone_names()
        for i, name in enumerate(mic_list):
            print(f"{i}: {name}")
        
        # Let user select a microphone
        try:
            mic_index = int(input("Enter the index of the microphone to use (default: 2 for MacBook Air Microphone): ") or "2")
            if mic_index < 0 or mic_index >= len(mic_list):
                print(f"Invalid index. Using default microphone index 2.")
                mic_index = 2
        except ValueError:
            print("Invalid input. Using default microphone index 2.")
            mic_index = 2
            
        print(f"Using microphone: {mic_list[mic_index]}")
        
        with sr.Microphone(device_index=mic_index) as source:
            print("Calibrating microphone...")
            recognizer.adjust_for_ambient_noise(source, duration=1.0)  # Increased calibration time
            print("Ready! Speak in Bengali...")
            
            while True:
                try:
                    # Only listen when mic_active is True
                    if mic_active:
                        listening = True
                        threading.Thread(target=animate_listening).start()
                        
                        # Use shorter timeouts for faster response
                        audio = recognizer.listen(source, timeout=1, phrase_time_limit=4)
                        listening = False
                        audio_callback(recognizer, audio)
                    else:
                        # When mic is not active, just wait a bit
                        time.sleep(0.1)
                    
                except sr.WaitTimeoutError:
                    listening = False
                    continue
                except Exception as e:
                    print(f"Listening error: {str(e)}")
                    time.sleep(1)  # Brief pause before retrying
    except Exception as e:
        print(f"Microphone setup error: {str(e)}")
        print("Falling back to default microphone")
        # Fallback to default microphone
        with sr.Microphone() as source:
            print("Calibrating fallback microphone...")
            recognizer.adjust_for_ambient_noise(source, duration=1.0)
            print("Ready! Speak in Bengali...")
            
            while True:
                try:
                    if mic_active:
                        listening = True
                        threading.Thread(target=animate_listening).start()
                        audio = recognizer.listen(source, timeout=1, phrase_time_limit=4)
                        listening = False
                        audio_callback(recognizer, audio)
                    else:
                        time.sleep(0.1)
                except sr.WaitTimeoutError:
                    listening = False
                    continue
                except Exception as e:
                    print(f"Listening error: {str(e)}")
                    time.sleep(1)

# Warm up components
def warmup():
    """Pre-initialize components to reduce first-run latency"""
    print("Warming up components...")
    # Force translator initialization
    try:
        translator.translate("hello", src='en', dest='bn')
    except:
        pass
    
    # Precache some common responses
    common_phrases = [
        "I didn't understand that",
        "Could you repeat that?",
        "Thank you",
        "How can I help you?"
    ]
    
    # Preload TTS for common phrases
    for phrase in common_phrases:
        try:
            tts = gTTS(text=phrase, lang='en', slow=False)
            with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as fp:
                temp_filename = fp.name
            
            tts.save(temp_filename)
            tts_cache[phrase] = temp_filename
        except:
            pass
            
    print("System ready!")

# Main execution
if __name__ == "__main__":
    # Run warmup in the main thread to ensure it completes
    warmup()
    
    print("Audio feedback prevention active - microphone will be disabled during playback")
    print("\nTroubleshooting tips:")
    print("1. Make sure you're speaking clearly")
    print("2. Reduce background noise")
    print("3. Select the correct microphone (likely index 2 for 'MacBook Air Microphone')")
    print("4. If recognition fails, try adjusting your speaking volume")
    print("5. Press Ctrl+C to exit the program\n")
    
    # Start main listening thread
    listening_thread = threading.Thread(target=start_listening)
    listening_thread.daemon = True
    listening_thread.start()

    try:
        while True:
            time.sleep(0.1)
    except KeyboardInterrupt:
        print("\nExiting...")
        # Clean up cached files
        for filename in tts_cache.values():
            try:
                os.remove(filename)
            except:
                pass
        executor.shutdown(wait=False)
        sys.exit(0)
