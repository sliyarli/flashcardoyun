import tkinter as tk
from tkinter import filedialog, messagebox
import socketio
import threading
from gtts import gTTS
import pygame
import io
import re
import csv
import ctypes

# Windows Şüşələnmə (DPI) həlli
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

# SERVER LİNKİ
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
                print(f"Səs Xətası: {e}")
        threading.Thread(target=play_sound, daemon=True).start()

class MultiplayerFlashcardApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Çoxoyunçulu Söz Kartları")
        self.root.geometry("1000x750")
        
        # Pəncərəni bağlayanda soruşsun
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        self.tts = TTSManager()
        self.sio = socketio.Client()
        
        self.username = ""
        self.current_word = ""
        self.options = []
        self.selected_answer = None
        self.has_answered = False
        self.interaction_allowed = False
        
        self.colors = {
            'bg': '#1E1E1E',
            'card_bg': '#2D2D2D',
            'text': '#FFFFFF',
            'btn_bg': '#3D3D3D',
            'btn_fg': '#FFFFFF',
            'accent': '#4CAF50',
            'wrong': '#F44336',
            'wait': '#FFC107',
            'selected': '#FF9800',
            'progress': '#888888',
            'gold': '#FFD700',
            'silver': '#C0C0C0'
        }

        self.main_container = tk.Frame(self.root, bg=self.colors['bg'])
        self.main_container.pack(expand=True, fill=tk.BOTH)

        self.setup_sockets()
        self.setup_login_ui()

    def on_closing(self):
        if messagebox.askyesno("Çıxış", "emin miyiz?"):
            try:
                self.sio.disconnect()
            except:
                pass
            self.root.destroy()

    def clear_container(self):
        for widget in self.main_container.winfo_children():
            widget.destroy()

    # --- SƏHİFƏLƏR ---

    def setup_login_ui(self):
        self.clear_container()
        login_frame = tk.Frame(self.main_container, bg=self.colors['bg'])
        login_frame.pack(expand=True)
        
        tk.Label(login_frame, text="Oyuna Xoş Gəldiniz!", font=("Segoe UI", 32, "bold"), bg=self.colors['bg'], fg=self.colors['accent']).pack(pady=20)
        tk.Label(login_frame, text="İstifadəçi adınızı yazın:", font=("Segoe UI", 16), bg=self.colors['bg'], fg=self.colors['text']).pack(pady=10)
        
        self.username_entry = tk.Entry(login_frame, font=("Segoe UI", 20), justify='center', width=15)
        self.username_entry.pack(pady=10)
        self.username_entry.focus()
        
        btn = tk.Button(login_frame, text="Daxil Ol", command=self.start_connection, font=("Segoe UI", 16, "bold"), bg=self.colors['accent'], fg="white", relief=tk.FLAT, padx=20)
        btn.pack(pady=30)

    def setup_game_ui(self):
        self.clear_container()
        top_frame = tk.Frame(self.main_container, bg=self.colors['bg'])
        top_frame.pack(fill=tk.X, pady=10, padx=20)
        
        # CSV Yüklə düyməsi
        self.load_btn = tk.Button(top_frame, text="📁 CSV Yüklə", command=self.load_csv_and_send, bg=self.colors['btn_bg'], fg=self.colors['btn_fg'], relief=tk.FLAT, font=("Segoe UI", 10, "bold"))
        self.load_btn.pack(side=tk.LEFT, padx=10)
        
        self.status_label = tk.Label(top_frame, text="Qoşulur...", fg=self.colors['wait'], bg=self.colors['bg'], font=("Segoe UI", 12, "bold"))
        self.status_label.pack(side=tk.LEFT, padx=20)
        
        self.speak_btn = tk.Button(top_frame, text="🔊 Səsləndir", command=self.speak_word, bg=self.colors['btn_bg'], fg=self.colors['btn_fg'], relief=tk.FLAT, font=("Segoe UI", 10, "bold"))
        self.speak_btn.pack(side=tk.RIGHT)

        self.card_frame = tk.Frame(self.main_container, bg=self.colors['card_bg'], bd=0)
        self.card_frame.pack(expand=True, fill=tk.BOTH, padx=40, pady=10)
        
        self.word_label = tk.Label(self.card_frame, text="Giriş edildi...", font=("Segoe UI", 48, "bold"), bg=self.colors['card_bg'], fg=self.colors['text'], wraplength=1500)
        self.word_label.pack(expand=True)
        
        self.progress_label = tk.Label(self.card_frame, text="0 / 0", font=("Segoe UI", 14, "bold"), bg=self.colors['card_bg'], fg=self.colors['progress'])
        self.progress_label.pack(side=tk.BOTTOM, pady=10)

        self.options_frame = tk.Frame(self.main_container, bg=self.colors['bg'])
        self.options_frame.pack(fill=tk.BOTH, expand=True, padx=40, pady=10)
        
        self.option_buttons = []
        for i in range(4):
            btn = tk.Button(self.options_frame, text="", font=("Segoe UI", 14, "bold"), bg=self.colors['btn_bg'], fg=self.colors['btn_fg'], relief=tk.FLAT, height=2)
            btn.config(command=lambda b=btn, idx=i: self.select_option(idx, b))
            btn.pack(fill=tk.X, pady=5)
            self.option_buttons.append(btn)

        self.next_btn = tk.Button(self.main_container, text="Növbəti Söz ►", command=self.request_next, font=("Segoe UI", 12, "bold"), bg=self.colors['btn_bg'], fg="#888888", relief=tk.FLAT, state=tk.DISABLED)
        self.next_btn.pack(pady=20, ipadx=20)

    def show_leaderboard(self, leaderboard):
        self.clear_container()
        board_frame = tk.Frame(self.main_container, bg=self.colors['bg'])
        board_frame.pack(expand=True)
        
        is_tie = len(leaderboard) == 2 and leaderboard[0]['score'] == leaderboard[1]['score']
        title_text = "Bərabərə!" if is_tie else "Oyun Bitdi! Nəticələr"
        title_color = self.colors['gold'] if is_tie else self.colors['text']

        tk.Label(board_frame, text=title_text, font=("Segoe UI", 42, "bold"), bg=self.colors['bg'], fg=title_color).pack(pady=40)
        
        for i, player in enumerate(leaderboard):
            if is_tie:
                color = self.colors['gold']
                medal = "👑"
                place = 1
            else:
                if i == 0:
                    color = self.colors['gold']
                    medal = "👑"
                    place = 1
                else:
                    color = self.colors['silver']
                    medal = "🥈"
                    place = 2
                
            text = f"{place}. {medal} {player['username']}  -  {player['score']} bal"
            tk.Label(board_frame, text=text, font=("Segoe UI", 30, "bold"), bg=self.colors['bg'], fg=color).pack(pady=15)
            
        btn = tk.Button(board_frame, text="Oyundan Çıx", command=self.on_closing, font=("Segoe UI", 16, "bold"), bg=self.colors['btn_bg'], fg="white", relief=tk.FLAT, padx=20)
        btn.pack(pady=50)

    # --- MƏNTİQ ---

    def load_csv_and_send(self):
        filepath = filedialog.askopenfilename(filetypes=[("CSV Files", "*.csv")])
        if not filepath: return
        try:
            with open(filepath, 'r', encoding='utf-8-sig') as f:
                reader = csv.reader(f)
                next(reader, None)
                words_list = [row[:2] for row in reader if len(row) >= 2]
            if len(words_list) < 4:
                messagebox.showerror("Xəta", "Faylda ən azı 4 söz olmalıdır.")
                return
            
            # SÖZLƏRİ GÖNDƏR VƏ DÜYMƏNİ YOXA ÇIXART
            self.sio.emit('upload_words', {'words': words_list})
            self.load_btn.pack_forget() # Düyməni gizlədir
            
        except Exception as e:
            messagebox.showerror("Xəta", f"Xəta: {e}")

    def start_connection(self):
        self.username = self.username_entry.get().strip()
        if not self.username:
            messagebox.showwarning("Xəta", "Zəhmət olmasa adınızı daxil edin!")
            return
        self.setup_game_ui()
        threading.Thread(target=self.connect_to_server, daemon=True).start()

    def connect_to_server(self):
        try:
            if not self.sio.connected:
                self.sio.connect(SERVER_URL)
            else:
                self.sio.emit('join_game', {'username': self.username})
        except Exception as e:
            self.update_status(f"Qoşulma xətası: {e}", self.colors['wrong'])

    def setup_sockets(self):
        @self.sio.on('connect')
        def on_connect():
            self.sio.emit('join_game', {'username': self.username})

        @self.sio.on('system_message')
        def on_message(data):
            self.update_status(data, self.colors['wait'])

        @self.sio.on('new_question')
        def on_question(data):
            self.current_word = data['word']
            self.options = data['options']
            self.has_answered = False
            self.interaction_allowed = True
            self.selected_answer = None
            
            # Sual gələn kimi yükləmə düyməsini bir daha gizlədiyimizdən əmin oluruq
            if hasattr(self, 'load_btn'):
                self.load_btn.pack_forget()

            self.root.after(0, lambda: self._update_ui_for_new_question(data))

        @self.sio.on('player_answered')
        def on_player_answered(data):
            count = data['count']
            if count == 1:
                if not self.has_answered:
                    self.update_status("Dostunuz cavab verdi! Sizin seçiminiz gözlənilir...", self.colors['wait'])
            elif count == 2:
                if self.has_answered:
                    self.update_status("Hər kəs cavab verdi! Nəticələr gəlir...", self.colors['wait'])

        @self.sio.on('show_result')
        def on_result(data):
            self.interaction_allowed = False
            self.root.after(0, lambda: self._update_ui_for_result(data))

        @self.sio.on('player_ready')
        def on_ready():
            self.update_status("Dostunuz növbəti suala keçmək istəyir...", self.colors['wait'])
            
        @self.sio.on('game_over')
        def on_game_over(data):
            leaderboard = data['leaderboard']
            self.root.after(0, lambda: self.show_leaderboard(leaderboard))

    def _update_ui_for_new_question(self, data):
        self.word_label.config(text=self.current_word, fg=self.colors['text'])
        self.progress_label.config(text=f"{data['current']} / {data['total']}")
        self.next_btn.config(state=tk.DISABLED, bg=self.colors['btn_bg'], fg="#888888")
        self.update_status("Sual gəldi! Seçiminizi edin.", self.colors['text'])
        for i, btn in enumerate(self.option_buttons):
            btn.config(text=self.options[i], bg=self.colors['btn_bg'], fg=self.colors['text'])
        self.speak_word()

    def _update_ui_for_result(self, data):
        correct_ans = data['correct_answer']
        result_msg = data['result_msg']
        self.update_status(result_msg, self.colors['accent'])
        for btn in self.option_buttons:
            if btn.cget('text') == correct_ans:
                btn.config(bg=self.colors['accent'])
            elif btn.cget('text') == self.selected_answer and self.selected_answer != correct_ans:
                btn.config(bg=self.colors['wrong'])
        self.next_btn.config(state=tk.NORMAL, bg=self.colors['accent'], fg="white")

    def update_status(self, text, color):
        if hasattr(self, 'status_label') and self.status_label.winfo_exists():
            self.status_label.config(text=text, fg=color)

    def select_option(self, idx, btn):
        if not self.interaction_allowed: return
        self.interaction_allowed = False
        self.has_answered = True
        self.selected_answer = self.options[idx]
        btn.config(bg=self.colors['selected'])
        self.update_status("Seçiminiz qeydə alındı. Gözləyin...", self.colors['wait'])
        self.sio.emit('submit_answer', {"answer": self.selected_answer})

    def request_next(self):
        self.next_btn.config(state=tk.DISABLED, bg=self.colors['btn_bg'], fg="#888888")
        self.update_status("Növbəti sual gözlənilir...", self.colors['wait'])
        self.sio.emit('request_next')

    def speak_word(self):
        if not self.current_word: return
        clean_word = re.sub(r'\(.*?\)', '', self.current_word).strip()
        self.tts.speak(clean_word)

if __name__ == "__main__":
    root = tk.Tk()
    app = MultiplayerFlashcardApp(root)
    root.mainloop()