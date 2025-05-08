from flask import Flask, render_template, request
from flask_socketio import SocketIO, join_room, leave_room

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
socketio = SocketIO(app, cors_allowed_origins="*")

rooms = {}

@socketio.on('connect')
def handle_connect():
    print(f"Client connected: {request.sid}")

@socketio.on('join_room')
def handle_join_room(data):
    room = data['room']
    join_room(room)
    
    if room not in rooms:
        rooms[room] = []
    
    rooms[room].append(request.sid)
    emit('existing_users', {'users': rooms[room]}, room=request.sid)
    emit('user_joined', {'sid': request.sid}, room=room, include_self=False)

@socketio.on('disconnect')
def handle_disconnect():
    for room, users in rooms.items():
        if request.sid in users:
            users.remove(request.sid)
            emit('user_left', {'sid': request.sid}, room=room)
            break

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
