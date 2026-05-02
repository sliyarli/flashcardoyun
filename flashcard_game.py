import tkinter as tk
from tkinter import messagebox
import socketio
import threading
from gtts import gTTS
import pygame
import io
import re
import ctypes

# Windows Şüşələnmə həlli
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

# BURAYA RENDER-DƏN ALDIĞINIZ LİNKİ YAZIN
SERVER_URL = "https://flashcardoyun.onrender.com" 

class TTSManager:
    def __init__(self):
        pygame.mixer.init()

    def speak(self, text):
        if not text: return
        def play_sound():
            try:
                tts = gTTS(text=text, lang='en')
                fp = io.BytesIO()
                tts.write_to_fp(fp)
                fp.seek(0)
                pygame.mixer.music.load(fp)
                pygame.mixer.music.play()
            except Exception as e:
                print(f"TTS Error: {e}")
        threading.Thread(target=play_sound, daemon=True).start()

class MultiplayerFlashcardApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Multiplayer Flashcards - Wait for Friend")
        self.root.geometry("1000x700")
        
        self.tts = TTSManager()
        self.sio = socketio.Client()
        
        self.current_word = ""
        self.options = []
        self.selected_answer = None
        self.has_answered = False
        
        self.colors = {
            'bg': '#1E1E1E',
            'card_bg': '#2D2D2D',
            'text': '#FFFFFF',
            'btn_bg': '#3D3D3D',
            'btn_fg': '#FFFFFF',
            'accent': '#4CAF50',
            'wrong': '#F44336',
            'wait': '#FFC107'
        }

        self.setup_ui()
        self.setup_sockets()
        
        # Serverə arxa planda qoşuluruq
        threading.Thread(target=self.connect_to_server, daemon=True).start()

    def setup_ui(self):
        self.root.configure(bg=self.colors['bg'])
        
        # Üst Panel
        top_frame = tk.Frame(self.root, bg=self.colors['bg'])
        top_frame.pack(fill=tk.X, pady=10, padx=20)
        
        self.status_label = tk.Label(top_frame, text="Serverə qoşulur...", fg=self.colors['wait'], bg=self.colors['bg'], font=("Segoe UI", 12, "bold"))
        self.status_label.pack(side=tk.LEFT)
        
        self.speak_btn = tk.Button(top_frame, text="🔊 Speak", command=self.speak_word, bg=self.colors['btn_bg'], fg=self.colors['btn_fg'], relief=tk.FLAT, font=("Segoe UI", 10))
        self.speak_btn.pack(side=tk.RIGHT)

        # Mərkəzi Söz
        self.card_frame = tk.Frame(self.root, bg=self.colors['card_bg'], bd=0)
        self.card_frame.pack(expand=True, fill=tk.BOTH, padx=40, pady=10)
        
        self.word_label = tk.Label(self.card_frame, text="...", font=("Segoe UI", 48, "bold"), bg=self.colors['card_bg'], fg=self.colors['text'], wraplength=1500)
        self.word_label.pack(expand=True)

        # Variantlar (A, B, C, D)
        self.options_frame = tk.Frame(self.root, bg=self.colors['bg'])
        self.options_frame.pack(fill=tk.BOTH, expand=True, padx=40, pady=20)
        
        self.option_buttons = []
        for i in range(4):
            btn = tk.Button(self.options_frame, text="", font=("Segoe UI", 14), bg=self.colors['btn_bg'], fg=self.colors['btn_fg'], relief=tk.FLAT, height=2, state=tk.DISABLED)
            btn.config(command=lambda b=btn, idx=i: self.select_option(idx, b))
            btn.pack(fill=tk.X, pady=5)
            self.option_buttons.append(btn)

        # Next Düyməsi
        self.next_btn = tk.Button(self.root, text="Next Word ►", command=self.request_next, font=("Segoe UI", 12, "bold"), bg=self.colors['accent'], fg="white", relief=tk.FLAT, state=tk.DISABLED)
        self.next_btn.pack(pady=20, ipadx=20)

    def connect_to_server(self):
        try:
            self.sio.connect(SERVER_URL)
        except Exception as e:
            self.update_status(f"Qoşulma xətası: {e}", self.colors['wrong'])

    def setup_sockets(self):
        @self.sio.on('system_message')
        def on_message(data):
            self.update_status(data, self.colors['wait'])

        @self.sio.on('new_question')
        def on_question(data):
            self.current_word = data['word']
            self.options = data['options']
            self.has_answered = False
            self.selected_answer = None
            
            # Ekranı yenilə
            self.word_label.config(text=self.current_word, fg=self.colors['text'])
            self.next_btn.config(state=tk.DISABLED)
            self.update_status("Sual gəldi! Seçiminizi edin.", self.colors['text'])
            
            for i, btn in enumerate(self.option_buttons):
                btn.config(text=self.options[i], bg=self.colors['btn_bg'], state=tk.NORMAL)
            
            # Sual gələn kimi avtomatik oxu
            self.speak_word()

        @self.sio.on('player_answered')
        def on_player_answered(data):
            if self.has_answered:
                self.update_status("Dostunuz da cavab verdi!", self.colors['accent'])
            else:
                self.update_status("Dostunuz cavab verdi! Sizin seçiminiz gözlənilir...", self.colors['wait'])

        @self.sio.on('show_result')
        def on_result(data):
            correct_ans = data['correct_answer']
            self.update_status("Nəticələr gəldi! 'Next' basaraq növbətini gözləyin.", self.colors['accent'])
            
            # Düymələri rənglə
            for btn in self.option_buttons:
                btn.config(state=tk.DISABLED)
                if btn.cget('text') == correct_ans:
                    btn.config(bg=self.colors['accent']) # Doğru yaşıl
                elif btn.cget('text') == self.selected_answer and self.selected_answer != correct_ans:
                    btn.config(bg=self.colors['wrong']) # Mənim səhvim qırmızı

            self.next_btn.config(state=tk.NORMAL)

        @self.sio.on('player_ready')
        def on_ready(data):
            self.update_status("Dostunuz növbəti suala keçmək istəyir...", self.colors['wait'])

    def update_status(self, text, color):
        self.status_label.config(text=text, fg=color)

    def select_option(self, idx, btn):
        if self.has_answered: return
        
        self.has_answered = True
        self.selected_answer = self.options[idx]
        
        # Seçdiyimiz düyməni bəlli edək
        btn.config(bg="#555555")
        for b in self.option_buttons:
            b.config(state=tk.DISABLED)
            
        self.update_status("Cavabınız göndərildi. Dostunuzun cavabı gözlənilir...", self.colors['wait'])
        self.sio.emit('submit_answer', {"answer": self.selected_answer})

    def request_next(self):
        self.next_btn.config(state=tk.DISABLED)
        self.update_status("Növbəti sual üçün serverə müraciət edildi. Dostunuz gözlənilir...", self.colors['wait'])
        self.sio.emit('request_next')

    def speak_word(self):
        if not self.current_word: return
        clean_word = re.sub(r'\(.*?\)', '', self.current_word).strip()
        self.tts.speak(clean_word)

if __name__ == "__main__":
    root = tk.Tk()
    app = MultiplayerFlashcardApp(root)
    root.mainloop()