
import sys
import ctypes
from ctypes import wintypes
from io import BytesIO

import requests
import spotipy

from spotipy.oauth2 import SpotifyOAuth

from PyQt6.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton,
    QVBoxLayout, QHBoxLayout, QFrame
)

from PyQt6.QtGui import (
    QPixmap, QPainter, QPainterPath, QRegion
)

from PyQt6.QtCore import Qt, QTimer

from credentials import CLIENT_ID, CLIENT_SECRET, REDIRECT_URI


# =====================================================
# WINDOWS ACRYLIC BLUR
# =====================================================

class ACCENT_POLICY(ctypes.Structure):
    _fields_ = [
        ("AccentState", ctypes.c_int),
        ("AccentFlags", ctypes.c_int),
        ("GradientColor", ctypes.c_uint),
        ("AnimationId", ctypes.c_int)
    ]


class WINDOWCOMPOSITIONATTRIBDATA(ctypes.Structure):
    _fields_ = [
        ("Attribute", ctypes.c_int),
        ("Data", ctypes.c_void_p),
        ("SizeOfData", ctypes.c_size_t)
    ]


def enable_acrylic(hwnd):

    try:
        accent = ACCENT_POLICY()
        accent.AccentState = 4
        accent.AccentFlags = 2
        accent.GradientColor = 0x1A171A23

        data = WINDOWCOMPOSITIONATTRIBDATA()
        data.Attribute = 19
        data.Data = ctypes.cast(
            ctypes.pointer(accent),
            ctypes.c_void_p
        )
        data.SizeOfData = ctypes.sizeof(accent)

        user32 = ctypes.windll.user32

        user32.SetWindowCompositionAttribute.argtypes = [
            wintypes.HWND,
            ctypes.POINTER(WINDOWCOMPOSITIONATTRIBDATA)
        ]

        user32.SetWindowCompositionAttribute.restype = ctypes.c_int

        result = user32.SetWindowCompositionAttribute(
            wintypes.HWND(hwnd),
            ctypes.byref(data)
        )

        try:
            dwmapi = ctypes.windll.dwmapi

            corner = ctypes.c_int(2)

            dwmapi.DwmSetWindowAttribute(
                wintypes.HWND(hwnd),
                33,
                ctypes.byref(corner),
                ctypes.sizeof(corner)
            )

            border = ctypes.c_int(-2)

            dwmapi.DwmSetWindowAttribute(
                wintypes.HWND(hwnd),
                34,
                ctypes.byref(border),
                ctypes.sizeof(border)
            )

        except Exception as error:
            print("DWM setting:", error)

        return bool(result)

    except Exception as error:
        print("Acrylic error:", error)
        return False


# =====================================================
# SPOTIFY AUTHENTICATION
# =====================================================

sp = spotipy.Spotify(
    auth_manager=SpotifyOAuth(
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        redirect_uri=REDIRECT_URI,
        scope="user-read-playback-state,user-modify-playback-state"
    )
)


# =====================================================
# GLASSMORPHISM THEME
# =====================================================

STYLE = """
QWidget {
    font-family: 'Segoe UI';
    color: white;
    background: transparent;
}

QFrame#container {
    background-color: rgba(23, 26, 35, 8);
    
}

QLabel#song {
    color: #FFFFFF;
    font-family: 'Segoe UI';
    font-size: 13px;
    font-weight: 650;
    background: transparent;
    border: none;
    padding: 0px;
    margin: 0px;
}

QLabel#artist {
    color: rgba(225, 229, 238, 210);
    font-family: 'Segoe UI';
    font-size: 10px;
    font-weight: 400;
    background: transparent;
    border: none;
    padding: 0px;
    margin: 0px;
}

QPushButton {
    border: 1px solid rgba(255, 255, 255, 35);
    border-radius: 16px;
    background-color: rgba(255, 255, 255, 15);
    color: #FFFFFF;
    font-size: 15px;
    font-weight: 600;
}

QPushButton:hover {
    background-color: rgba(255, 255, 255, 35);
    border: 1px solid rgba(255, 255, 255, 65);
}

QPushButton#play {
    background-color: rgba(29, 185, 84, 235);
    color: #07190D;
    font-size: 17px;
    border: 1px solid rgba(255, 255, 255, 45);
    border-radius: 20px;
}

QPushButton#play:hover {
    background-color: #1ED760;
}
"""


# =====================================================
# MAIN WIDGET
# =====================================================

