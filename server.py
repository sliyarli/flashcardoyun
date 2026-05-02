from flask import Flask, request
from flask_socketio import SocketIO, emit
import csv
import random
import glob
import os

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

players = {}
flashcards = []
current_question = None
answers_received = 0

def load_csv():
    global flashcards
    # Qovluqdakı istənilən CSV faylını avtomatik tapır
    csv_files = glob.glob("*.csv")
    if not csv_files:
        print("CSV faylı tapılmadı!")
        return
        
    try:
        with open(csv_files[0], 'r', encoding='utf-8-sig') as f:
            reader = csv.reader(f)
            next(reader, None) # Başlığı atla
            flashcards = [row[:2] for row in reader if len(row) >= 2]
    except Exception as e:
        print(f"CSV Error: {e}")

load_csv()

def generate_question():
    if not flashcards:
        return {"word": "CSV Xətası", "options": ["A", "B", "C", "D"], "correct": "A"}
    
    correct_card = random.choice(flashcards)
    word = correct_card[0]
    correct_translation = correct_card[1]
    
    wrong_options = [card[1] for card in flashcards if card[1] != correct_translation]
    wrong_options = list(set(wrong_options)) # Eyni sözlərin təkrarlanmasının qarşısını alır
    wrong_options = random.sample(wrong_options, min(3, len(wrong_options)))
    
    options = wrong_options + [correct_translation]
    random.shuffle(options)
    
    return {
        "word": word,
        "options": options,
        "correct": correct_translation
    }

@socketio.on('connect')
def handle_connect():
    global current_question
    player_id = request.sid
    if len(players) < 2:
        players[player_id] = {"score": 0, "last_answer": None, "ready_for_next": False}
        emit('system_message', "Serverə qoşuldunuz. Digər oyunçu gözlənilir...", room=player_id)
        
        if len(players) == 2:
            socketio.emit('system_message', "Oyunçu 2 qoşuldu! Oyun başlayır...")
            if not current_question:
                current_question = generate_question()
            socketio.emit('new_question', {"word": current_question["word"], "options": current_question["options"]})
    else:
        emit('system_message', "Server doludur (Maks 2 nəfər).", room=player_id)

@socketio.on('disconnect')
def handle_disconnect():
    player_id = request.sid
    if player_id in players:
        del players[player_id]
        socketio.emit('system_message', "Digər oyunçu serverdən ayrıldı.")

@socketio.on('submit_answer')
def handle_answer(data):
    global answers_received
    player_id = request.sid
    
    if player_id in players and players[player_id]["last_answer"] is None:
        players[player_id]["last_answer"] = data["answer"]
        answers_received += 1
        
        socketio.emit('player_answered', {"player": "Oyunçu"})
        
        if answers_received == 2:
            results = []
            for pid, p_data in players.items():
                is_correct = (p_data["last_answer"] == current_question["correct"])
                if is_correct:
                    p_data["score"] += 1
                results.append({
                    "id": pid,
                    "answer": p_data["last_answer"],
                    "is_correct": is_correct,
                    "score": p_data["score"]
                })
            
            socketio.emit('show_result', {
                "correct_answer": current_question["correct"],
                "results": results
            })

@socketio.on('request_next')
def handle_next():
    global current_question, answers_received
    player_id = request.sid
    
    if player_id in players:
        players[player_id]["ready_for_next"] = True
        socketio.emit('player_ready', {"player": "Oyunçu"})
        
        if all(p["ready_for_next"] for p in players.values()):
            answers_received = 0
            for p in players.values():
                p["last_answer"] = None
                p["ready_for_next"] = False
            
            current_question = generate_question()
            socketio.emit('new_question', {"word": current_question["word"], "options": current_question["options"]})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    socketio.run(app, host='0.0.0.0', port=port)