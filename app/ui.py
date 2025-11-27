from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLineEdit, QLabel, QStackedWidget, QDialog,
    QMessageBox, QListWidget, QListWidgetItem, QTableWidget,
    QTableWidgetItem, QHeaderView, QSizePolicy, QSlider, QSpinBox,
    QProgressBar
)
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QPainter, QBrush, QColor, QFontMetrics, QFont
import numpy as np
import librosa

class NicknameDialog(QDialog):
    nickname_set = Signal(str)

    def __init__(self, current_nickname=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Set Your Nickname")
        self.setFixedSize(300, 150)

        layout = QVBoxLayout(self)

        self.label = QLabel("Please enter your nickname:")
        self.nickname_input = QLineEdit()
        if current_nickname:
            self.nickname_input.setText(current_nickname)
        self.nickname_input.setPlaceholderText("Enter nickname")

        self.ok_button = QPushButton("OK")
        self.ok_button.clicked.connect(self._accept_nickname)

        layout.addWidget(self.label)
        layout.addWidget(self.nickname_input)
        layout.addWidget(self.ok_button)

        self.setLayout(layout)

    def _accept_nickname(self):
        nickname = self.nickname_input.text().strip()
        if nickname:
            self.nickname_set.emit(nickname)
            self.accept()
        else:
            QMessageBox.warning(self, "Input Error", "Nickname cannot be empty.")

class AddSongDialog(QDialog):
    song_add_requested = Signal(str, str) # url_or_query, song_title

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add Song from YouTube")
        self.setFixedSize(500, 200)

        layout = QVBoxLayout(self)

        self.url_label = QLabel("YouTube URL or Search Query:")
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("Paste YouTube URL or type song title + artist")

        self.add_button = QPushButton("Add Song")
        self.add_button.clicked.connect(self._add_song)

        layout.addWidget(self.url_label)
        layout.addWidget(self.url_input)
        layout.addWidget(self.add_button)

        self.setLayout(layout)

    def _add_song(self):
        input_text = self.url_input.text().strip()
        if not input_text:
            QMessageBox.warning(self, "Input Error", "Please enter a YouTube URL or search query.")
            return

        # Simple heuristic to guess if it's a URL
        if "youtube.com/watch" in input_text or "youtu.be/" in input_text:
            url_or_query = input_text
            song_title = "" # Title will be fetched later
        else:
            url_or_query = input_text
            song_title = input_text # Use query as title placeholder

        self.song_add_requested.emit(url_or_query, song_title)
        self.accept()

class SongListWidget(QWidget):
    start_singing_requested = Signal(str) # Emits song_id
    add_song_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)

        self.add_song_button = QPushButton("Add Song from YouTube")
        self.add_song_button.clicked.connect(self.add_song_requested.emit)
        self.layout.addWidget(self.add_song_button)

        self.song_table = QTableWidget()
        self.song_table.setColumnCount(4)
        self.song_table.setHorizontalHeaderLabels(["Title", "Artist", "Duration", "Action"])
        self.song_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.song_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.song_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.layout.addWidget(self.song_table)

        self.setLayout(self.layout)

    def update_song_list(self, songs):
        self.song_table.setRowCount(len(songs))
        for i, song in enumerate(songs):
            self.song_table.setItem(i, 0, QTableWidgetItem(song.get("title", "Unknown Title")))
            self.song_table.setItem(i, 1, QTableWidgetItem(song.get("artist", "Unknown Artist")))
            
            duration_sec = song.get("duration", 0)
            mins = int(duration_sec // 60)
            secs = int(duration_sec % 60)
            self.song_table.setItem(i, 2, QTableWidgetItem(f"{mins:02}:{secs:02}"))

            sing_button = QPushButton("Sing")
            sing_button.setProperty("song_id", song.get("id"))
            sing_button.clicked.connect(lambda checked, s_id=song.get("id"): self.start_singing_requested.emit(s_id))
            self.song_table.setCellWidget(i, 3, sing_button)

class SingingWidget(QWidget):
    stop_singing_requested = Signal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        self.setContentsMargins(0, 0, 0, 0)

        # Top bar for real-time score
        self.score_bar_layout = QHBoxLayout()
        self.current_score_label = QLabel("Score: 0")
        self.current_score_label.setAlignment(Qt.AlignCenter)
        self.current_score_label.setFont(QFont("Arial", 24))
        self.score_bar_layout.addWidget(self.current_score_label)
        self.layout.addLayout(self.score_bar_layout)

        # Pitch lane area
        self.pitch_lane = PitchVisualizationWidget()
        self.layout.addWidget(self.pitch_lane)

        # Lyrics display
        self.lyrics_label = QLabel("Ready to sing...")
        self.lyrics_label.setAlignment(Qt.AlignCenter)
        self.lyrics_label.setFont(QFont("Arial", 18))
        self.layout.addWidget(self.lyrics_label)

        # Progress bar and controls
        self.progress_layout = QHBoxLayout()
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 1000)
        self.progress_bar.setTextVisible(True)
        self.progress_layout.addWidget(self.progress_bar)

        self.stop_button = QPushButton("Stop Singing")
        self.stop_button.clicked.connect(self.stop_singing_requested.emit)
        self.progress_layout.addWidget(self.stop_button)
        self.layout.addLayout(self.progress_layout)

        self.setLayout(self.layout)

    def set_reference_pitch_contour(self, pitch_contour, duration):
        self.pitch_lane.set_reference_pitch(pitch_contour, duration)

    def update_realtime_pitch(self, pitch_hz):
        self.pitch_lane.update_user_pitch(pitch_hz)

    def update_playback_position(self, current_time_sec):
        progress = int((current_time_sec / self.pitch_lane.total_duration) * 1000) if self.pitch_lane.total_duration > 0 else 0
        self.progress_bar.setValue(progress)
        self.pitch_lane.update_playback_cursor(current_time_sec)

    def update_lyrics(self, lyric_text):
        self.lyrics_label.setText(lyric_text)

    def update_score(self, current_score):
        self.current_score_label.setText(f"Score: {current_score:.0f}")

class PitchVisualizationWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(200)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self.reference_pitch_contour = []
        self.user_pitch_points = [] # list of (time, pitch_hz)
        self.total_duration = 1.0 # default to 1 sec to avoid div by zero
        self.playback_cursor_time = 0.0

        self.pitch_min = librosa.note_to_hz('C2')
        self.pitch_max = librosa.note_to_hz('C7')
        self.pitch_range_log = np.log2(self.pitch_max) - np.log2(self.pitch_min)

        self.setMouseTracking(True) # For potential future interaction

    def set_reference_pitch(self, pitch_contour, duration):
        self.reference_pitch_contour = pitch_contour
        self.total_duration = duration
        self.user_pitch_points = []
        self.update()

    def update_user_pitch(self, pitch_hz):
        if pitch_hz > 0: # Only add if a valid pitch is detected
            self.user_pitch_points.append((self.playback_cursor_time, pitch_hz))
            # Keep a limited history for performance
            if len(self.user_pitch_points) > 500: # ~10 seconds at 50 updates/sec
                self.user_pitch_points.pop(0)
        self.update()

    def update_playback_cursor(self, current_time_sec):
        self.playback_cursor_time = current_time_sec
        self.update() # Trigger repaint

    def _pitch_to_y(self, pitch_hz, height):
        if pitch_hz <= 0:
            return -1 # Out of bounds / unvoiced
        
        # Logarithmic scale for pitch
        log_pitch = np.log2(pitch_hz)
        log_pitch_min = np.log2(self.pitch_min)
        log_pitch_max = np.log2(self.pitch_max)
        
        # Normalize to 0-1 range
        normalized_pitch = (log_pitch - log_pitch_min) / (log_pitch_max - log_pitch_min)
        
        # Invert y-axis for GUI (higher pitch = lower y value)
        return height * (1 - normalized_pitch)

    def _time_to_x(self, time_sec, width):
        return int((time_sec / self.total_duration) * width)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        width = self.width()
        height = self.height()

        # Draw background (handled by QSS)

        # Draw reference pitch contour (target melody)
        if self.reference_pitch_contour and self.total_duration > 0:
            painter.setPen(QColor(0, 150, 255, 150)) # Light blue/cyan for reference
            prev_x, prev_y = -1, -1
            
            # Assuming reference_pitch_contour is already in Hz
            # Convert frame index to time, then time to x
            # Assuming uniform sampling for reference_pitch_contour (e.g., from librosa.pyin)
            # The contour has a hop_length, so each point corresponds to a time.
            
            # Simplified: just iterate through points and draw lines
            for i, pitch_hz in enumerate(self.reference_pitch_contour):
                if pitch_hz > 0:
                    time_sec = (i * self.scorer.hop_length / self.scorer.sr) # Needs actual scorer reference
                    # This implies SingingWidget should pass the scorer's sr/hop_length to PitchVisualizationWidget
                    # For now, will use placeholder hop/sr (needs to be aligned with actual librosa analysis)
                    time_sec = (i * self.scorer.hop_length / self.scorer.sr)

                    x = self._time_to_x(time_sec, width)
                    y = self._pitch_to_y(pitch_hz, height)
                    
                    if prev_x != -1:
                        painter.drawLine(prev_x, prev_y, x, y)
                    prev_x, prev_y = x, y

        # Draw user's real-time pitch
        if self.user_pitch_points:
            painter.setPen(QColor(255, 255, 0)) # Yellow for user pitch
            for time_sec, pitch_hz in self.user_pitch_points:
                x = self._time_to_x(time_sec, width)
                y = self._pitch_to_y(pitch_hz, height)
                if x >= 0 and y >= 0: # Ensure point is visible
                    painter.drawEllipse(x - 2, y - 2, 4, 4) # Draw small dot

        # Draw playback cursor
        cursor_x = self._time_to_x(self.playback_cursor_time, width)
        painter.setPen(QColor(255, 0, 0)) # Red cursor
        painter.drawLine(cursor_x, 0, cursor_x, height)

