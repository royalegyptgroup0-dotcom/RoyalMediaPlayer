import sys
import os

# Ensure VLC DLLs and plugins are discoverable on Windows
if sys.platform.startswith("win"):
    vlc_dir = r"C:\Program Files\VideoLAN\VLC"
    if os.path.isdir(vlc_dir):
        if hasattr(os, "add_dll_directory"):
            try:
                os.add_dll_directory(vlc_dir)
            except Exception:
                pass
        if vlc_dir not in os.environ.get("PATH", ""):
            os.environ["PATH"] = vlc_dir + ";" + os.environ.get("PATH", "")

import vlc

from PySide6.QtCore import Qt, QTimer, QEvent
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


def format_time(ms):
    """Format milliseconds into MM:SS or HH:MM:SS."""
    if ms is None or ms < 0:
        ms = 0
    total_seconds = int(ms // 1000)
    minutes = total_seconds // 60
    seconds = total_seconds % 60
    hours = minutes // 60
    if hours > 0:
        minutes = minutes % 60
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    return f"{minutes:02d}:{seconds:02d}"


class RoyalMediaPlayer(QMainWindow):

    MEDIA_EXTENSIONS = {
        ".mp4", ".mkv", ".avi", ".mov", ".wmv", ".webm",
        ".mp3", ".wav", ".flac", ".aac", ".ogg", ".m4a",
    }

    AUDIO_EXTENSIONS = {
        ".mp3", ".wav", ".flac", ".aac", ".ogg", ".m4a",
    }

    def __init__(self):
        super().__init__()

        self.setAcceptDrops(True)
        self.setWindowTitle("Royal Media Player")
        self.resize(1100, 700)

        self.instance = vlc.Instance(
            "--no-video-title-show",
            "--quiet",
            "--no-stats"
        )

        self.player = self.instance.media_player_new()

        self.current_file = None
        self.current_media = None
        self._ended_file = None
        self._closing = False
        self._is_audio_file = False

        self.create_interface()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_position)
        self.timer.start(300)

    # =========================================================
    # INTERFACE
    # =========================================================

    def create_interface(self):

        central = QWidget()
        central.setAcceptDrops(True)
        central.installEventFilter(self)
        self.setCentralWidget(central)

        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # -----------------------------------------------------
        # VIDEO AREA
        # -----------------------------------------------------

        self.video_frame = QWidget()
        self.video_frame.setAcceptDrops(True)
        self.video_frame.installEventFilter(self)
        self.video_frame.setAttribute(
            Qt.WidgetAttribute.WA_NativeWindow
        )

        self.video_frame.setStyleSheet(
            "background-color: black;"
        )

        video_layout = QVBoxLayout(self.video_frame)
        video_layout.setContentsMargins(0, 0, 0, 0)

        self.video_label = QLabel("ROYAL MEDIA PLAYER")
        self.video_label.setAcceptDrops(True)
        self.video_label.installEventFilter(self)
        self.video_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.video_label.setWordWrap(True)

        self.video_label.setStyleSheet(
            """
            color: #d4af37;
            font-size: 24px;
            font-weight: bold;
            padding: 20px;
            """
        )

        video_layout.addWidget(self.video_label)

        # -----------------------------------------------------
        # PLAYLIST
        # -----------------------------------------------------

        self.playlist = QListWidget()
        self.playlist.setAcceptDrops(True)
        self.playlist.installEventFilter(self)
        self.playlist.setMinimumWidth(260)

        self.playlist.itemDoubleClicked.connect(
            self.play_selected
        )

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setAcceptDrops(True)
        splitter.installEventFilter(self)

        splitter.addWidget(self.video_frame)
        splitter.addWidget(self.playlist)

        splitter.setSizes([850, 250])

        main_layout.addWidget(splitter, 1)

        # -----------------------------------------------------
        # PROGRESS BAR & TIME DISPLAY
        # -----------------------------------------------------

        progress_layout = QHBoxLayout()
        progress_layout.setContentsMargins(10, 4, 10, 4)
        progress_layout.setSpacing(10)

        self.position_slider = QSlider(Qt.Orientation.Horizontal)
        self.position_slider.setRange(0, 1000)
        self.position_slider.sliderMoved.connect(self.seek)
        self.position_slider.sliderReleased.connect(self._on_slider_released)

        self.time_label = QLabel("00:00 / 00:00")
        self.time_label.setMinimumWidth(110)
        self.time_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.time_label.setStyleSheet("color: #a0a0a0; font-size: 13px; font-weight: bold;")

        progress_layout.addWidget(self.position_slider, 1)
        progress_layout.addWidget(self.time_label)

        main_layout.addLayout(progress_layout)

        # -----------------------------------------------------
        # BUTTONS & CONTROLS
        # -----------------------------------------------------

        controls = QHBoxLayout()
        controls.setContentsMargins(10, 8, 10, 8)
        controls.setSpacing(8)

        self.open_button = QPushButton("Open")
        self.open_button.clicked.connect(self.open_file)

        self.previous_button = QPushButton("Previous")
        self.previous_button.clicked.connect(self.previous)

        self.play_button = QPushButton("Play")
        self.play_button.clicked.connect(self.play_pause)

        self.stop_button = QPushButton("Stop")
        self.stop_button.clicked.connect(self.stop)

        self.next_button = QPushButton("Next")
        self.next_button.clicked.connect(self.next)

        self.fullscreen_button = QPushButton("Fullscreen")
        self.fullscreen_button.clicked.connect(self.fullscreen)

        self.volume_label = QLabel("Volume 80%")
        self.volume_label.setStyleSheet("color: #cccccc; font-size: 13px;")

        self.volume_slider = QSlider(Qt.Orientation.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(80)
        self.volume_slider.setMaximumWidth(120)
        self.volume_slider.valueChanged.connect(self.change_volume)

        controls.addWidget(self.open_button)
        controls.addWidget(self.previous_button)
        controls.addWidget(self.play_button)
        controls.addWidget(self.stop_button)
        controls.addWidget(self.next_button)
        controls.addWidget(self.fullscreen_button)

        controls.addStretch()

        controls.addWidget(self.volume_label)
        controls.addWidget(self.volume_slider)

        main_layout.addLayout(controls)

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
                background: #1f1f1f;
                color: #e0e0e0;
                border: 1px solid #333333;
                border-radius: 6px;
                padding: 7px 14px;
                font-size: 14px;
                font-weight: 500;
            }

            QPushButton:hover {
                background: #2c2c2c;
                border-color: #d4af37;
                color: #ffffff;
            }

            QPushButton:pressed {
                background: #3a3a3a;
            }

            QListWidget {
                background: #161616;
                color: #e0e0e0;
                border: 1px solid #252525;
                padding: 4px;
                font-size: 13px;
            }

            QListWidget::item {
                padding: 8px;
                border-radius: 4px;
                margin-bottom: 2px;
            }

            QListWidget::item:hover {
                background: #222222;
            }

            QListWidget::item:selected {
                background: #2a2820;
                color: #d4af37;
                border-left: 3px solid #d4af37;
            }

            QSlider::groove:horizontal {
                height: 5px;
                background: #282828;
                border-radius: 2px;
            }

            QSlider::sub-page:horizontal {
                background: #d4af37;
                border-radius: 2px;
            }

            QSlider::handle:horizontal {
                width: 14px;
                margin: -5px 0;
                background: #ffffff;
                border: 1px solid #d4af37;
                border-radius: 7px;
            }

            QSlider::handle:horizontal:hover {
                background: #d4af37;
            }
            """
        )

    # =========================================================
    # DRAG AND DROP
    # =========================================================

    def eventFilter(self, watched, event):
        event_type = event.type()

        if event_type in (QEvent.Type.DragEnter, QEvent.Type.DragMove):
            if event.mimeData().hasUrls():
                event.acceptProposedAction()
            else:
                event.ignore()
            return True

        if event_type == QEvent.Type.Drop:
            self._process_drop_event(event)
            return True

        if watched == self.video_frame and event_type == QEvent.Type.MouseButtonDblClick:
            self.fullscreen()
            return True

        return super().eventFilter(watched, event)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):
        self._process_drop_event(event)

    def _process_drop_event(self, event):
        if not event.mimeData().hasUrls():
            event.ignore()
            return

        dropped_paths = [
            url.toLocalFile()
            for url in event.mimeData().urls()
            if url.isLocalFile()
        ]

        media_paths = self.collect_media_paths(dropped_paths)

        if not media_paths:
            event.ignore()
            return

        for file_path in media_paths:
            self.add_to_playlist(file_path)

        first_path = os.path.normcase(
            os.path.abspath(os.path.normpath(media_paths[0]))
        )

        selected_row = -1
        for index in range(self.playlist.count()):
            item = self.playlist.item(index)
            existing_path = item.data(Qt.ItemDataRole.UserRole)
            if not existing_path:
                continue

            existing_normalized = os.path.normcase(
                os.path.abspath(os.path.normpath(existing_path))
            )
            if existing_normalized == first_path:
                selected_row = index
                break

        if selected_row >= 0:
            self.playlist.setCurrentRow(selected_row)
            self.play_file(media_paths[0])
            event.acceptProposedAction()
        else:
            event.ignore()

    def collect_media_paths(self, paths):
        collected = []
        seen = set()

        for raw_path in paths:
            if not raw_path:
                continue

            path = os.path.abspath(os.path.normpath(raw_path))

            if os.path.isfile(path):
                candidates = [path]
            elif os.path.isdir(path):
                candidates = []
                for root, directories, filenames in os.walk(path):
                    directories.sort()
                    for filename in sorted(filenames):
                        candidates.append(os.path.join(root, filename))
            else:
                continue

            for candidate in candidates:
                if not os.path.isfile(candidate):
                    continue

                extension = os.path.splitext(candidate)[1].lower()
                if extension not in self.MEDIA_EXTENSIONS:
                    continue

                normalized = os.path.abspath(os.path.normpath(candidate))
                key = os.path.normcase(normalized)

                if key not in seen:
                    seen.add(key)
                    collected.append(normalized)

        return collected

    # =========================================================
    # OPEN FILE
    # =========================================================

    def open_file(self):
        file_paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Open Media",
            "",
            "Media Files (*.mp4 *.mkv *.avi *.mov *.wmv *.webm *.mp3 *.wav *.flac *.aac *.ogg *.m4a);;All Files (*)"
        )

        if file_paths:
            for p in file_paths:
                self.add_to_playlist(p)

            # Play the first newly opened file
            self.play_file(file_paths[0])

    # =========================================================
    # PLAY FILE
    # =========================================================

    def play_file(self, file_path):
        if self._closing or not file_path or not os.path.isfile(file_path):
            return False

        absolute_path = os.path.abspath(file_path)
        ext = os.path.splitext(absolute_path)[1].lower()
        self._is_audio_file = ext in self.AUDIO_EXTENSIONS

        try:
            media = self.instance.media_new(absolute_path)
            if media is None:
                return False

            self.player.set_media(media)

            if sys.platform.startswith("win"):
                self.player.set_hwnd(int(self.video_frame.winId()))

            self.player.audio_set_volume(
                max(0, min(100, self.volume_slider.value()))
            )

            result = self.player.play()
            if result == -1:
                self.play_button.setText("Play")
                return False

            self.current_media = media
            self.current_file = absolute_path
            self._ended_file = None

            # Video vs Audio UI presentation
            if self._is_audio_file:
                track_name = os.path.basename(absolute_path)
                self.video_label.setText(f"🎵 Now Playing:\n{track_name}")
                self.video_label.show()
            else:
                self.video_label.hide()

            self.play_button.setText("Pause")

            self.position_slider.blockSignals(True)
            try:
                self.position_slider.setValue(0)
            finally:
                self.position_slider.blockSignals(False)

            self.time_label.setText("00:00 / 00:00")
            return True

        except Exception as exc:
            print(f"Playback error: {exc}")
            self.play_button.setText("Play")
            return False

    # =========================================================
    # PLAY / PAUSE
    # =========================================================

    def play_pause(self):
        if self._closing or not self.current_file:
            # If no file playing, play current selection in playlist if available
            row = self.playlist.currentRow()
            if row >= 0:
                item = self.playlist.item(row)
                target = item.data(Qt.ItemDataRole.UserRole)
                if target:
                    self.play_file(target)
            return

        try:
            state = self.player.get_state()

            if state == vlc.State.Playing:
                self.player.set_pause(1)
                self.play_button.setText("Play")

            elif state == vlc.State.Paused:
                self.player.set_pause(0)
                self.play_button.setText("Pause")

            else:
                result = self.player.play()
                if result != -1:
                    self.play_button.setText("Pause")
                    if self._is_audio_file:
                        self.video_label.show()
                    else:
                        self.video_label.hide()

        except Exception as exc:
            print(f"Play/Pause error: {exc}")

    # =========================================================
    # STOP
    # =========================================================

    def stop(self):
        if self._closing:
            return

        try:
            self.player.stop()
        except Exception as exc:
            print(f"Stop error: {exc}")

        self.play_button.setText("Play")
        self._ended_file = None

        self.position_slider.blockSignals(True)
        try:
            self.position_slider.setValue(0)
        finally:
            self.position_slider.blockSignals(False)

        self.time_label.setText("00:00 / 00:00")
        self.video_label.setText("ROYAL MEDIA PLAYER")
        self.video_label.show()

    # =========================================================
    # PLAYLIST MANAGEMENT
    # =========================================================

    def add_to_playlist(self, file_path):
        if not file_path or not os.path.isfile(file_path):
            return False

        file_path = os.path.abspath(os.path.normpath(file_path))
        normalized_path = os.path.normcase(file_path)
        name = os.path.basename(file_path)

        for i in range(self.playlist.count()):
            existing = self.playlist.item(i)
            existing_path = existing.data(Qt.ItemDataRole.UserRole)

            if existing_path:
                existing_normalized = os.path.normcase(
                    os.path.abspath(os.path.normpath(existing_path))
                )
                if existing_normalized == normalized_path:
                    self.playlist.setCurrentRow(i)
                    return False

        self.playlist.addItem(name)
        new_item = self.playlist.item(self.playlist.count() - 1)
        new_item.setData(Qt.ItemDataRole.UserRole, file_path)
        self.playlist.setCurrentItem(new_item)
        return True

    def play_selected(self, item):
        file_path = item.data(Qt.ItemDataRole.UserRole)
        if file_path:
            self.play_file(file_path)

    def next(self):
        row = self.playlist.currentRow()
        if row < self.playlist.count() - 1:
            row += 1
            self.playlist.setCurrentRow(row)
            item = self.playlist.item(row)
            target = item.data(Qt.ItemDataRole.UserRole)
            if target:
                self.play_file(target)

    def previous(self):
        row = self.playlist.currentRow()
        if row > 0:
            row -= 1
            self.playlist.setCurrentRow(row)
            item = self.playlist.item(row)
            target = item.data(Qt.ItemDataRole.UserRole)
            if target:
                self.play_file(target)

    # =========================================================
    # POSITION & TIME UPDATE
    # =========================================================

    def update_position(self):
        if self._closing:
            return

        try:
            state = self.player.get_state()

            # Handle end of playback & auto advance
            if (
                state == vlc.State.Ended
                and self.current_file
                and self._ended_file != self.current_file
            ):
                self._ended_file = self.current_file
                row = self.playlist.currentRow()
                if 0 <= row < self.playlist.count() - 1:
                    self.next()
                else:
                    self.stop()
                return

            if state == vlc.State.Playing:
                # Do not fight user dragging the slider
                if not self.position_slider.isSliderDown():
                    position = self.player.get_position()
                    if position >= 0:
                        value = max(0, min(1000, int(position * 1000)))
                        self.position_slider.blockSignals(True)
                        try:
                            self.position_slider.setValue(value)
                        finally:
                            self.position_slider.blockSignals(False)

                length = self.player.get_length()
                current_time = self.player.get_time()
                if length > 0 and current_time >= 0:
                    self.time_label.setText(
                        f"{format_time(current_time)} / {format_time(length)}"
                    )

                self.play_button.setText("Pause")

            elif state == vlc.State.Paused:
                self.play_button.setText("Play")

            elif state == vlc.State.Stopped:
                self.play_button.setText("Play")

        except Exception as exc:
            try:
                self.position_slider.blockSignals(False)
            except Exception:
                pass
            print(f"Position update error: {exc}")

    # =========================================================
    # SEEK
    # =========================================================

    def seek(self, value):
        if self._closing or not self.current_file:
            return

        try:
            length = self.player.get_length()
            if length <= 0:
                return

            position = max(0.0, min(1.0, float(value) / 1000.0))
            self.player.set_position(position)

            approx_time = int(position * length)
            self.time_label.setText(
                f"{format_time(approx_time)} / {format_time(length)}"
            )

        except Exception as exc:
            print(f"Seek error: {exc}")

    def _on_slider_released(self):
        self.seek(self.position_slider.value())

    # =========================================================
    # VOLUME
    # =========================================================

    def change_volume(self, value):
        try:
            clamped = max(0, min(100, int(value)))
            self.player.audio_set_volume(clamped)
            self.volume_label.setText(f"Volume {clamped}%")
        except Exception as exc:
            print(f"Volume error: {exc}")

    # =========================================================
    # FULLSCREEN
    # =========================================================

    def fullscreen(self):
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()

    # =========================================================
    # CLEAN EXIT & KEYBOARD CONTROLS
    # =========================================================

    def closeEvent(self, event):
        self._closing = True

        try:
            if hasattr(self, "timer") and self.timer.isActive():
                self.timer.stop()

            if getattr(self, "player", None):
                self.player.stop()
                if sys.platform.startswith("win"):
                    try:
                        self.player.set_hwnd(0)
                    except Exception:
                        pass
                self.player.release()
                self.player = None

            if getattr(self, "instance", None):
                self.instance.release()
                self.instance = None

            self.current_media = None

        except Exception as exc:
            print(f"Shutdown cleanup error: {exc}")

        super().closeEvent(event)

    def keyPressEvent(self, event):
        key = event.key()

        if key == Qt.Key.Key_Space:
            self.play_pause()

        elif key == Qt.Key.Key_F:
            self.fullscreen()

        elif key == Qt.Key.Key_Escape:
            if self.isFullScreen():
                self.showNormal()

        elif key == Qt.Key.Key_Left:
            # Seek backward 5 seconds
            try:
                curr = self.player.get_time()
                length = self.player.get_length()
                if length > 0 and curr >= 0:
                    new_time = max(0, curr - 5000)
                    self.player.set_time(new_time)
            except Exception:
                pass

        elif key == Qt.Key.Key_Right:
            # Seek forward 5 seconds
            try:
                curr = self.player.get_time()
                length = self.player.get_length()
                if length > 0 and curr >= 0:
                    new_time = min(length, curr + 5000)
                    self.player.set_time(new_time)
            except Exception:
                pass

        elif key == Qt.Key.Key_Up:
            # Volume +5
            val = min(100, self.volume_slider.value() + 5)
            self.volume_slider.setValue(val)

        elif key == Qt.Key.Key_Down:
            # Volume -5
            val = max(0, self.volume_slider.value() - 5)
            self.volume_slider.setValue(val)

        elif key == Qt.Key.Key_M:
            # Toggle mute
            try:
                is_muted = self.player.audio_get_mute()
                self.player.audio_set_mute(not is_muted)
            except Exception:
                pass

        else:
            super().keyPressEvent(event)


# =============================================================
# START
# =============================================================

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = RoyalMediaPlayer()
    window.show()
    sys.exit(app.exec())
