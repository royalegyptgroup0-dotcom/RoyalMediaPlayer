import os
import sys
import time
import unittest
from pathlib import Path

# Headless platform for automated verification
os.environ["QT_QPA_PLATFORM"] = "offscreen"

# Ensure VLC path is available on Windows
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

# Add development directory to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
DEV_DIR = BASE_DIR / "development"
MEDIA_DIR = BASE_DIR / "test_media"
sys.path.insert(0, str(DEV_DIR))

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt, QUrl, QMimeData, QPoint
from PySide6.QtGui import QDragEnterEvent, QDropEvent, QDragMoveEvent

import vlc
from RoyalMediaPlayer import RoyalMediaPlayer, format_time


app = QApplication.instance() or QApplication(sys.argv)


class TestRoyalMediaPlayer(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.audio_file = str(MEDIA_DIR / "sample_audio.mp3")
        cls.audio2_file = str(MEDIA_DIR / "sample_audio2.wav")
        cls.video_file = str(MEDIA_DIR / "sample_video.mp4")
        cls.video2_file = str(MEDIA_DIR / "sample_video2.mkv")

        for f in [cls.audio_file, cls.audio2_file, cls.video_file, cls.video2_file]:
            if not os.path.exists(f):
                raise FileNotFoundError(f"Required test media missing: {f}")

    def setUp(self):
        self.player = RoyalMediaPlayer()
        self.player.show()
        app.processEvents()

    def tearDown(self):
        if hasattr(self, "player") and self.player:
            self.player.close()
            app.processEvents()

    # -------------------------------------------------------------
    # 1. Qt Interface & Control Elements
    # -------------------------------------------------------------
    def test_01_qt_initialization(self):
        self.assertEqual(self.player.windowTitle(), "Royal Media Player")
        self.assertIsNotNone(self.player.video_frame)
        self.assertIsNotNone(self.player.video_label)
        self.assertIsNotNone(self.player.playlist)
        self.assertIsNotNone(self.player.position_slider)
        self.assertIsNotNone(self.player.time_label)
        self.assertIsNotNone(self.player.volume_label)
        self.assertIsNotNone(self.player.volume_slider)
        self.assertIsNotNone(self.player.play_button)
        self.assertIsNotNone(self.player.stop_button)
        self.assertIsNotNone(self.player.next_button)
        self.assertIsNotNone(self.player.previous_button)
        self.assertIsNotNone(self.player.open_button)
        self.assertIsNotNone(self.player.fullscreen_button)

        self.assertEqual(self.player.volume_slider.value(), 80)
        self.assertEqual(self.player.position_slider.value(), 0)
        self.assertIn("00:00", self.player.time_label.text())

    # -------------------------------------------------------------
    # 2. VLC Core Setup
    # -------------------------------------------------------------
    def test_02_vlc_instance(self):
        self.assertIsNotNone(self.player.instance)
        self.assertIsNotNone(self.player.player)
        self.assertTrue(self.player.video_frame.winId() > 0)

    # -------------------------------------------------------------
    # 3. Audio Playback, Label Feedback, Volume, Pause, Stop
    # -------------------------------------------------------------
    def test_03_audio_playback(self):
        success = self.player.play_file(self.audio_file)
        self.assertTrue(success, "Failed to start audio playback")
        self.assertEqual(self.player.current_file, os.path.abspath(self.audio_file))
        self.assertEqual(self.player.play_button.text(), "Pause")

        # Verify Audio Feedback on video_label
        self.assertTrue(self.player.video_label.isVisible())
        self.assertIn("sample_audio.mp3", self.player.video_label.text())

        # Let VLC spin up to Playing
        deadline = time.time() + 2.0
        while time.time() < deadline:
            app.processEvents()
            state = self.player.player.get_state()
            if state == vlc.State.Playing:
                break
            time.sleep(0.05)

        # Test Volume control
        self.player.volume_slider.setValue(65)
        self.assertEqual(self.player.volume_label.text(), "Volume 65%")

        # Verify VLC reflects volume asynchronously
        vol_deadline = time.time() + 1.5
        applied_vol = self.player.player.audio_get_volume()
        while time.time() < vol_deadline and applied_vol != 65:
            app.processEvents()
            time.sleep(0.05)
            applied_vol = self.player.player.audio_get_volume()
        self.assertEqual(applied_vol, 65)

        # Test Pause
        self.player.play_pause()
        pause_deadline = time.time() + 1.5
        while time.time() < pause_deadline:
            app.processEvents()
            if self.player.player.get_state() == vlc.State.Paused:
                break
            time.sleep(0.03)
        self.assertEqual(self.player.play_button.text(), "Play")

        # Test Resume
        self.player.play_pause()
        resume_deadline = time.time() + 1.5
        while time.time() < resume_deadline:
            app.processEvents()
            if self.player.player.get_state() == vlc.State.Playing:
                break
            time.sleep(0.03)
        self.assertEqual(self.player.play_button.text(), "Pause")
        self.assertTrue(self.player.video_label.isVisible())

        # Test Stop
        self.player.stop()
        app.processEvents()
        self.assertEqual(self.player.play_button.text(), "Play")
        self.assertEqual(self.player.position_slider.value(), 0)
        self.assertEqual(self.player.video_label.text(), "ROYAL MEDIA PLAYER")

    # -------------------------------------------------------------
    # 4. Video Playback & Seek
    # -------------------------------------------------------------
    def test_04_video_playback_and_seek(self):
        success = self.player.play_file(self.video_file)
        self.assertTrue(success, "Failed to start video playback")

        # For video, label should be hidden
        self.assertFalse(self.player.video_label.isVisible())

        deadline = time.time() + 2.0
        while time.time() < deadline:
            app.processEvents()
            state = self.player.player.get_state()
            if state in (vlc.State.Playing, vlc.State.Buffering, vlc.State.Opening):
                break
            time.sleep(0.05)

        # Test seek
        self.player.seek(500)
        app.processEvents()

        # Position update
        self.player.update_position()
        self.player.stop()
        self.assertTrue(self.player.video_label.isVisible())

    # -------------------------------------------------------------
    # 5. Playlist Management & Navigation
    # -------------------------------------------------------------
    def test_05_playlist_management(self):
        # Add audio and video
        res1 = self.player.add_to_playlist(self.audio_file)
        self.assertTrue(res1)
        self.assertEqual(self.player.playlist.count(), 1)

        res2 = self.player.add_to_playlist(self.video_file)
        self.assertTrue(res2)
        self.assertEqual(self.player.playlist.count(), 2)

        # Duplicate rejection
        res_dup = self.player.add_to_playlist(self.audio_file)
        self.assertFalse(res_dup, "Duplicate file should not be re-added")
        self.assertEqual(self.player.playlist.count(), 2)

        # Navigation: play first, then next
        self.player.playlist.setCurrentRow(0)
        self.player.play_file(self.audio_file)

        self.player.next()
        app.processEvents()
        self.assertEqual(self.player.playlist.currentRow(), 1)
        self.assertEqual(self.player.current_file, os.path.abspath(self.video_file))

        # Navigation: previous
        self.player.previous()
        app.processEvents()
        self.assertEqual(self.player.playlist.currentRow(), 0)
        self.assertEqual(self.player.current_file, os.path.abspath(self.audio_file))

    # -------------------------------------------------------------
    # 6. Drag and Drop Verification (DragEnter, DragMove, Drop)
    # -------------------------------------------------------------
    def test_06_drag_and_drop(self):
        # Test collect_media_paths directly with directory
        paths = self.player.collect_media_paths([str(MEDIA_DIR)])
        self.assertGreaterEqual(len(paths), 4)

        mime = QMimeData()
        mime.setUrls([QUrl.fromLocalFile(self.video2_file)])

        # Test DragEnter on playlist widget through eventFilter
        enter_event = QDragEnterEvent(
            QPoint(20, 20),
            Qt.DropAction.CopyAction,
            mime,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
        handled_enter = self.player.eventFilter(self.player.playlist, enter_event)
        self.assertTrue(handled_enter)
        self.assertTrue(enter_event.isAccepted(), "DragEnter on playlist should be accepted")

        # Test DragMove on playlist widget through eventFilter
        move_event = QDragMoveEvent(
            QPoint(20, 20),
            Qt.DropAction.CopyAction,
            mime,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
        handled_move = self.player.eventFilter(self.player.playlist, move_event)
        self.assertTrue(handled_move)
        self.assertTrue(move_event.isAccepted(), "DragMove on playlist MUST be accepted for drop to succeed")

        # Test Drop event
        drop_event = QDropEvent(
            QPoint(100, 100),
            Qt.DropAction.CopyAction,
            mime,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
        self.player._process_drop_event(drop_event)
        app.processEvents()

        # The dropped file should be in playlist and currently playing
        self.assertEqual(self.player.current_file, os.path.abspath(self.video2_file))
        self.player.stop()

    # -------------------------------------------------------------
    # 7. Clean Exit during Active Playback
    # -------------------------------------------------------------
    def test_07_clean_exit_during_playback(self):
        self.player.play_file(self.video_file)
        app.processEvents()
        time.sleep(0.1)

        # Trigger closeEvent
        self.player.close()
        app.processEvents()

        # Check closing state and resource release
        self.assertTrue(self.player._closing)
        self.assertFalse(self.player.timer.isActive())
        self.assertIsNone(self.player.player)
        self.assertIsNone(self.player.instance)

    # -------------------------------------------------------------
    # 8. Time Formatting Helper
    # -------------------------------------------------------------
    def test_08_format_time(self):
        self.assertEqual(format_time(0), "00:00")
        self.assertEqual(format_time(65000), "01:05")
        self.assertEqual(format_time(3665000), "01:01:05")


if __name__ == "__main__":
    unittest.main(verbosity=2)
