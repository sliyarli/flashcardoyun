from flask import Flask, request
from flask_socketio import SocketIO, emit
import random
import os

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

players = {}
flashcards = []
current_question = None
current_index = 0
answers_received = 0

def send_next_question():
    global current_index, current_question, flashcards
    
    if current_index >= len(flashcards):
        socketio.emit('system_message', "Bütün sözlər bitdi! Təbriklər!")
        socketio.emit('game_over')
        return
        
    correct_card = flashcards[current_index]
    word = correct_card[0]
    correct_translation = correct_card[1]
    
    # Bütün fərqli tərcümələri tap və 3 yalnış variant seç
    all_translations = list(set([c[1] for c in flashcards if c[1] != correct_translation]))
    wrong_options = random.sample(all_translations, min(3, len(all_translations)))
    
    options = wrong_options + [correct_translation]
    random.shuffle(options)
    
    current_question = {
        "word": word,
        "options": options,
        "correct": correct_translation
    }
    
    socketio.emit('new_question', {
        "word": word,
        "options": options,
        "current": current_index + 1,
        "total": len(flashcards)
    })

@socketio.on('connect')
def handle_connect():
    player_id = request.sid
    if len(players) < 2:
        players[player_id] = {"score": 0, "last_answer": None, "ready_for_next": False}
        emit('system_message', "Serverə qoşuldunuz. Digər oyunçu gözlənilir...", room=player_id)
        
        if len(players) == 2:
            if not flashcards:
                socketio.emit('system_message', "İki oyunçu da hazırdır! Xahiş olunur biriniz CSV faylını yükləyin.")
            else:
                # Kimsə sonradan düşüb təzədən qoşulsa, qaldığı yerdən davam edir
                if current_question:
                    emit('new_question', {
                        "word": current_question["word"], 
                        "options": current_question["options"],
                        "current": current_index + 1,
                        "total": len(flashcards)
                    }, room=player_id)
    else:
        emit('system_message', "Server doludur.", room=player_id)

@socketio.on('disconnect')
def handle_disconnect():
    player_id = request.sid
    if player_id in players:
        del players[player_id]
        socketio.emit('system_message', "Digər oyunçu ayrıldı. Gözlənilir...")

@socketio.on('upload_words')
def handle_upload(data):
    global flashcards, current_index, answers_received
    if len(data['words']) < 4:
        emit('system_message', "Sözlər ən az 4 dənə olmalıdır!", room=request.sid)
        return
        
    flashcards = data['words']
    random.shuffle(flashcards) # Yüklənən kimi sözləri qarışdırırıq
    current_index = 0
    answers_received = 0
    
    for p in players.values():
        p["score"] = 0
        p["last_answer"] = None
        p["ready_for_next"] = False
        
    socketio.emit('system_message', f"{len(flashcards)} söz yükləndi! Oyun başlayır...")
    send_next_question()

@socketio.on('submit_answer')
def handle_answer(data):
    global answers_received
    player_id = request.sid
    
    if player_id in players and players[player_id]["last_answer"] is None:
        players[player_id]["last_answer"] = data["answer"]
        answers_received += 1
        
        socketio.emit('player_answered', {"count": answers_received})
        
        if answers_received == 2:
            results = []
            for pid, p_data in players.items():
                is_correct = (p_data["last_answer"] == current_question["correct"])
                if is_correct: p_data["score"] += 1
                results.append({"id": pid, "is_correct": is_correct})
            
            socketio.emit('show_result', {"correct_answer": current_question["correct"]})

@socketio.on('request_next')
def handle_next():
    global current_index, answers_received
    player_id = request.sid
    
    if player_id in players:
        players[player_id]["ready_for_next"] = True
        socketio.emit('player_ready')
        
        if all(p["ready_for_next"] for p in players.values()):
            current_index += 1
            answers_received = 0
            for p in players.values():
                p["last_answer"] = None
                p["ready_for_next"] = False
            send_next_question()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    socketio.run(app, host='0.0.0.0', port=port)