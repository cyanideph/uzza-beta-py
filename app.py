from flask import Flask, render_template, request, jsonify, session, redirect, url_for, send_from_directory
from flask_socketio import SocketIO, emit, join_room, leave_room
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import os
from datetime import datetime

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///uzzap.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'uploads'

db = SQLAlchemy(app)
socketio = SocketIO(app)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    avatar = db.Column(db.String(200), default='default_avatar.png')
    status = db.Column(db.String(20), default='offline')
    bio = db.Column(db.String(500))

class Chatroom(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)

class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.String(500), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    chatroom_id = db.Column(db.Integer, db.ForeignKey('chatroom.id'), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    edited = db.Column(db.Boolean, default=False)
    file_attachment = db.Column(db.String(200))

class PrivateMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.String(500), nullable=False)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    recipient_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    read = db.Column(db.Boolean, default=False)
    file_attachment = db.Column(db.String(200))

with app.app_context():
    db.create_all()

@app.route('/')
def index():
    if 'user_id' in session:
        return render_template('chat.html')
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            session['user_id'] = user.id
            user.status = 'online'
            db.session.commit()
            return redirect(url_for('index'))
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        email = request.form['email']
        hashed_password = generate_password_hash(password)
        new_user = User(username=username, password=hashed_password, email=email)
        db.session.add(new_user)
        db.session.commit()
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/logout')
def logout():
    user = User.query.get(session['user_id'])
    user.status = 'offline'
    db.session.commit()
    session.pop('user_id', None)
    return redirect(url_for('login'))

@app.route('/profile', methods=['GET', 'POST'])
def profile():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user = User.query.get(session['user_id'])
    if request.method == 'POST':
        user.bio = request.form['bio']
        if 'avatar' in request.files:
            file = request.files['avatar']
            if file.filename != '':
                filename = secure_filename(file.filename)
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                user.avatar = filename
        db.session.commit()
    return render_template('profile.html', user=user)

@app.route('/chatrooms')
def chatrooms():
    rooms = Chatroom.query.all()
    return jsonify([{'id': room.id, 'name': room.name} for room in rooms])

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@socketio.on('join')
def on_join(data):
    room = data['room']
    join_room(room)
    emit('status', {'msg': session.get('username') + ' has entered the room.'}, room=room)

@socketio.on('leave')
def on_leave(data):
    room = data['room']
    leave_room(room)
    emit('status', {'msg': session.get('username') + ' has left the room.'}, room=room)

@socketio.on('message')
def handle_message(data):
    room = data['room']
    content = data['message']
    user_id = session.get('user_id')
    chatroom = Chatroom.query.filter_by(name=room).first()
    if chatroom:
        new_message = Message(content=content, user_id=user_id, chatroom_id=chatroom.id)
        db.session.add(new_message)
        db.session.commit()
        emit('message', {
            'id': new_message.id,
            'user': User.query.get(user_id).username,
            'msg': content,
            'timestamp': new_message.timestamp.isoformat(),
            'avatar': User.query.get(user_id).avatar
        }, room=room)

@socketio.on('edit_message')
def edit_message(data):
    message_id = data['message_id']
    new_content = data['new_content']
    message = Message.query.get(message_id)
    if message and message.user_id == session.get('user_id'):
        message.content = new_content
        message.edited = True
        db.session.commit()
        emit('message_edited', {
            'id': message.id,
            'new_content': new_content,
            'edited': True
        }, room=message.chatroom.name)

@socketio.on('delete_message')
def delete_message(data):
    message_id = data['message_id']
    message = Message.query.get(message_id)
    if message and message.user_id == session.get('user_id'):
        db.session.delete(message)
        db.session.commit()
        emit('message_deleted', {'id': message_id}, room=message.chatroom.name)

@socketio.on('private_message')
def handle_private_message(data):
    sender_id = session.get('user_id')
    recipient_id = data['recipient_id']
    content = data['message']
    new_message = PrivateMessage(content=content, sender_id=sender_id, recipient_id=recipient_id)
    db.session.add(new_message)
    db.session.commit()
    emit('private_message', {
        'id': new_message.id,
        'sender': User.query.get(sender_id).username,
        'msg': content,
        'timestamp': new_message.timestamp.isoformat(),
        'avatar': User.query.get(sender_id).avatar
    }, room=recipient_id)

@socketio.on('read_private_message')
def read_private_message(data):
    message_id = data['message_id']
    message = PrivateMessage.query.get(message_id)
    if message and message.recipient_id == session.get('user_id'):
        message.read = True
        db.session.commit()

@socketio.on('user_status')
def user_status(data):
    user_id = session.get('user_id')
    status = data['status']
    user = User.query.get(user_id)
    if user:
        user.status = status
        db.session.commit()
        emit('user_status_change', {'user_id': user_id, 'status': status}, broadcast=True)

if __name__ == '__main__':
    socketio.run(app, debug=True)
