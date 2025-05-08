import os
import wave
import time
import numpy as np
import pyaudio
import soundfile as sf
from scipy import signal
import speech_recognition as sr
import tempfile
import shutil
import json
import pickle
from tqdm import tqdm

class CustomVoiceTTS:
    def __init__(self, voice_samples_dir="voice_samples", 
                 voice_model_dir="voice_model",
                 sample_rate=22050):
        
        self.voice_samples_dir = voice_samples_dir
        self.voice_model_dir = voice_model_dir
        self.sample_rate = sample_rate
        self.audio_format = pyaudio.paInt16
        self.channels = 1
        self.chunk = 2048  # Increased from 1024 to 2048 to reduce overflow risk
        self.recognizer = sr.Recognizer()
        
        # Create directories if they don't exist
        os.makedirs(self.voice_samples_dir, exist_ok=True)
        os.makedirs(self.voice_model_dir, exist_ok=True)
        
        # Voice metadata
        self.voice_metadata = {
            "sample_count": 0,
            "total_duration": 0,
            "phrases": [],
            "created": time.strftime("%Y-%m-%d %H:%M:%S"),
            "sample_rate": sample_rate
        }
        
        # Load existing metadata if available
        self.metadata_file = os.path.join(self.voice_model_dir, "metadata.json")
        if os.path.exists(self.metadata_file):
            with open(self.metadata_file, "r") as f:
                self.voice_metadata = json.load(f)
    
    def record_sample(self, duration=5, prompt=None):
        """Record a voice sample for the specified duration"""
        p = pyaudio.PyAudio()
        
        # Open stream with error handling
        try:
            stream = p.open(format=self.audio_format,
                          channels=self.channels,
                          rate=self.sample_rate,
                          input=True,
                          frames_per_buffer=self.chunk,
                          input_overflow_callback=lambda: print("⚠️ Input overflow detected, try speaking a bit softer"))
        except Exception as e:
            print(f"Error opening audio stream: {e}")
            print("Trying alternative audio configuration...")
            
            # Try with a different sample rate
            alt_sample_rate = 16000
            try:
                stream = p.open(format=self.audio_format,
                             channels=self.channels,
                             rate=alt_sample_rate,
                             input=True,
                             frames_per_buffer=self.chunk * 2)
                self.sample_rate = alt_sample_rate
                print(f"Using alternative sample rate: {alt_sample_rate}")
            except Exception as e2:
                print(f"Failed to open audio stream with alternative configuration: {e2}")
                p.terminate()
                return None, None
        
        print("=" * 50)
        if prompt:
            print(f"Please read aloud: \"{prompt}\"")
        
        # Give the user a moment to prepare
        print("Get ready to speak...")
        for i in range(3, 0, -1):
            print(f"{i}...")
            time.sleep(1)
        
        print("Recording... Speak naturally!")
        
        frames = []
        try:
            for i in range(0, int(self.sample_rate / self.chunk * duration)):
                try:
                    data = stream.read(self.chunk, exception_on_overflow=False)
                    frames.append(data)
                    # Show progress
                    progress = i / int(self.sample_rate / self.chunk * duration) * 100
                    print(f"Recording: {progress:.1f}%", end="\r")
                except OSError as e:
                    print(f"\nAudio buffer overflow detected, continuing recording... {e}")
                    # Continue recording despite overflow
                    continue
            
            print("\nFinished recording!")
        except KeyboardInterrupt:
            print("\nRecording interrupted by user.")
        except Exception as e:
            print(f"\nError during recording: {e}")
        finally:
            # Always stop and close the stream
            try:
                stream.stop_stream()
                stream.close()
            except:
                pass
            p.terminate()
        
        if len(frames) == 0:
            print("No audio data recorded!")
            return None, None
            
        # Save the audio file
        sample_id = len(self.voice_metadata["phrases"])
        filename = os.path.join(self.voice_samples_dir, f"sample_{sample_id:04d}.wav")
        
        try:
            wf = wave.open(filename, 'wb')
            wf.setnchannels(self.channels)
            wf.setsampwidth(p.get_sample_size(self.audio_format))
            wf.setframerate(self.sample_rate)
            wf.writeframes(b''.join(frames))
            wf.close()
            
            # Try to transcribe what was said
            transcription = self._transcribe_audio(filename)
            
            # Update metadata
            self.voice_metadata["sample_count"] += 1
            self.voice_metadata["total_duration"] += duration
            self.voice_metadata["phrases"].append({
                "id": sample_id,
                "filename": filename,
                "duration": duration,
                "prompt": prompt,
                "transcription": transcription,
                "date_recorded": time.strftime("%Y-%m-%d %H:%M:%S")
            })
            
            # Save updated metadata
            with open(self.metadata_file, "w") as f:
                json.dump(self.voice_metadata, f, indent=2)
            
            return filename, transcription
        except Exception as e:
            print(f"Error saving audio file: {e}")
            return None, None
    
    def _transcribe_audio(self, audio_file):
        """Transcribe the recorded audio"""
        try:
            with sr.AudioFile(audio_file) as source:
                audio = self.recognizer.record(source)
                text = self.recognizer.recognize_google(audio)
                return text
        except Exception as e:
            print(f"Transcription error: {e}")
            return None
    
    def process_samples(self):
        """Process all recorded samples to prepare for TTS"""
        print("Processing voice samples...")
        
        # Create processed directory
        processed_dir = os.path.join(self.voice_model_dir, "processed")
        os.makedirs(processed_dir, exist_ok=True)
        
        # Process each sample
        for phrase in tqdm(self.voice_metadata["phrases"]):
            sample_path = phrase["filename"]
            
            if not os.path.exists(sample_path):
                print(f"Warning: Sample file {sample_path} not found.")
                continue
            
            try:
                # Load audio
                audio, sr = sf.read(sample_path)
                
                # Normalize audio
                audio = audio / (np.max(np.abs(audio)) + 1e-8)  # Prevent division by zero
                
                # Apply light compression
                audio = np.sign(audio) * np.log(1 + 5 * np.abs(audio)) / np.log(6)
                
                # Remove silence
                audio_abs = np.abs(audio)
                threshold = 0.02
                mask = audio_abs > threshold
                
                # Only trim if there's enough audio left
                if np.sum(mask) > 0.5 * len(audio):
                    start = np.argmax(mask)
                    end = len(audio) - np.argmax(mask[::-1])
                    audio = audio[start:end]
                
                # Save processed audio
                processed_path = os.path.join(processed_dir, os.path.basename(sample_path))
                sf.write(processed_path, audio, sr)
                
                # Update path in metadata
                phrase["processed_file"] = processed_path
            except Exception as e:
                print(f"Error processing sample {sample_path}: {e}")
        
        # Save updated metadata
        with open(self.metadata_file, "w") as f:
            json.dump(self.voice_metadata, f, indent=2)
        
        print(f"Processed {len(self.voice_metadata['phrases'])} voice samples.")
    
    def create_voice_model(self):
        """Create a simple voice model from the processed samples"""
        print("Creating voice model...")
        
        # This is a simple placeholder for what would typically be a much more complex process
        # A real voice model would use deep learning techniques
        
        # For our simple version, we'll just save a reference to all processed samples
        model_data = {
            "samples": self.voice_metadata["phrases"],
            "sample_rate": self.sample_rate,
            "created": time.strftime("%Y-%m-%d %H:%M:%S")
        }
        
        # Save the model
        model_path = os.path.join(self.voice_model_dir, "voice_model.pkl")
        with open(model_path, "wb") as f:
            pickle.dump(model_data, f)
        
        print(f"Voice model saved to {model_path}")
        return model_path

    def suggest_phrases(self):
        """Return a list of suggested phrases to record for voice modeling"""
        phrases = [
            "Hello, how are you today?",
            "My name is [Your Name] and this is my voice.",
            "The quick brown fox jumps over the lazy dog.",
            "This is a custom voice model for text to speech.",
            "I'm creating my own voice assistant that sounds like me.",
            "Technology is advancing rapidly in the field of artificial intelligence.",
            "Thank you for using my voice translation system.",
            "Please repeat that in English.",
            "I didn't catch what you said.",
            "It's a beautiful day outside today.",
            "I'm happy to help with your translation needs.",
            "Could you speak more slowly please?",
            "Let me translate that for you.",
            "This is a sample of my natural speaking voice.",
            "I'm recording various phrases to create a complete voice model.",
            "The system will use these recordings to generate speech.",
            "Artificial intelligence helps us communicate across languages.",
            "Voice technology has improved significantly in recent years.",
            "I hope this custom voice sounds natural and authentic.",
            "Thank you for your patience while I set up this system."
        ]
        return phrases
        
    def list_audio_devices(self):
        """List available audio input devices"""
        p = pyaudio.PyAudio()
        print("\n=== Available Audio Input Devices ===")
        
        info = p.get_host_api_info_by_index(0)
        numdevices = info.get('deviceCount')
        
        for i in range(numdevices):
            device_info = p.get_device_info_by_index(i)
            if device_info.get('maxInputChannels') > 0:
                print(f"Index {i}: {device_info.get('name')}")
        
        p.terminate()
        
        print("\nYou can select a specific device by adding:")
        print("tts = CustomVoiceTTS(input_device_index=YOUR_DEVICE_INDEX)")


