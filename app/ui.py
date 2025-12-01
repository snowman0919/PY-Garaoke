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

class NicknameDialog(QDialog):
    nickname_set = Signal(str)

    def __init__(self, current_nickname=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("닉네임 설정")
        self.setFixedSize(300, 150)
        layout = QVBoxLayout(self)
        self.label = QLabel("닉네임을 입력해 주세요:")
        self.nickname_input = QLineEdit()
        if current_nickname:
            self.nickname_input.setText(current_nickname)
        self.nickname_input.setPlaceholderText("닉네임 입력")
        self.ok_button = QPushButton("확인")
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
            QMessageBox.warning(self, "입력 오류", "닉네임은 비워둘 수 없습니다.")

class AddSongDialog(QDialog):
    song_add_requested = Signal(str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("YouTube에서 노래 추가")
        self.setFixedSize(500, 200)
        layout = QVBoxLayout(self)
        self.url_label = QLabel("YouTube URL 또는 검색어:")
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("YouTube URL을 붙여넣거나 노래 제목 + 가수 입력")
        self.add_button = QPushButton("노래 추가")
        self.add_button.clicked.connect(self._add_song)
        layout.addWidget(self.url_label)
        layout.addWidget(self.url_input)
        layout.addWidget(self.add_button)
        self.setLayout(layout)

    def _add_song(self):
        input_text = self.url_input.text().strip()
        if not input_text:
            QMessageBox.warning(self, "입력 오류", "YouTube URL 또는 검색어를 입력해 주세요.")
            return
        if "youtube.com/watch" in input_text or "youtu.be/" in input_text:
            url_or_query = input_text
            song_title = ""
        else:
            url_or_query = input_text
            song_title = input_text
        self.song_add_requested.emit(url_or_query, song_title)
        self.accept()

class SongListWidget(QWidget):
    start_singing_requested = Signal(str)
    add_song_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        self.add_song_button = QPushButton("YouTube에서 노래 추가")
        self.add_song_button.clicked.connect(self.add_song_requested.emit)
        self.layout.addWidget(self.add_song_button)
        self.song_table = QTableWidget()
        self.song_table.setColumnCount(4)
        self.song_table.setHorizontalHeaderLabels(["제목", "가수", "길이", "액션"])
        self.song_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.song_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.song_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.layout.addWidget(self.song_table)
        self.setLayout(self.layout)

    def update_song_list(self, songs):
        self.song_table.setRowCount(len(songs))
        for i, song in enumerate(songs):
            self.song_table.setItem(i, 0, QTableWidgetItem(song.get("title", "알 수 없는 제목")))
            self.song_table.setItem(i, 1, QTableWidgetItem(song.get("artist", "알 수 없는 가수")))
            duration_sec = song.get("duration", 0)
            mins = int(duration_sec // 60)
            secs = int(duration_sec % 60)
            self.song_table.setItem(i, 2, QTableWidgetItem(f"{mins:02}:{secs:02}"))
            sing_button = QPushButton("부르기")
            sing_button.setProperty("song_id", song.get("id"))
            sing_button.clicked.connect(lambda checked=False, s_id=song.get("id"): self.start_singing_requested.emit(s_id))
            self.song_table.setCellWidget(i, 3, sing_button)

class SingingWidget(QWidget):
    stop_singing_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("SingingWidget")
        self.layout = QVBoxLayout(self)
        self.setContentsMargins(20, 20, 20, 20)
        self.score_bar_layout = QHBoxLayout()
        self.current_score_label = QLabel("점수: 0")
        self.current_score_label.setObjectName("ScoreLabel")
        self.current_score_label.setAlignment(Qt.AlignCenter)
        self.current_score_label.setFont(QFont("Arial", 24))
        self.score_bar_layout.addWidget(self.current_score_label)
        self.layout.addLayout(self.score_bar_layout)
        self.pitch_lane = PitchVisualizationWidget()
        self.layout.addWidget(self.pitch_lane)
        self.lyrics_label = QLabel("노래할 준비 완료...")
        self.lyrics_label.setObjectName("LyricsLabel")
        self.lyrics_label.setAlignment(Qt.AlignCenter)
        self.lyrics_label.setFont(QFont("Arial", 28, QFont.Bold))
        self.lyrics_label.setWordWrap(True)
        self.layout.addWidget(self.lyrics_label)
        self.progress_layout = QHBoxLayout()
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 1000)
        self.progress_bar.setTextVisible(False)
        self.progress_layout.addWidget(self.progress_bar)
        self.stop_button = QPushButton("노래 중지")
        self.stop_button.setCursor(Qt.PointingHandCursor)
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
        if lyric_text:
            self.lyrics_label.setText(lyric_text)
        else:
            pass

    def update_score(self, current_score):
        self.current_score_label.setText(f"점수: {current_score:.0f}")

class PitchVisualizationWidget(QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(200)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setAttribute(Qt.WA_OpaquePaintEvent)
        self.setAttribute(Qt.WA_NoSystemBackground)
        self.reference_pitch_contour = []
        self.user_pitch_points = []
        self.total_duration = 1.0
        self.playback_cursor_time = 0.0
        self.smoothed_pitch = 0.0
        self.sr = 22050
        self.hop_length = 512
        self.frame_duration = self.hop_length / self.sr
        self.visible_window = 10.0
        self.pitch_min = 65.41
        self.pitch_max = 1046.50
        self.pitch_range_log = np.log2(self.pitch_max) - np.log2(self.pitch_min)
        self.setMouseTracking(True)

    def set_reference_pitch(self, pitch_contour, duration, sr=22050, hop_length=512):
        self.reference_pitch_contour = pitch_contour
        self.total_duration = duration
        self.sr = sr
        self.hop_length = hop_length
        self.frame_duration = self.hop_length / self.sr
        self.user_pitch_points = []
        self.smoothed_pitch = 0.0
        self.update()

    def update_user_pitch(self, pitch_hz):
        alpha = 0.25
        if pitch_hz > 0:
            if self.smoothed_pitch <= 0:
                self.smoothed_pitch = pitch_hz
            else:
                semitone_diff = abs(12 * np.log2(pitch_hz / self.smoothed_pitch))
                if semitone_diff > 3.0:
                     self.smoothed_pitch = pitch_hz
                else:
                     if abs(pitch_hz - self.smoothed_pitch) < 1.5:
                         pass
                     else:
                         self.smoothed_pitch = (self.smoothed_pitch * (1 - alpha)) + (pitch_hz * alpha)
        else:
            self.smoothed_pitch = 0.0
        
        if self.smoothed_pitch > 0:
            latency_compensation = 0.04 
            corrected_time = max(0, self.playback_cursor_time - latency_compensation)
            self.user_pitch_points.append((corrected_time, self.smoothed_pitch))
            
            min_time = self.playback_cursor_time - self.visible_window
            while self.user_pitch_points and self.user_pitch_points[0][0] < min_time:
                self.user_pitch_points.pop(0)
        self.update()

    def update_playback_cursor(self, current_time_sec):
        self.playback_cursor_time = current_time_sec
        self.update()

    def _pitch_to_y(self, pitch_hz, height):
        if pitch_hz <= 0:
            return -1
        try:
            log_pitch = np.log2(pitch_hz)
        except:
            return -1
        log_pitch_min = np.log2(self.pitch_min)
        log_pitch_max = np.log2(self.pitch_max)
        normalized_pitch = (log_pitch - log_pitch_min) / (log_pitch_max - log_pitch_min)
        normalized_pitch = max(0.0, min(1.0, normalized_pitch))
        return height * (1 - normalized_pitch)

    def _time_to_x(self, time_sec, width, start_time):
        rel_time = time_sec - start_time
        return int((rel_time / self.visible_window) * width)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.fillRect(self.rect(), QColor(30, 30, 40))
        width = self.width()
        height = self.height()
        start_time = max(0, self.playback_cursor_time - (self.visible_window * 0.3))
        end_time = start_time + self.visible_window
        if self.reference_pitch_contour:
            painter.setPen(QColor(100, 150, 255, 180))
            painter.setBrush(QBrush(QColor(100, 150, 255, 180)))
            start_frame = int(start_time / self.frame_duration)
            end_frame = int(end_time / self.frame_duration) + 1
            start_frame = max(0, start_frame)
            end_frame = min(len(self.reference_pitch_contour), end_frame)
            prev_x, prev_y = -1, -1
            for i in range(start_frame, end_frame):
                pitch_hz = self.reference_pitch_contour[i]
                if pitch_hz > 0:
                    time_sec = i * self.frame_duration
                    x = self._time_to_x(time_sec, width, start_time)
                    y = self._pitch_to_y(pitch_hz, height)
                    if prev_x != -1 and (time_sec - ((i-1) * self.frame_duration)) < (self.frame_duration * 1.5):
                        painter.drawLine(prev_x, prev_y, x, y)
                    else:
                        painter.drawEllipse(x-1, y-1, 2, 2)
                    prev_x, prev_y = x, y
                else:
                    prev_x, prev_y = -1, -1
        if self.user_pitch_points:
            painter.setPen(QColor(255, 200, 50))
            prev_x, prev_y = -1, -1
            for time_sec, pitch_hz in self.user_pitch_points:
                if time_sec < start_time or time_sec > end_time:
                    continue
                x = self._time_to_x(time_sec, width, start_time)
                y = self._pitch_to_y(pitch_hz, height)
                if prev_x != -1:
                    painter.drawLine(prev_x, prev_y, x, y)
                else:
                     painter.drawEllipse(x-2, y-2, 4, 4)
                prev_x, prev_y = x, y
        cursor_x = self._time_to_x(self.playback_cursor_time, width, start_time)
        if 0 <= cursor_x <= width:
            painter.setPen(QColor(255, 50, 50, 200))
            painter.drawLine(cursor_x, 0, cursor_x, height)

class ResultsWidget(QWidget):
    back_to_home_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("ResultsWidget")
        self.layout = QVBoxLayout(self)
        self.setContentsMargins(20, 20, 20, 20)
        self.title_label = QLabel("노래 결과")
        self.title_label.setAlignment(Qt.AlignCenter)
        self.title_label.setFont(QFont("Arial", 36))
        self.layout.addWidget(self.title_label)
        self.score_label = QLabel("최종 점수: --/100")
        self.score_label.setAlignment(Qt.AlignCenter)
        self.score_label.setFont(QFont("Arial", 48, QFont.Bold))
        self.layout.addWidget(self.score_label)
        self.subscores_layout = QHBoxLayout()
        self.pitch_label = QLabel("음정: --%")
        self.rhythm_label = QLabel("리듬: --%")
        self.vibrato_label = QLabel("비브라토: --%")
        for label in [self.pitch_label, self.rhythm_label, self.vibrato_label]:
            label.setAlignment(Qt.AlignCenter)
            label.setFont(QFont("Arial", 20))
            self.subscores_layout.addWidget(label)
        self.layout.addLayout(self.subscores_layout)
        self.feedback_label = QLabel("피드백이 여기에 표시됩니다...")
        self.feedback_label.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self.feedback_label.setFont(QFont("Arial", 16))
        self.feedback_label.setWordWrap(True)
        self.layout.addWidget(self.feedback_label)
        self.ranking_table = QTableWidget()
        self.ranking_table.setColumnCount(3)
        self.ranking_table.setHorizontalHeaderLabels(["순위", "닉네임", "점수"])
        self.ranking_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.ranking_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.layout.addWidget(self.ranking_table)
        self.back_button = QPushButton("홈으로 돌아가기")
        self.back_button.clicked.connect(self.back_to_home_requested.emit)
        self.layout.addWidget(self.back_button)
        self.setLayout(self.layout)

    def display_results(self, final_score_data, feedback_messages, local_rankings, global_rankings=None):
        self.score_label.setText(f"최종 점수: {final_score_data['final_score']:.2f}/100")
        self.pitch_label.setText(f"음정: {final_score_data['pitch_accuracy']:.1f}%")
        self.rhythm_label.setText(f"리듬: {final_score_data['rhythm_accuracy']:.1f}%")
        self.vibrato_label.setText(f"비브라토: {final_score_data['vibrato_quality']:.1f}%")
        self.feedback_label.setText("<b>피드백:</b><br>" + "<br>".join(feedback_messages))
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
        self.stacked_widget.addWidget(self.song_list_widget)
        self.stacked_widget.addWidget(self.singing_widget)
        self.stacked_widget.addWidget(self.results_widget)
        self.show_song_list()

    def show_song_list(self):
        self.stacked_widget.setCurrentIndex(0)

    def show_singing_screen(self, song_id):
        self.stacked_widget.setCurrentIndex(1)

    def show_results_screen(self):
        self.stacked_widget.setCurrentIndex(2)

    def set_pitch_scorer_ref(self, scorer):
        self.singing_widget.pitch_lane.scorer = scorer
