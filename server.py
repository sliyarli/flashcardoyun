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
        # OYUN BİTDİ - LEADERBOARD HAZIRLA
        sorted_players = sorted(players.values(), key=lambda x: x["score"], reverse=True)
        leaderboard = [{"username": p["username"], "score": p["score"]} for p in sorted_players]
        
        socketio.emit('game_over', {"leaderboard": leaderboard})
        return
        
    correct_card = flashcards[current_index]
    word = correct_card[0]
    correct_translation = correct_card[1]
    
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

@socketio.on('join_game')
def handle_join(data):
    player_id = request.sid
    username = data.get('username', 'Anonim')
    
    if len(players) < 2:
        players[player_id] = {"username": username, "score": 0, "last_answer": None, "ready_for_next": False}
        emit('system_message', f"Xoş gəldin, {username}! Digər oyunçu gözlənilir...", room=player_id)
        
        if len(players) == 2:
            socketio.emit('system_message', "Hər iki oyunçu hazırdır! Xahiş olunur biriniz CSV faylını yükləyin.")
    else:
        emit('system_message', "Server doludur.", room=player_id)

@socketio.on('disconnect')
def handle_disconnect():
    player_id = request.sid
    if player_id in players:
        del players[player_id]
        socketio.emit('system_message', "Digər oyunçu ayrıldı.")

@socketio.on('upload_words')
def handle_upload(data):
    global flashcards, current_index, answers_received
    if len(data['words']) < 4:
        emit('system_message', "Sözlər ən az 4 dənə olmalıdır!", room=request.sid)
        return
        
    flashcards = data['words']
    random.shuffle(flashcards)
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
            correct_users = []
            
            for pid, p_data in players.items():
                is_correct = (p_data["last_answer"] == current_question["correct"])
                if is_correct: 
                    p_data["score"] += 1
                    correct_users.append(p_data["username"])
                    
                results.append({"id": pid, "is_correct": is_correct})
            
            # KİMİN DÜZ TAPDIĞINI MÜƏYYƏN EDİRİK
            if len(correct_users) == 2:
                result_msg = "Möhtəşəm! Hər ikiniz düzgün cavab verdiniz! 🎉"
            elif len(correct_users) == 1:
                result_msg = f"{correct_users[0]} düzgün cavab verdi! ✅"
            else:
                result_msg = "Təəssüf ki, heç kim düz tapmadı! ❌"
                
            socketio.emit('show_result', {
                "correct_answer": current_question["correct"],
                "result_msg": result_msg
            })

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