import tkinter as tk
from tkinter import filedialog, messagebox
import csv
import random
import re
import json
import os
import ctypes
import threading
from gtts import gTTS
import pygame
import io

# --- WINDOWS ÜÇÜN BLUR (ŞÜŞƏLƏNMƏ) PROBLEMININ HƏLLI ---
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass


# --- YENİ VƏ DONMAYAN TTS MANAGER (Google Translate Səsi) ---
class TTSManager:
    def __init__(self):
        pygame.mixer.init()

    def speak(self, text):
        if not text: 
            return
        
        # Əsas proqramı dondurmasın deyə thread içində çalışır
        def play_sound():
            try:
                # Səsi MP3 kimi memuarda yaradırıq (fayl olaraq saxlamağa ehtiyac yoxdur)
                tts = gTTS(text=text, lang='en')
                fp = io.BytesIO()
                tts.write_to_fp(fp)
                fp.seek(0)
                
                # Pygame ilə oxuduruq
                pygame.mixer.music.load(fp)
                pygame.mixer.music.play()
            except Exception as e:
                print(f"Səs xətası (İnternet bağlantınızı yoxlayın): {e}")

        threading.Thread(target=play_sound, daemon=True).start()

    def stop(self, wait=False):
        pygame.mixer.music.stop()


PROGRESS_FILE = "flashcard_progress.json"

class FlashcardApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Sleek Flashcards")
        self.root.geometry("1000x650")
        self.root.minsize(800, 400)
        
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        # TTS Meneceri (gTTS versiyası)
        self.tts = TTSManager()

        # Dəyişənlər
        self.cards = []
        self.current_card = None
        self.current_index = 0
        self.is_front = True
        self.is_dark_mode = True
        self.font_size = 48
        self.current_csv_path = ""

        # Rənglər
        self.colors = {
            'bg': '#1E1E1E',
            'card_bg': '#2D2D2D',
            'text': '#FFFFFF',
            'btn_bg': '#3D3D3D',
            'btn_fg': '#FFFFFF',
            'accent': '#4CAF50',
            'progress': '#888888'
        }

        self.setup_ui()
        self.apply_theme()
        
        if not self.load_progress():
            self.word_label.config(text="Load a CSV file to start")

    def setup_ui(self):
        # Top Menu Bar
        menu_frame = tk.Frame(self.root, bg=self.colors['bg'])
        menu_frame.pack(fill=tk.X, pady=10, padx=20)

        self.load_btn = tk.Button(menu_frame, text="📁 Load CSV", command=self.load_csv, relief=tk.FLAT, font=("Segoe UI", 10))
        self.load_btn.pack(side=tk.LEFT, padx=5)

        self.theme_btn = tk.Button(menu_frame, text="🌓 Theme", command=self.toggle_theme, relief=tk.FLAT, font=("Segoe UI", 10))
        self.theme_btn.pack(side=tk.LEFT, padx=5)

        self.zoom_in_btn = tk.Button(menu_frame, text="➕ Zoom", command=lambda: self.change_font(4), relief=tk.FLAT, font=("Segoe UI", 10))
        self.zoom_in_btn.pack(side=tk.RIGHT, padx=5)

        self.zoom_out_btn = tk.Button(menu_frame, text="➖ Zoom", command=lambda: self.change_font(-4), relief=tk.FLAT, font=("Segoe UI", 10))
        self.zoom_out_btn.pack(side=tk.RIGHT, padx=5)

        self.speak_btn = tk.Button(menu_frame, text="🔊 Speak", command=self.speak_word, relief=tk.FLAT, font=("Segoe UI", 10))
        self.speak_btn.pack(side=tk.RIGHT, padx=5)

        # Main Card Area
        self.card_frame = tk.Frame(self.root, bg=self.colors['card_bg'], bd=0, highlightthickness=1, highlightbackground="#444444")
        self.card_frame.pack(expand=True, fill=tk.BOTH, padx=20, pady=20)
        self.card_frame.bind("<Button-1>", self.flip_card)

        # wraplength=2500 edilib ki, ekran çox kiçik olmadığı müddətcə yeni sətrə keçməsin
        self.word_label = tk.Label(self.card_frame, text="", font=("Segoe UI", self.font_size, "bold"), wraplength=2500)
        self.word_label.pack(expand=True, fill=tk.BOTH)
        self.word_label.bind("<Button-1>", self.flip_card)

        # Progress Label
        self.progress_label = tk.Label(self.card_frame, text="", font=("Segoe UI", 12), fg=self.colors['progress'])
        self.progress_label.pack(side=tk.BOTTOM, pady=15)
        self.progress_label.bind("<Button-1>", self.flip_card)

        # Bottom Controls
        control_frame = tk.Frame(self.root, bg=self.colors['bg'])
        control_frame.pack(fill=tk.X, pady=20, padx=20)

        self.prev_btn = tk.Button(control_frame, text="◄ Previous", command=self.prev_card, width=15, font=("Segoe UI", 12), relief=tk.FLAT)
        self.prev_btn.pack(side=tk.LEFT, expand=True)

        self.flip_btn = tk.Button(control_frame, text="↻ Reveal", command=self.flip_card, width=20, font=("Segoe UI", 12, "bold"), bg=self.colors['accent'], fg="white", relief=tk.FLAT)
        self.flip_btn.pack(side=tk.LEFT, expand=True)

        self.next_btn = tk.Button(control_frame, text="Next ►", command=self.next_card, width=15, font=("Segoe UI", 12), relief=tk.FLAT)
        self.next_btn.pack(side=tk.LEFT, expand=True)

        # Key Bindings
        self.root.bind('<Right>', lambda e: self.next_card())
        self.root.bind('<Left>', lambda e: self.prev_card())
        self.root.bind('<space>', lambda e: self.flip_card())
        self.root.bind('s', lambda e: self.speak_word())

    def load_csv(self):
        filepath = filedialog.askopenfilename(filetypes=[("CSV Files", "*.csv")])
        if not filepath: return

        try:
            with open(filepath, 'r', encoding='utf-8-sig') as f:
                reader = csv.reader(f)
                header = next(reader) 
                self.cards = [row[:2] for row in reader if len(row) >= 2]
            
            if not self.cards:
                messagebox.showerror("Error", "Geçərli kart tapılmadı.")
                return
            
            self.current_csv_path = filepath
            random.shuffle(self.cards) 
            self.current_index = 0
            self.show_card()
            self.save_progress() 
            
        except Exception as e:
            messagebox.showerror("Error", f"Fayl oxunarkən xəta baş verdi:\n{e}")

    def save_progress(self):
        if not self.cards: return
        data = {
            "csv_path": self.current_csv_path,
            "index": self.current_index,
            "cards": self.cards
        }
        with open(PROGRESS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f)

    def load_progress(self):
        if os.path.exists(PROGRESS_FILE):
            try:
                with open(PROGRESS_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.current_csv_path = data.get("csv_path", "")
                    self.cards = data.get("cards", [])
                    self.current_index = data.get("index", 0)
                    if self.cards:
                        self.show_card()
                        return True
            except Exception:
                pass
        return False

    def on_closing(self):
        self.save_progress()
        self.tts.stop() 
        self.root.destroy()

    def show_card(self):
        if not self.cards: return
        self.current_card = self.cards[self.current_index]
        self.is_front = True
        
        self.word_label.config(text=self.current_card[0], fg=self.colors['text'])
        self.update_progress_label()

    def update_progress_label(self):
        if self.cards:
            self.progress_label.config(text=f"{self.current_index + 1} / {len(self.cards)}")

    def flip_card(self, event=None):
        if not self.cards: return
        self.is_front = not self.is_front
        
        if self.is_front:
            self.word_label.config(text=self.current_card[0], fg=self.colors['text'])
        else:
            self.word_label.config(text=self.current_card[1], fg=self.colors['accent'])

    def next_card(self):
        if not self.cards: return
        self.current_index = (self.current_index + 1) % len(self.cards)
        self.show_card()
        self.save_progress()

    def prev_card(self):
        if not self.cards: return
        self.current_index = (self.current_index - 1) % len(self.cards)
        self.show_card()
        self.save_progress()

    def speak_word(self):
        if not self.cards: return
        word = self.current_card[0]
        # Regex ilə mötərizə içlərini təmizləyir ki, oxumasın
        clean_word = re.sub(r'\(.*?\)', '', word).strip()
        self.tts.speak(clean_word)

    def change_font(self, amount):
        self.font_size = max(20, min(150, self.font_size + amount))
        self.word_label.config(font=("Segoe UI", self.font_size, "bold"))

    def toggle_theme(self):
        self.is_dark_mode = not self.is_dark_mode
        if self.is_dark_mode:
            self.colors = {'bg': '#1E1E1E', 'card_bg': '#2D2D2D', 'text': '#FFFFFF', 'btn_bg': '#3D3D3D', 'btn_fg': '#FFFFFF', 'accent': '#4CAF50', 'progress': '#888888'}
        else:
            self.colors = {'bg': '#F0F0F0', 'card_bg': '#FFFFFF', 'text': '#333333', 'btn_bg': '#E0E0E0', 'btn_fg': '#333333', 'accent': '#0078D7', 'progress': '#888888'}
        self.apply_theme()

    def apply_theme(self):
        self.root.configure(bg=self.colors['bg'])
        self.card_frame.configure(bg=self.colors['card_bg'], highlightbackground=self.colors['btn_bg'])
        self.word_label.configure(bg=self.colors['card_bg'], fg=self.colors['text'] if self.is_front else self.colors['accent'])
        self.progress_label.configure(bg=self.colors['card_bg'], fg=self.colors['progress'])
        
        for frame in self.root.winfo_children():
            if isinstance(frame, tk.Frame) and frame != self.card_frame:
                frame.configure(bg=self.colors['bg'])
                for btn in frame.winfo_children():
                    if isinstance(btn, tk.Button) and btn != self.flip_btn:
                        btn.configure(bg=self.colors['btn_bg'], fg=self.colors['btn_fg'], activebackground=self.colors['accent'])

if __name__ == "__main__":
    root = tk.Tk()
    app = FlashcardApp(root)
    root.mainloop()