import os
import tempfile
import threading
from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit, join_room, leave_room
from speech_recognition import Recognizer, AudioFile
from googletrans import Translator
from gtts import gTTS

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
socketio = SocketIO(app, cors_allowed_origins="*")

recognizer = Recognizer()
translator = Translator()

# Room management
rooms = {}
user_data = {}

def process_audio(audio_path, lang, room, sid):
    try:
        with AudioFile(audio_path) as source:
            audio = recognizer.record(source)
            text = recognizer.recognize_google(audio, language=lang)
            print(f"Recognized ({lang}): {text}")
            
            # Translate to all target languages in the room
            targets = set([u['language'] for u in user_data[room].values()])
            for target in targets:
                translation = translator.translate(text, src=lang.split('-')[0], dest=target).text
                tts = gTTS(translation, lang=target)
                with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as fp:
                    tts.save(fp.name)
                    emit('translated_audio', {
                        'text': translation,
                        'path': fp.name,
                        'lang': target,
                        'sender': sid
                    }, room=room)
    except Exception as e:
        print(f"Processing error: {e}")

@socketio.on('connect')
def handle_connect():
    print(f"Client connected: {request.sid}")
    emit('connection_response', {'status': 'connected', 'sid': request.sid})

@socketio.on('join_room')
def handle_join_room(data):
    room = data['room']
    language = data['language']
    join_room(room)
    
    if room not in user_data:
        user_data[room] = {}
    
    user_data[room][request.sid] = {
        'language': language,
        'camera_on': False,
        'mic_on': False
    }
    
    # Notify others in the room
    emit('user_joined', {
        'sid': request.sid,
        'users': list(user_data[room].keys())
    }, room=room, include_self=False)
    
    # Send existing users to new member
    emit('existing_users', {
        'users': list(user_data[room].keys())
    }, room=request.sid)

@socketio.on('audio_chunk')
def handle_audio_chunk(data):
    try:
        room = data['room']
        lang = user_data[room][request.sid]['language']
        
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as fp:
            fp.write(data['chunk'])
            threading.Thread(target=process_audio, args=(fp.name, lang, room, request.sid)).start()
    except Exception as e:
        print(f"Audio handling error: {e}")

@socketio.on('disconnect')
def handle_disconnect():
    for room in user_data:
        if request.sid in user_data[room]:
            del user_data[room][request.sid]
            emit('user_left', {'sid': request.sid}, room=room)
            break

# WebRTC Signaling
@socketio.on('offer')
def handle_offer(data):
    emit('offer', {
        'offer': data['offer'],
        'sender': request.sid
    }, room=data['target'])

@socketio.on('answer')
def handle_answer(data):
    emit('answer', {
        'answer': data['answer'],
        'sender': request.sid
    }, room=data['target'])

@socketio.on('ice_candidate')
def handle_ice_candidate(data):
    emit('ice_candidate', {
        'candidate': data['candidate'],
        'sender': request.sid
    }, room=data['target'])

@app.route('/')
def index():
    return render_template('index.html')

if __name__ == '__main__':
    socketio.run(app, debug=True, host='0.0.0.0',port=3000)
