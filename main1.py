from transformers import Wav2Vec2ForCTC, Wav2Vec2Processor
import torch
import librosa

# Load model
processor = Wav2Vec2Processor.from_pretrained("facebook/wav2vec2-large-xlsr-53")
model = Wav2Vec2ForCTC.from_pretrained("facebook/wav2vec2-large-xlsr-53")

# Load and process audio
audio, rate = librosa.load("jasim_voice.wav", sr=16000)
input_values = processor(audio, return_tensors="pt", sampling_rate=16000).input_values

# Get transcription
with torch.no_grad():
    logits = model(input_values).logits
predicted_ids = torch.argmax(logits, dim=-1)
bengali_text = processor.batch_decode(predicted_ids)[0]

print("Recognized Bengali Text:", bengali_text)
