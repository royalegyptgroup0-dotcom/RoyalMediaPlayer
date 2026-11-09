import sys
import os

# =============================================================
# DYNAMIC VLC DISCOVERY & ENVIRONMENT INITIALIZATION
# =============================================================

_VLC_DLL_DIRECTORY_HANDLE = None


def find_vlc_directory():
    """Dynamically discover VLC installation directory on Windows."""
    candidates = []

    # 1. Environment variables
    for var in ("VLC_PATH", "PYTHON_VLC_LIB_PATH"):
        val = os.environ.get(var)
        if val:
            if os.path.isfile(val) and os.path.basename(val).lower() == "libvlc.dll":
                candidates.append(os.path.dirname(val))
            elif os.path.isdir(val):
                candidates.append(val)

    # 2. Windows Registry
    if sys.platform.startswith("win"):
        try:
            import winreg

            reg_paths = [
                (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\VideoLAN\VLC"),
                (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\VideoLAN\VLC"),
                (winreg.HKEY_CURRENT_USER, r"SOFTWARE\VideoLAN\VLC"),
            ]
            for hkey, subkey in reg_paths:
                try:
                    with winreg.OpenKey(hkey, subkey) as key:
                        val, _ = winreg.QueryValueEx(key, "InstallDir")
                        if val and os.path.isdir(val):
                            candidates.append(val)
                except Exception:
                    pass
        except Exception:
            pass

    # 3. Standard Windows directories
    prog_files = os.environ.get("ProgramFiles", r"C:\Program Files")
    prog_files_x86 = os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")
    local_app_data = os.environ.get("LOCALAPPDATA", "")

    standard_paths = [
        os.path.join(prog_files, "VideoLAN", "VLC"),
        os.path.join(prog_files_x86, "VideoLAN", "VLC"),
        r"C:\Program Files\VideoLAN\VLC",
        r"C:\Program Files (x86)\VideoLAN\VLC",
        r"D:\Program Files\VideoLAN\VLC",
        r"C:\VLC",
    ]
    if local_app_data:
        standard_paths.append(os.path.join(local_app_data, "Programs", "VideoLAN", "VLC"))

    candidates.extend(standard_paths)

    # 4. PATH search for vlc.exe
    try:
        import shutil

        vlc_exe = shutil.which("vlc") or shutil.which("vlc.exe")
        if vlc_exe:
            candidates.append(os.path.dirname(os.path.abspath(vlc_exe)))
    except Exception:
        pass

    # Validate candidates: must contain libvlc.dll
    for path in candidates:
        if path and os.path.isdir(path):
            libvlc_dll = os.path.join(path, "libvlc.dll")
            if os.path.isfile(libvlc_dll):
                return os.path.abspath(path)

    return None


def init_vlc_environment():
    """Initialize DLL search paths and retain the DLL directory handle."""
    global _VLC_DLL_DIRECTORY_HANDLE

    if not sys.platform.startswith("win"):
        return

    vlc_dir = find_vlc_directory()
    if not vlc_dir:
        return

    # Retain the handle in module-level global so Python GC does not remove it
    if hasattr(os, "add_dll_directory"):
        try:
            _VLC_DLL_DIRECTORY_HANDLE = os.add_dll_directory(vlc_dir)
        except Exception as exc:
            print(f"Warning: add_dll_directory failed: {exc}")

    # Ensure PATH contains the VLC directory
    current_path = os.environ.get("PATH", "")
    if vlc_dir not in current_path:
        os.environ["PATH"] = vlc_dir + ";" + current_path

    # Hint python-vlc directly to the library file
    libvlc_file = os.path.join(vlc_dir, "libvlc.dll")
    if os.path.isfile(libvlc_file) and "PYTHON_VLC_LIB_PATH" not in os.environ:
        os.environ["PYTHON_VLC_LIB_PATH"] = libvlc_file


# Run environment setup before importing vlc
init_vlc_environment()

try:
    import vlc
except ImportError as exc:
    vlc = None
    print(f"Warning: Failed to import python-vlc: {exc}")

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

        # Widget references
        self.video_frame = None
        self.video_label = None
        self.playlist = None
        self.position_slider = None
        self.time_label = None
        self.volume_label = None
        self.volume_slider = None
        self.open_button = None
        self.previous_button = None
        self.play_button = None
        self.stop_button = None
        self.next_button = None
        self.fullscreen_button = None

        # Playback state
        self.current_file = None
        self.current_media = None
        self._ended_file = None
        self._error_handled_file = None
        self._closing = False
        self._is_audio_file = False
        self._vlc_available = False

        # VLC Instance & Player Initialization with Verification
        self.instance = None
        self.player = None

        if vlc is not None:
            try:
                self.instance = vlc.Instance(
                    "--no-video-title-show",
                    "--quiet",
                    "--no-stats"
                )
                if self.instance is not None:
                    self.player = self.instance.media_player_new()
                    if self.player is not None:
                        self._vlc_available = True
            except Exception as exc:
                print(f"VLC Initialization Error: {exc}")

        # Construct UI
        self.create_interface()

        # Handle VLC unavailable state gracefully
        if not self._vlc_available:
            self.video_label.setText(
                "⚠️ VLC Engine Failed to Initialize\n\n"
                "Please verify that 64-bit VLC Media Player is installed on your system."
            )
            self.video_label.setStyleSheet(
                "color: #ff6b6b; font-size: 18px; font-weight: bold; padding: 20px;"
            )
            for btn in (
                self.play_button,
                self.stop_button,
                self.next_button,
                self.previous_button,
                self.position_slider,
                self.volume_slider,
            ):
                if btn:
                    btn.setEnabled(False)

        # Position updater timer
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

            QPushButton:disabled {
                background: #161616;
                color: #555555;
                border-color: #222222;
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

        if (
            self.video_frame is not None
            and watched == self.video_frame
            and event_type == QEvent.Type.MouseButtonDblClick
        ):
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

        # Play first dropped item and synchronize selection
        played = self.play_file(media_paths[0])
        if played:
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
    # PLAYLIST SELECTION SYNCHRONIZATION
    # =========================================================

    def sync_playlist_to_file(self, file_path):
        """Ensure the selected row in the playlist always matches file_path."""
        if not file_path or self.playlist is None:
            return -1

        normalized_target = os.path.normcase(os.path.abspath(os.path.normpath(file_path)))

        for index in range(self.playlist.count()):
            item = self.playlist.item(index)
            existing_path = item.data(Qt.ItemDataRole.UserRole)
            if not existing_path:
                continue

            existing_normalized = os.path.normcase(
                os.path.abspath(os.path.normpath(existing_path))
            )
            if existing_normalized == normalized_target:
                if self.playlist.currentRow() != index:
                    self.playlist.blockSignals(True)
                    try:
                        self.playlist.setCurrentRow(index)
                    finally:
                        self.playlist.blockSignals(False)
                return index

        return -1

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

            # Play the first opened file and synchronize playlist selection
            self.play_file(file_paths[0])

    # =========================================================
    # PLAYBACK FAILURE HANDLER
    # =========================================================

    def _handle_playback_failure(self, attempted_path, error_msg=""):
        """Safely clear stale metadata and stop playback when a file fails to play."""
        try:
            if self.player:
                self.player.stop()
                self.player.set_media(None)
        except Exception:
            pass

        if self.current_media:
            try:
                self.current_media.release()
            except Exception:
                pass
            self.current_media = None

        self.current_file = None
        self._ended_file = None
        self.play_button.setText("Play")

        self.position_slider.blockSignals(True)
        try:
            self.position_slider.setValue(0)
        finally:
            self.position_slider.blockSignals(False)

        self.time_label.setText("00:00 / 00:00")

        # Clear stale info and display error feedback
        if attempted_path:
            name = os.path.basename(attempted_path)
            self.video_label.setText(f"⚠️ Unable to play:\n{name}")
        else:
            self.video_label.setText("ROYAL MEDIA PLAYER")

        self.video_label.show()

    # =========================================================
    # PLAY FILE (LIFECYCLE SAFE)
    # =========================================================

    def play_file(self, file_path):
        if self._closing or not self._vlc_available or not file_path:
            self._handle_playback_failure(file_path, "Player unavailable or closing")
            return False

        if not os.path.isfile(file_path):
            self._handle_playback_failure(file_path, "File does not exist")
            return False

        absolute_path = os.path.abspath(file_path)
        ext = os.path.splitext(absolute_path)[1].lower()
        self._is_audio_file = ext in self.AUDIO_EXTENSIONS

        try:
            new_media = self.instance.media_new(absolute_path)
            if new_media is None:
                self._handle_playback_failure(file_path, "Failed to create VLC Media")
                return False

            # Attach new media to player first
            self.player.set_media(new_media)

            # Safely release previous media now that the player has switched
            old_media = self.current_media
            self.current_media = new_media
            if old_media is not None:
                try:
                    old_media.release()
                except Exception:
                    pass

            if sys.platform.startswith("win") and self.video_frame is not None:
                try:
                    self.player.set_hwnd(int(self.video_frame.winId()))
                except Exception:
                    pass

            self.player.audio_set_volume(
                max(0, min(100, self.volume_slider.value()))
            )

            result = self.player.play()
            if result == -1:
                self._handle_playback_failure(file_path, "VLC play() returned -1")
                return False

            self.current_file = absolute_path
            self._ended_file = None
            self._error_handled_file = None

            # Always synchronize current playlist selection to this file
            self.sync_playlist_to_file(absolute_path)

            # Audio vs Video UI presentation
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
            self._handle_playback_failure(file_path, str(exc))
            return False

    # =========================================================
    # PLAY / PAUSE
    # =========================================================

    def play_pause(self):
        if self._closing or not self._vlc_available:
            return

        if not self.current_file:
            row = self.playlist.currentRow()
            if row >= 0:
                item = self.playlist.item(row)
                target = item.data(Qt.ItemDataRole.UserRole)
                if target:
                    self.play_file(target)
            elif self.playlist.count() > 0:
                # Play first item in playlist if nothing is currently selected
                item = self.playlist.item(0)
                target = item.data(Qt.ItemDataRole.UserRole)
                if target:
                    self.play_file(target)
            return

        try:
            state = self.player.get_state()

            if state == vlc.State.Playing:
                self.player.set_pause(1)
                self.play_button.setText("Play")

            elif state in (vlc.State.Paused, vlc.State.Opening, vlc.State.Buffering):
                self.player.set_pause(0)
                self.play_button.setText("Pause")
                if self._is_audio_file:
                    self.video_label.show()
                else:
                    self.video_label.hide()

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
        if self._closing or not self._vlc_available:
            return

        try:
            self.player.stop()
        except Exception as exc:
            print(f"Stop error: {exc}")

        self.play_button.setText("Play")
        self._ended_file = None
        self._error_handled_file = None

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
                    return False

        self.playlist.addItem(name)
        new_item = self.playlist.item(self.playlist.count() - 1)
        new_item.setData(Qt.ItemDataRole.UserRole, file_path)
        return True

    def play_selected(self, item):
        file_path = item.data(Qt.ItemDataRole.UserRole)
        if file_path:
            self.play_file(file_path)

    def next(self):
        """Advance to the next playable file, safely skipping missing/corrupted files."""
        if not self._vlc_available or self.playlist is None:
            return False

        count = self.playlist.count()
        if count == 0:
            return False

        current_row = self.playlist.currentRow()
        start_row = current_row if current_row >= 0 else -1

        # Search forward for the next playable file
        for next_row in range(start_row + 1, count):
            item = self.playlist.item(next_row)
            target = item.data(Qt.ItemDataRole.UserRole)
            if not target or not os.path.isfile(target):
                continue

            self.playlist.setCurrentRow(next_row)
            if self.play_file(target):
                return True

        # If reached end without finding another playable file, stop cleanly
        self.stop()
        return False

    def previous(self):
        """Move to previous playable file, safely skipping missing/corrupted files."""
        if not self._vlc_available or self.playlist is None:
            return False

        count = self.playlist.count()
        if count == 0:
            return False

        current_row = self.playlist.currentRow()
        if current_row <= 0:
            return False

        # Search backward for previous playable file
        for prev_row in range(current_row - 1, -1, -1):
            item = self.playlist.item(prev_row)
            target = item.data(Qt.ItemDataRole.UserRole)
            if not target or not os.path.isfile(target):
                continue

            self.playlist.setCurrentRow(prev_row)
            if self.play_file(target):
                return True

        return False

    # =========================================================
    # POSITION & TIME UPDATE
    # =========================================================

    def update_position(self):
        if self._closing or not self._vlc_available:
            return

        try:
            state = self.player.get_state()

            # Handle asynchronous VLC decode/open failures exactly once per file.
            # VLC may return success from play() and report the actual failure later.
            if (
                state == vlc.State.Error
                and self.current_file
                and self._error_handled_file != self.current_file
            ):
                failed_file = self.current_file
                self._error_handled_file = failed_file
                failed_name = os.path.basename(failed_file)
                advanced = self.next()
                if not advanced:
                    self.stop()
                    self.video_label.setText(
                        f"⚠️ Unable to play:\n{failed_name}\nNo more playable files in the playlist."
                    )
                    self.video_label.show()
                return

            # Handle end of playback & auto advance
            if (
                state == vlc.State.Ended
                and self.current_file
                and self._ended_file != self.current_file
            ):
                self._ended_file = self.current_file
                # Attempt to advance to the next playable track
                advanced = self.next()
                if not advanced:
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
        if self._closing or not self._vlc_available or not self.current_file:
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
        if not self._vlc_available:
            return
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
    # ROBUST CLEAN EXIT & COMPREHENSIVE KEYBOARD CONTROLS
    # =========================================================

    def closeEvent(self, event):
        """Robust shutdown cleanup executing all steps independently."""
        self._closing = True

        # 1. Stop timer
        try:
            if hasattr(self, "timer") and self.timer and self.timer.isActive():
                self.timer.stop()
        except Exception as exc:
            print(f"Error stopping timer on shutdown: {exc}")

        # 2. Stop player playback and detach HWND
        try:
            if getattr(self, "player", None):
                self.player.stop()
                if sys.platform.startswith("win"):
                    try:
                        self.player.set_hwnd(0)
                    except Exception:
                        pass
        except Exception as exc:
            print(f"Error stopping player on shutdown: {exc}")

        # 3. Unset media from player
        try:
            if getattr(self, "player", None):
                self.player.set_media(None)
        except Exception as exc:
            print(f"Error unsetting media on shutdown: {exc}")

        # 4. Release current media
        try:
            if getattr(self, "current_media", None):
                self.current_media.release()
                self.current_media = None
        except Exception as exc:
            print(f"Error releasing media on shutdown: {exc}")

        # 5. Release player
        try:
            if getattr(self, "player", None):
                self.player.release()
                self.player = None
        except Exception as exc:
            print(f"Error releasing player on shutdown: {exc}")

        # 6. Release instance
        try:
            if getattr(self, "instance", None):
                self.instance.release()
                self.instance = None
        except Exception as exc:
            print(f"Error releasing instance on shutdown: {exc}")

        # 7. Super class closeEvent
        try:
            super().closeEvent(event)
        except Exception as exc:
            print(f"Error in super().closeEvent: {exc}")

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

        elif key == Qt.Key.Key_N:
            # Next track
            self.next()

        elif key == Qt.Key.Key_P:
            # Previous track
            self.previous()

        elif key in (Qt.Key.Key_S, Qt.Key.Key_Backspace):
            # Stop playback
            self.stop()

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