def main():
    print("=" * 70)
    print("CUSTOM VOICE TTS CREATOR")
    print("=" * 70)
    print("This tool will help you create a custom TTS voice model.")
    print("You'll need to record several phrases to capture your voice characteristics.")
    print("The more samples you record, the better your voice model will sound.")
    print("\nLet's get started!\n")
    
    tts = CustomVoiceTTS()
    
    # Show menu
    while True:
        print("\n" + "=" * 50)
        print("MAIN MENU")
        print("=" * 50)
        print("1. Record new voice samples")
        print("2. Process samples & create voice model")
        print("3. View voice model stats")
        print("4. List audio devices")
        print("5. Exit")
        
        choice = input("\nEnter your choice (1-5): ")
        
        if choice == "1":
            # Recording menu
            while True:
                print("\n" + "=" * 50)
                print("RECORDING MENU")
                print("=" * 50)
                print("1. Record a custom phrase")
                print("2. Record suggested phrases")
                print("3. Return to main menu")
                
                rec_choice = input("\nEnter your choice (1-3): ")
                
                if rec_choice == "1":
                    phrase = input("Enter the phrase you want to record: ")
                    duration = int(input("Enter recording duration in seconds (3-10): "))
                    duration = max(3, min(10, duration))
                    tts.record_sample(duration=duration, prompt=phrase)
                
                elif rec_choice == "2":
                    phrases = tts.suggest_phrases()
                    print("\nSuggested phrases:")
                    for i, phrase in enumerate(phrases):
                        print(f"{i+1}. {phrase}")
                    
                    try:
                        start_idx = int(input("\nStart with phrase number (1-20): ")) - 1
                        count = int(input("How many phrases to record (1-20): "))
                        
                        start_idx = max(0, min(19, start_idx))
                        count = max(1, min(20 - start_idx, count))
                        
                        for i in range(start_idx, start_idx + count):
                            if i < len(phrases):
                                print(f"\nPhrase {i+1} of {start_idx + count}")
                                result = tts.record_sample(duration=6, prompt=phrases[i])
                                
                                if result[0] is None:  # If recording failed
                                    if input("Recording failed. Try again? (y/n): ").lower() != 'y':
                                        break
                                    i -= 1  # Try the same phrase again
                                    continue
                                
                                if i < start_idx + count - 1:
                                    input("Press Enter to continue to the next phrase...")
                    except ValueError:
                        print("Invalid input. Please enter numbers only.")
                
                elif rec_choice == "3":
                    break
                
                else:
                    print("Invalid choice, please try again.")
        
        elif choice == "2":
            if tts.voice_metadata["sample_count"] < 5:
                print("You should record at least 5 samples for a decent voice model.")
                if input("Continue anyway? (y/n): ").lower() != 'y':
                    continue
            
            print("\nProcessing samples...")
            tts.process_samples()
            
            print("\nCreating voice model...")
            model_path = tts.create_voice_model()
            
            print(f"\nVoice model created! You can now integrate it with the translator.")
            print(f"Model saved at: {model_path}")
            
            # Create integration instructions
            print("\nCreating integration instructions...")
            integration_file = "voice_tts_integration.py"
            with open(integration_file, "w") as f:
                f.write("""# Custom Voice TTS Integration
import os
import pickle
import random
import numpy as np
import soundfile as sf
from pydub import AudioSegment
from pydub.playback import play
import tempfile

class CustomVoiceSpeaker:
    def __init__(self, model_path="voice_model/voice_model.pkl"):
        # Load the voice model
        with open(model_path, "rb") as f:
            self.model = pickle.load(f)
        
        self.sample_rate = self.model.get("sample_rate", 22050)
        self.samples = self.model.get("samples", [])
        
        # Check if we have samples
        if not self.samples:
            raise ValueError("No voice samples found in the model")
        
        # Create a cache for processed audio segments
        self.audio_cache = {}
    
    def speak_text(self, text):
        \"\"\"Very simple text-to-speech using sample concatenation\"\"\"
        # For now, just play a random sample
        # In a real implementation, this would use a proper TTS system
        # trained on your voice samples
        
        if not self.samples:
            print("No voice samples available")
            return
        
        # Find samples with processed files
        valid_samples = [s for s in self.samples if s.get("processed_file")]
        
        if not valid_samples:
            print("No processed voice samples available")
            return
        
        # Choose a random sample
        sample = random.choice(valid_samples)
        processed_file = sample.get("processed_file")
        
        if os.path.exists(processed_file):
            try:
                audio = AudioSegment.from_wav(processed_file)
                print(f"Speaking using sample: {os.path.basename(processed_file)}")
                play(audio)
                return True
            except Exception as e:
                print(f"Error playing audio: {e}")
        else:
            print(f"Audio file not found: {processed_file}")
        
        return False

# Usage example
if __name__ == "__main__":
    try:
        speaker = CustomVoiceSpeaker()
        speaker.speak_text("This is a test of my custom voice.")
    except Exception as e:
        print(f"Error initializing voice: {e}")
""")
            
            print(f"\nIntegration file created: {integration_file}")
            print("To use in your translator, replace the TTS function with CustomVoiceSpeaker.")
        
        elif choice == "3":
            # Display stats
            print("\n" + "=" * 50)
            print("VOICE MODEL STATISTICS")
            print("=" * 50)
            print(f"Total samples recorded: {tts.voice_metadata['sample_count']}")
            print(f"Total audio duration: {tts.voice_metadata['total_duration']} seconds")
            print(f"Created: {tts.voice_metadata['created']}")
            
            if tts.voice_metadata["sample_count"] > 0:
                print("\nRecorded phrases:")
                for i, phrase in enumerate(tts.voice_metadata["phrases"]):
                    print(f"{i+1}. Prompt: \"{phrase.get('prompt', 'No prompt')}\"")
                    print(f"   Transcription: \"{phrase.get('transcription', 'Not transcribed')}\"")
                    print(f"   Duration: {phrase.get('duration', 0)} seconds")
            
            if tts.voice_metadata["sample_count"] < 10:
                print("\nRecommendation: Record at least 10 samples for better results.")
                
        elif choice == "4":
            # List audio devices
            tts.list_audio_devices()
        
        elif choice == "5":
            print("\nExiting Custom Voice TTS Creator. Thank you!")
            break
        
        else:
            print("Invalid choice, please try again.")

if __name__ == "__main__":
    main()
