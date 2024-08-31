const socket = io();

const messageForm = document.getElementById('message-form');
const messageInput = document.getElementById('message-input');
const messages = document.getElementById('messages');
const chatroomList = document.getElementById('chatroom-list');
const userList = document.getElementById('user-list');
const currentRoom = document.getElementById('current-room');
const fileInput = document.getElementById('file-input');

let activeRoom = null;
let activePrivateChat = null;

function loadChatrooms() {
    fetch('/chatrooms')
        .then(response => response.json())
        .then(rooms => {
            chatroomList.innerHTML = '<h3>Chatrooms</h3>';
            rooms.forEach(room => {
                const roomElement = document.createElement('div');
                roomElement.textContent = room.name;
                roomElement.classList.add('chatroom-item');
                roomElement.addEventListener('click', () => joinRoom(room.name));
                chatroomList.appendChild(roomElement);
            });
        });
}

function joinRoom(roomName) {
    if (activeRoom) {
        socket.emit('leave', {room: activeRoom});
    }
    socket.emit('join', {room: roomName});
    activeRoom = roomName;
    activePrivateChat = null;
    currentRoom.textContent = roomName;
    messages.innerHTML = '';
    document.querySelectorAll('.chatroom-item').forEach(item => item.classList.remove('active'));
    document.querySelector(`.chatroom-item:contains('${roomName}')`).classList.add('active');
}

function startPrivateChat(userId, username) {
    activeRoom = null;
    activePrivateChat = userId;
    currentRoom.textContent = `Chat with ${username}`;
    messages.innerHTML = '';
    document.querySelectorAll('.user-item').forEach(item => item.classList.remove('active'));
    document.querySelector(`.user-item[data-user-id="${userId}"]`).classList.add('active');
}

messageForm.addEventListener('submit', (e) => {
    e.preventDefault();
    if (messageInput.value) {
        if (activeRoom) {
            socket.emit('message', {room: activeRoom, message: messageInput.value});
        } else if (activePrivateChat) {
            socket.emit('private_message', {recipient_id: activePrivateChat, message: messageInput.value});
        }
        messageInput.value = '';
    }
});

fileInput.addEventListener('change', (e) => {
    const file = e.target.files[0];
    if (file) {
        const reader = new FileReader();
        reader.onload = function(event) {
            const fileData = event.target.result;
            if (activeRoom) {
                socket.emit('message', {room: activeRoom, message: 'File: ' + file.name, file: fileData});
            } else if (activePrivateChat) {
                socket.emit('private_message', {recipient_id: activePrivateChat, message: 'File: ' + file.name, file: fileData});
            }
        };
        reader.readAsDataURL(file);
    }
});

socket.on('message', (data) => {
    const messageElement = createMessageElement(data);
    messages.appendChild(messageElement);
    messages.scrollTop = messages.scrollHeight;
});

socket.on('private_message', (data) => {
    if (activePrivateChat === data.sender_id) {
        const messageElement = createMessageElement(data);
        messages.appendChild(messageElement);
        messages.scrollTop = messages.scrollHeight;
    } else {
        // Show notification
        showNotification(`New message from ${data.sender}`);
    }
});

socket.on('user_status_change', (data) => {
    const userElement = document.querySelector(`.user-item[data-user-id="${data.user_id}"]`);
    if (userElement) {
        userElement.classList.remove('online', 'offline', 'away');
        userElement.classList.add(data.status);
    }
});

function createMessageElement(data) {
    const messageElement = document.createElement('div');
    messageElement.classList.add('message');
    if (data.user === username) {
        messageElement.classList.add('sent');
    }

    const avatarElement = document.createElement('img');
    avatarElement.src = data.avatar || '/static/images/default_avatar.png';
    avatarElement.classList.add('message-avatar');
    messageElement.appendChild(avatarElement);

    const contentElement = document.createElement('div');
    contentElement.classList.add('message-content');

    const userElement = document.createElement('span');
    userElement.classList.add('message-user');
    userElement.textContent = data.user;
    contentElement.appendChild(userElement);

    const textElement = document.createElement('p');
    textElement.textContent = data.msg;
    contentElement.appendChild(textElement);

    if (data.file) {
        const fileElement = document.createElement('a');
        fileElement.href = data.file;
        fileElement.textContent = 'Download File';
        fileElement.download = data.msg.replace('File: ', '');
        contentElement.appendChild(fileElement);
    }

    const timeElement = document.createElement('span');
    timeElement.classList.add('message-time');
    timeElement.textContent = new Date(data.timestamp).toLocaleTimeString();
    contentElement.appendChild(timeElement);

    messageElement.appendChild(contentElement);

    if (data.user === username) {
        const editButton = document.createElement('button');
        editButton.textContent = 'Edit';
        editButton.addEventListener('click', () => editMessage(data.id, textElement));
        messageElement.appendChild(editButton);

        const deleteButton = document.createElement('button');
        deleteButton.textContent = 'Delete';
        deleteButton.addEventListener('click', () => deleteMessage(data.id));
        messageElement.appendChild(deleteButton);
    }

    return messageElement;
}

function editMessage(messageId, textElement) {
    const newContent = prompt('Edit your message:', textElement.textContent);
    if (newContent !== null) {
        socket.emit('edit_message', {message_id: messageId, new_content: newContent});
    }
}

function deleteMessage(messageId) {
    if (confirm('Are you sure you want to delete this message?')) {
        socket.emit('delete_message', {message_id: messageId});
    }
}

socket.on('message_edited', (data) => {
    const messageElement = document.querySelector(`.message[data-id="${data.id}"]`);
    if (messageElement) {
        const textElement = messageElement.querySelector('p');
        textElement.textContent = data.new_content;
        if (data.edited) {
            const editedElement = document.createElement('span');
            editedElement.classList.add('message-edited');
            editedElement.textContent = '(edited)';
            textElement.appendChild(editedElement);
        }
    }
});

socket.on('message_deleted', (data) => {
    const messageElement = document.querySelector(`.message[data-id="${data.id}"]`);
    if (messageElement) {
        messageElement.remove();
    }
});

function showNotification(message) {
    if ('Notification' in window) {
        Notification.requestPermission().then(permission => {
            if (permission === 'granted') {
                new Notification('UzZap Beta', { body: message });
            }
        });
    }
}

loadChatrooms();

// Update user status every 30 seconds
setInterval(() => {
    socket.emit('user_status', { status: 'online' });
}, 30000);