class SpotifyWidget(QWidget):

    # -------------------------------------------------
    # ROUNDED WINDOW MASK
    # -------------------------------------------------

    def resizeEvent(self, event):

        path = QPainterPath()

        path.addRoundedRect(
            0.0,
            0.0,
            float(self.width()),
            float(self.height()),
            22.0,
            22.0
        )

        self.setMask(
            QRegion(path.toFillPolygon().toPolygon())
        )

        super().resizeEvent(event)

    # -------------------------------------------------
    # INITIALIZATION
    # -------------------------------------------------

    def __init__(self):
        super().__init__()

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowStaysOnTopHint
        )

        self.setAttribute(
            Qt.WidgetAttribute.WA_TranslucentBackground
        )

        self.setAttribute(
            Qt.WidgetAttribute.WA_NoSystemBackground,
            True
        )

        self.setStyleSheet(STYLE)
        self.setFixedSize(340, 94)

        self.dragging = False
        self.is_playing = False
        self.current_image_url = None
        self.acrylic_applied = False

        # Tracks whether music has started during
        # this monitor session.
        self.has_started_playing = False

        # Main container
        self.container = QFrame()
        self.container.setObjectName("container")

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self.container)

        layout = QHBoxLayout(self.container)
        layout.setContentsMargins(11, 10, 11, 10)
        layout.setSpacing(11)

        # Album artwork
        self.album_art = QLabel("♪")
        self.album_art.setFixedSize(62, 62)

        self.album_art.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        self.album_art.setStyleSheet("""
            background-color: rgba(255,255,255,12);
            border-radius: 12px;
            color: white;
            font-size: 27px;
            border: 1px solid rgba(255,255,255,35);
        """)

        layout.addWidget(self.album_art)

        # Song information
        info_layout = QVBoxLayout()
        info_layout.setContentsMargins(0, 0, 0, 0)
        info_layout.setSpacing(0)

        self.song_title = QLabel("Not playing")
        self.song_title.setObjectName("song")
        self.song_title.setWordWrap(False)
        self.song_title.setFixedHeight(20)

        self.artist = QLabel("Open Spotify to start")
        self.artist.setObjectName("artist")
        self.artist.setWordWrap(False)
        self.artist.setFixedHeight(16)

        info_layout.addWidget(self.song_title)
        info_layout.addWidget(self.artist)

        info_layout.setAlignment(
            Qt.AlignmentFlag.AlignVCenter
        )

        layout.addLayout(info_layout, 1)

        # Playback controls
        controls = QHBoxLayout()
        controls.setSpacing(7)

        self.previous_button = QPushButton("◀|")
        self.previous_button.setFixedSize(32, 32)

        self.play_button = QPushButton("▶")
        self.play_button.setObjectName("play")
        self.play_button.setFixedSize(40, 40)

        self.next_button = QPushButton("|▶")
        self.next_button.setFixedSize(32, 32)

        controls.addWidget(self.previous_button)
        controls.addWidget(self.play_button)
        controls.addWidget(self.next_button)

        layout.addLayout(controls)

        # Connect buttons
        self.previous_button.clicked.connect(
            self.previous_song
        )

        self.play_button.clicked.connect(
            self.toggle_playback
        )

        self.next_button.clicked.connect(
            self.next_song
        )

        # -------------------------------------------------
        # BACKGROUND PLAYBACK MONITOR
        # -------------------------------------------------

        self.monitor_timer = QTimer(self)

        self.monitor_timer.timeout.connect(
            self.check_spotify_playback
        )

        # Check Spotify every 5 seconds
        self.monitor_timer.start(5000)

        # Start hidden. Never display an idle widget.
        self.hide()

        # Initial background check
        QTimer.singleShot(
            500,
            self.check_spotify_playback
        )

    # =================================================
    # SHOW WIDGET
    # =================================================

    def show_widget(self):

        if not self.isVisible():

            self.show()

            if not self.acrylic_applied:

                QTimer.singleShot(
                    300,
                    self.apply_acrylic
                )

    def apply_acrylic(self):

        if self.isVisible():

            self.acrylic_applied = enable_acrylic(
                int(self.winId())
            )

            print(
                "Windows Acrylic enabled:",
                self.acrylic_applied
            )

    # =================================================
    # HIDE WIDGET
    # =================================================

    def hide_widget(self):

        if self.isVisible():
            self.hide()

    # =================================================
    # SPOTIFY PLAYBACK DETECTION
    # =================================================

    def check_spotify_playback(self):

        try:

            playback = sp.current_playback()

            # Spotify closed, no active device,
            # or no current track.
            if not playback or not playback.get("item"):

                self.has_started_playing = False
                self.is_playing = False
                self.hide_widget()

                return

            is_playing = playback.get(
                "is_playing", False
            )

            # Music has actually started
            if is_playing:

                self.has_started_playing = True

                self.show_widget()

                self.update_track_information(playback)

            # Music is paused after starting
            elif self.has_started_playing:

                self.show_widget()

                self.update_track_information(playback)

            # Spotify may have an old paused track
            # from before this monitor was launched.
            else:

                self.hide_widget()

        except Exception as error:

            # Temporary API/network errors should not
            # cause the widget to disappear.
            print(
                "Playback monitoring error:",
                error
            )

    # =================================================
    # UPDATE TRACK INFORMATION
    # =================================================

    def update_track_information(self, playback):

        track = playback["item"]

        title = track.get(
            "name",
            "Unknown song"
        )

        artists = ", ".join(
            artist["name"]
            for artist in track.get("artists", [])
        )

        self.song_title.setText(title)
        self.artist.setText(artists)

        self.is_playing = playback.get(
            "is_playing", False
        )

        self.play_button.setText(
            "Ⅱ" if self.is_playing else "▶"
        )

        # Album artwork
        images = track.get("album", {}).get(
            "images", []
        )

        if images:

            image_url = images[0]["url"]

            if image_url != self.current_image_url:

                try:

                    response = requests.get(
                        image_url,
                        timeout=8
                    )

                    response.raise_for_status()

                    pixmap = QPixmap()

                    pixmap.loadFromData(
                        response.content
                    )

                    if not pixmap.isNull():

                        self.album_art.setPixmap(
                            self.make_rounded_pixmap(pixmap)
                        )

                        self.current_image_url = image_url

                except Exception as error:

                    print("Artwork error:", error)

    # =================================================
    # ROUNDED ALBUM ARTWORK
    # =================================================

    def make_rounded_pixmap(self, pixmap, radius=12):

        size = 62

        source = pixmap.scaled(
            size,
            size,
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation
        )

        x = (source.width() - size) // 2
        y = (source.height() - size) // 2

        source = source.copy(x, y, size, size)

        result = QPixmap(size, size)
        result.fill(Qt.GlobalColor.transparent)

        painter = QPainter(result)

        painter.setRenderHint(
            QPainter.RenderHint.Antialiasing
        )

        painter.setRenderHint(
            QPainter.RenderHint.SmoothPixmapTransform
        )

        path = QPainterPath()

        path.addRoundedRect(
            0.0,
            0.0,
            float(size),
            float(size),
            float(radius),
            float(radius)
        )

        painter.setClipPath(path)
        painter.drawPixmap(0, 0, source)

        painter.end()

        return result

    # =================================================
    # PLAY / PAUSE
    # =================================================

    def toggle_playback(self):

        try:

            if self.is_playing:

                sp.pause_playback()

            else:

                sp.start_playback()

            QTimer.singleShot(
                700,
                self.check_spotify_playback
            )

        except Exception as error:

            print("Playback error:", error)

    # =================================================
    # NEXT SONG
    # =================================================

    def next_song(self):

        try:

            sp.next_track()

            QTimer.singleShot(
                700,
                self.check_spotify_playback
            )

        except Exception as error:

            print("Next track error:", error)

    # =================================================
    # PREVIOUS SONG
    # =================================================

    def previous_song(self):

        try:

            sp.previous_track()

            QTimer.singleShot(
                700,
                self.check_spotify_playback
            )

        except Exception as error:

            print("Previous track error:", error)

    # =================================================
    # DRAG WINDOW
    # =================================================

    def mousePressEvent(self, event):

        if event.button() == Qt.MouseButton.LeftButton:

            self.dragging = True

            self.drag_position = (
                event.globalPosition().toPoint()
                - self.frameGeometry().topLeft()
            )

    def mouseMoveEvent(self, event):

        if (
            self.dragging
            and event.buttons() & Qt.MouseButton.LeftButton
        ):

            self.move(
                event.globalPosition().toPoint()
                - self.drag_position
            )

    def mouseReleaseEvent(self, event):

        if event.button() == Qt.MouseButton.LeftButton:
            self.dragging = False


# =====================================================
# APPLICATION START
# =====================================================

if __name__ == "__main__":

    app = QApplication(sys.argv)

    app.setApplicationName("Spotify Glass Widget")

    widget = SpotifyWidget()

    widget.move(300, 300)

    # Widget stays hidden until playback starts.
    sys.exit(app.exec())