class ResultsWidget(QWidget):
    back_to_home_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        self.setContentsMargins(20, 20, 20, 20)

        self.title_label = QLabel("Singing Results")
        self.title_label.setAlignment(Qt.AlignCenter)
        self.title_label.setFont(QFont("Arial", 36))
        self.layout.addWidget(self.title_label)

        self.score_label = QLabel("Final Score: --/100")
        self.score_label.setAlignment(Qt.AlignCenter)
        self.score_label.setFont(QFont("Arial", 48, QFont.Bold))
        self.layout.addWidget(self.score_label)

        self.subscores_layout = QHBoxLayout()
        self.pitch_label = QLabel("Pitch: --%")
        self.rhythm_label = QLabel("Rhythm: --%")
        self.vibrato_label = QLabel("Vibrato: --%")
        for label in [self.pitch_label, self.rhythm_label, self.vibrato_label]:
            label.setAlignment(Qt.AlignCenter)
            label.setFont(QFont("Arial", 20))
            self.subscores_layout.addWidget(label)
        self.layout.addLayout(self.subscores_layout)

        self.feedback_label = QLabel("Feedback will appear here...")
        self.feedback_label.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self.feedback_label.setFont(QFont("Arial", 16))
        self.feedback_label.setWordWrap(True)
        self.layout.addWidget(self.feedback_label)

        self.ranking_table = QTableWidget()
        self.ranking_table.setColumnCount(3)
        self.ranking_table.setHorizontalHeaderLabels(["Rank", "Nickname", "Score"])
        self.ranking_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.ranking_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.layout.addWidget(self.ranking_table)

        self.back_button = QPushButton("Back to Home")
        self.back_button.clicked.connect(self.back_to_home_requested.emit)
        self.layout.addWidget(self.back_button)

        self.setLayout(self.layout)

    def display_results(self, final_score_data, feedback_messages, local_rankings, global_rankings=None):
        self.score_label.setText(f"Final Score: {final_score_data['final_score']:.2f}/100")
        self.pitch_label.setText(f"Pitch: {final_score_data['pitch_accuracy']:.1f}%")
        self.rhythm_label.setText(f"Rhythm: {final_score_data['rhythm_accuracy']:.1f}%")
        self.vibrato_label.setText(f"Vibrato: {final_score_data['vibrato_quality']:.1f}%")
        
        self.feedback_label.setText("<b>Feedback:</b><br>" + "<br>".join(feedback_messages))

        # Combine and display rankings
        all_rankings = sorted(local_rankings + (global_rankings if global_rankings else []), key=lambda x: x['score'], reverse=True)
        self.ranking_table.setRowCount(len(all_rankings))
        for i, rank_entry in enumerate(all_rankings):
            self.ranking_table.setItem(i, 0, QTableWidgetItem(str(i + 1)))
            self.ranking_table.setItem(i, 1, QTableWidgetItem(rank_entry['nickname']))
            self.ranking_table.setItem(i, 2, QTableWidgetItem(f"{rank_entry['score']:.2f}"))

class MainWindow(QMainWindow):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("PY-Garaoke")
        self.setGeometry(100, 100, 1200, 800)

        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QVBoxLayout(self.central_widget)

        self.stacked_widget = QStackedWidget()
        self.main_layout.addWidget(self.stacked_widget)

        self.song_list_widget = SongListWidget()
        self.singing_widget = SingingWidget()
        self.results_widget = ResultsWidget()
        self.add_song_dialog = AddSongDialog(self)

        self.stacked_widget.addWidget(self.song_list_widget) # Index 0
        self.stacked_widget.addWidget(self.singing_widget)   # Index 1
        self.stacked_widget.addWidget(self.results_widget)   # Index 2

        self.show_song_list() # Start on song list screen

    def show_song_list(self):
        self.stacked_widget.setCurrentIndex(0)

    def show_singing_screen(self, song_id):
        self.stacked_widget.setCurrentIndex(1)
        # Controller will configure SingingWidget with song data

    def show_results_screen(self):
        self.stacked_widget.setCurrentIndex(2)

    def set_pitch_scorer_ref(self, scorer):
        # This is a bit of a hack, ideally PitchVisualizationWidget doesn't need the whole scorer
        # just the hop_length and sr
        self.singing_widget.pitch_lane.scorer = scorer
