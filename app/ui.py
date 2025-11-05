from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QFrame,
    QLineEdit,
    QListWidget,
    QSplitter,
    QSizePolicy,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont


class App(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("디미 노래방")
        self.resize(1280, 800)

        cw = QWidget()
        root = QVBoxLayout(cw)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        appbar = QWidget()
        appbar.setObjectName("AppBar")
        appbar.setStyleSheet(
            "#AppBar{background:qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #2d2f55, stop:1 #1d203b);}"
        )
        hb = QHBoxLayout(appbar)
        hb.setContentsMargins(16, 10, 16, 10)
        hb.setSpacing(10)

        # Left: logo mark
        self.logo = QLabel("@")
        self.logo.setStyleSheet(
            "color:#ff5ac8; font-weight:800; font-size:20px; background: transparent;"
        )

        self.search = QLineEdit()
        self.search.setPlaceholderText("검색")
        self.search.setFixedWidth(260)
        self.search.setClearButtonEnabled(True)

        # self.btn_search = QPushButton("🔍")
        # self.btn_search.setFixedSize(32, 32)
        # self.btn_search.setProperty("variant", "ghost")

        self.btn_add = QPushButton("+")
        self.btn_add.setFixedSize(32, 32)
        self.btn_add.setProperty("variant", "accent")

        spacer = QWidget()
        spacer.setObjectName("AppBarSpacer")
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        spacer.setStyleSheet("background: transparent; border: 0;")

        self.btn_profile = QPushButton()
        self.btn_profile.setFixedSize(28, 28)
        self.btn_profile.setStyleSheet(
            "border-radius:14px; background:#c9cbd3; border:0;"
        )

        hb.addWidget(self.logo)
        hb.addSpacing(8)
        hb.addWidget(self.search)
        # hb.addWidget(self.btn_search)
        hb.addWidget(self.btn_add)
        hb.addWidget(spacer)
        hb.addWidget(self.btn_profile)

        content = QSplitter()
        content.setChildrenCollapsible(False)
        content.setHandleWidth(1)

        left = QWidget()
        left.setObjectName("LeftPanel")
        lv = QVBoxLayout(left)
        lv.setContentsMargins(0, 0, 0, 0)
        lv.setSpacing(0)

        left_head = QWidget()
        lh = QHBoxLayout(left_head)
        lh.setContentsMargins(16, 12, 16, 12)
        lh.setSpacing(8)
        title = QLabel("노래 목록")
        title.setStyleSheet("font-size:18px; font-weight:700;")
        lh.addWidget(title)

        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)

        self.list_songs = QListWidget()
        self.list_songs.setMinimumWidth(280)
        self.list_songs.setAlternatingRowColors(True)

        lv.addWidget(left_head)
        lv.addWidget(line)
        lv.addWidget(self.list_songs, 1)

        center = QWidget()
        cv = QVBoxLayout(center)
        cv.setContentsMargins(0, 0, 0, 0)
        cv.setSpacing(0)
        self.lyrics = QLabel("가사")
        self.lyrics.setAlignment(Qt.AlignCenter)
        self.lyrics.setStyleSheet("font-size:22px; font-weight:700;")
        cv.addWidget(self.lyrics, 1)

        content.addWidget(left)
        content.addWidget(center)
        content.setStretchFactor(0, 0)
        content.setStretchFactor(1, 1)

        root.addWidget(appbar)
        root.addWidget(content, 1)
        self.setCentralWidget(cw)

        self.btn_search.clicked.connect(self._do_search)
        self.btn_add.clicked.connect(self._add_current_to_list)

    def _do_search(self):
        q = self.search.text().strip()
        if q:
            self.lyrics.setText(f"검색: {q}")

    def _add_current_to_list(self):
        q = self.search.text().strip()
        if q:
            self.list_songs.addItem(q)
