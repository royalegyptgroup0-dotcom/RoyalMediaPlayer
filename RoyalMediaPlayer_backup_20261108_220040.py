import sys
import os
import vlc

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QSlider,
    QFileDialog,
    QListWidget,
    QSplitter,
)


class RoyalMediaPlayer(QMainWindow):

    def __init__(self):
        super().__init__()

        self.setWindowTitle("Royal Media Player")
        self.resize(1100, 700)

        self.instance = vlc.Instance(
            "--no-video-title-show"
        )

        self.player = self.instance.media_player_new()

        self.current_file = None

        self.create_interface()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_position)
        self.timer.start(500)

    # =========================================================
    # INTERFACE
    # =========================================================

    def create_interface(self):

        central = QWidget()
        self.setCentralWidget(central)

        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # -----------------------------------------------------
        # VIDEO AREA
        # -----------------------------------------------------

        self.video_frame = QWidget()
        self.video_frame.setAttribute(
            Qt.WidgetAttribute.WA_NativeWindow
        )

        self.video_frame.setStyleSheet(
            "background-color: black;"
        )

        video_layout = QVBoxLayout(self.video_frame)
        video_layout.setContentsMargins(0, 0, 0, 0)

        self.video_label = QLabel(
            "ROYAL MEDIA PLAYER"
        )

        self.video_label.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        self.video_label.setStyleSheet(
            """
            color: #888888;
            font-size: 26px;
            font-weight: bold;
            """
        )

        video_layout.addWidget(self.video_label)

        # -----------------------------------------------------
        # PLAYLIST
        # -----------------------------------------------------

        self.playlist = QListWidget()

        self.playlist.setMinimumWidth(260)

        self.playlist.itemDoubleClicked.connect(
            self.play_selected
        )

        splitter = QSplitter(
            Qt.Orientation.Horizontal
        )

        splitter.addWidget(
            self.video_frame
        )

        splitter.addWidget(
            self.playlist
        )

        splitter.setSizes(
            [850, 250]
        )

        main_layout.addWidget(
            splitter,
            1
        )

        # -----------------------------------------------------
        # PROGRESS BAR
        # -----------------------------------------------------

        self.position_slider = QSlider(
            Qt.Orientation.Horizontal
        )

        self.position_slider.setRange(
            0,
            1000
        )

        self.position_slider.sliderMoved.connect(
            self.seek
        )

        main_layout.addWidget(
            self.position_slider
        )

        # -----------------------------------------------------
        # BUTTONS
        # -----------------------------------------------------

        controls = QHBoxLayout()

        controls.setContentsMargins(
            10,
            8,
            10,
            8
        )

        self.open_button = QPushButton(
            "📂 Open"
        )

        self.open_button.clicked.connect(
            self.open_file
        )

        self.previous_button = QPushButton(
            "⏮"
        )

        self.previous_button.clicked.connect(
            self.previous
        )

        self.play_button = QPushButton(
            "▶"
        )

        self.play_button.clicked.connect(
            self.play_pause
        )

        self.stop_button = QPushButton(
            "⏹"
        )

        self.stop_button.clicked.connect(
            self.stop
        )

        self.next_button = QPushButton(
            "⏭"
        )

        self.next_button.clicked.connect(
            self.next
        )

        self.fullscreen_button = QPushButton(
            "⛶"
        )

        self.fullscreen_button.clicked.connect(
            self.fullscreen
        )

        volume_label = QLabel(
            "🔊"
        )

        self.volume_slider = QSlider(
            Qt.Orientation.Horizontal
        )

        self.volume_slider.setRange(
            0,
            100
        )

        self.volume_slider.setValue(
            80
        )

        self.volume_slider.valueChanged.connect(
            self.change_volume
        )

        controls.addWidget(
            self.open_button
        )

        controls.addWidget(
            self.previous_button
        )

        controls.addWidget(
            self.play_button
        )

        controls.addWidget(
            self.stop_button
        )

        controls.addWidget(
            self.next_button
        )

        controls.addWidget(
            self.fullscreen_button
        )

        controls.addStretch()

        controls.addWidget(
            volume_label
        )

        controls.addWidget(
            self.volume_slider
        )

        main_layout.addLayout(
            controls
        )

        # -----------------------------------------------------
        # STYLE
        # -----------------------------------------------------

        self.setStyleSheet(
            """
            QMainWindow {
                background: #101010;
            }

            QWidget {
                background: #101010;
                color: white;
            }

            QPushButton {
                background: #202020;
                color: white;
                border: 1px solid #333333;
                border-radius: 6px;
                padding: 8px 14px;
                font-size: 15px;
            }

            QPushButton:hover {
                background: #303030;
            }

            QListWidget {
                background: #181818;
                color: white;
                border: none;
                padding: 5px;
                font-size: 14px;
            }

            QListWidget::item {
                padding: 8px;
            }

            QListWidget::item:selected {
                background: #333333;
            }

            QSlider::groove:horizontal {
                height: 5px;
                background: #333333;
            }

            QSlider::handle:horizontal {
                width: 14px;
                margin: -5px 0;
                background: white;
                border-radius: 7px;
            }
            """
        )

    # =========================================================
    # OPEN FILE
    # =========================================================

    def open_file(self):

        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Open Media",
            "",
            """
            Media Files
            (*.mp4 *.mkv *.avi *.mov *.wmv *.webm
             *.mp3 *.wav *.flac *.aac *.ogg *.m4a);
            ;All Files (*)
            """
        )

        if file_path:

            self.add_to_playlist(
                file_path
            )

            self.play_file(
                file_path
            )

    # =========================================================
    # PLAY FILE
    # =========================================================

    def play_file(self, file_path):

        if not os.path.exists(file_path):
            return

        self.current_file = file_path

        media = self.instance.media_new(
            file_path
        )

        self.player.set_media(
            media
        )

        self.video_label.hide()

        self.player.set_hwnd(
            int(
                self.video_frame.winId()
            )
        )

        self.player.audio_set_volume(
            self.volume_slider.value()
        )

        self.player.play()

        self.play_button.setText(
            "⏸"
        )

    # =========================================================
    # PLAY / PAUSE
    # =========================================================

    def play_pause(self):

        if self.player.is_playing():

            self.player.pause()

            self.play_button.setText(
                "▶"
            )

        else:

            self.player.play()

            self.play_button.setText(
                "⏸"
            )

    # =========================================================
    # STOP
    # =========================================================

    def stop(self):

        self.player.stop()

        self.play_button.setText(
            "▶"
        )

        self.position_slider.setValue(
            0
        )

        self.video_label.show()

    # =========================================================
    # PLAYLIST
    # =========================================================

    def add_to_playlist(self, file_path):

        name = os.path.basename(
            file_path
        )

        for i in range(
            self.playlist.count()
        ):

            existing = self.playlist.item(i)

            if existing.data(
                Qt.ItemDataRole.UserRole
            ) == file_path:

                self.playlist.setCurrentRow(
                    i
                )

                return

        item = self.playlist.addItem(
            name
        )

        # QListWidget.addItem returns None,
        # so get the newly-created item.

        new_item = self.playlist.item(
            self.playlist.count() - 1
        )

        new_item.setData(
            Qt.ItemDataRole.UserRole,
            file_path
        )

        self.playlist.setCurrentItem(
            new_item
        )

    # =========================================================
    # SELECT PLAYLIST ITEM
    # =========================================================

    def play_selected(self, item):

        file_path = item.data(
            Qt.ItemDataRole.UserRole
        )

        if file_path:

            self.play_file(
                file_path
            )

    # =========================================================
    # NEXT
    # =========================================================

    def next(self):

        row = self.playlist.currentRow()

        if row < self.playlist.count() - 1:

            row += 1

            self.playlist.setCurrentRow(
                row
            )

            item = self.playlist.item(
                row
            )

            self.play_file(
                item.data(
                    Qt.ItemDataRole.UserRole
                )
            )

    # =========================================================
    # PREVIOUS
    # =========================================================

    def previous(self):

        row = self.playlist.currentRow()

        if row > 0:

            row -= 1

            self.playlist.setCurrentRow(
                row
            )

            item = self.playlist.item(
                row
            )

            self.play_file(
                item.data(
                    Qt.ItemDataRole.UserRole
                )
            )

    # =========================================================
    # POSITION UPDATE
    # =========================================================

    def update_position(self):

        if not self.player:
            return

        length = self.player.get_length()

        if length > 0:

            position = self.player.get_position()

            self.position_slider.blockSignals(
                True
            )

            self.position_slider.setValue(
                int(position * 1000)
            )

            self.position_slider.blockSignals(
                False
            )

    # =========================================================
    # SEEK
    # =========================================================

    def seek(self, value):

        self.player.set_position(
            value / 1000
        )

    # =========================================================
    # VOLUME
    # =========================================================

    def change_volume(self, value):

        self.player.audio_set_volume(
            value
        )

    # =========================================================
    # FULLSCREEN
    # =========================================================

    def fullscreen(self):

        if self.isFullScreen():

            self.showNormal()

        else:

            self.showFullScreen()

    # =========================================================
    # KEYBOARD
    # =========================================================

    def keyPressEvent(self, event):

        if event.key() == Qt.Key.Key_Space:

            self.play_pause()

        elif event.key() == Qt.Key.Key_F:

            self.fullscreen()

        elif event.key() == Qt.Key.Key_Escape:

            self.showNormal()

        else:

            super().keyPressEvent(event)


# =============================================================
# START
# =============================================================

if __name__ == "__main__":

    app = QApplication(sys.argv)

    window = RoyalMediaPlayer()

    window.show()

    sys.exit(
        app.exec()
    )