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
from PySide6.QtGui import QKeyEvent

import vlc
from RoyalMediaPlayer import RoyalMediaPlayer


app = QApplication.instance() or QApplication(sys.argv)


class TestRoyalMediaPlayerExtended(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.audio_file = str(MEDIA_DIR / "sample_audio.mp3")
        cls.audio2_file = str(MEDIA_DIR / "sample_audio2.wav")
        cls.video_file = str(MEDIA_DIR / "sample_video.mp4")
        cls.video2_file = str(MEDIA_DIR / "sample_video2.mkv")

    def setUp(self):
        self.player = RoyalMediaPlayer()
        self.player.show()
        app.processEvents()

    def tearDown(self):
        if hasattr(self, "player") and self.player:
            self.player.close()
            app.processEvents()

    # -------------------------------------------------------------
    # 1. Test Slider Non-Interference While User is Dragging
    # -------------------------------------------------------------
    def test_slider_drag_protection(self):
        self.player.play_file(self.video_file)
        app.processEvents()

        # Simulate user pressing down and dragging slider to position 750
        self.player.position_slider.setSliderDown(True)
        self.player.position_slider.setValue(750)

        # Trigger update_position while slider is down
        self.player.update_position()
        app.processEvents()

        # Value should NOT have been overwritten by update_position
        self.assertEqual(self.player.position_slider.value(), 750)

        # Release slider
        self.player.position_slider.setSliderDown(False)
        self.player.stop()

    # -------------------------------------------------------------
    # 2. Test Keyboard Shortcuts (Space, F, Esc, Up, Down, M, Arrows)
    # -------------------------------------------------------------
    def test_keyboard_shortcuts(self):
        self.player.add_to_playlist(self.audio_file)
        self.player.playlist.setCurrentRow(0)

        # Space to start playback
        space_event = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Space, Qt.KeyboardModifier.NoModifier)
        self.player.keyPressEvent(space_event)
        app.processEvents()
        self.assertEqual(self.player.current_file, os.path.abspath(self.audio_file))

        # Volume Up (+5)
        initial_vol = self.player.volume_slider.value()
        up_event = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Up, Qt.KeyboardModifier.NoModifier)
        self.player.keyPressEvent(up_event)
        app.processEvents()
        self.assertEqual(self.player.volume_slider.value(), min(100, initial_vol + 5))

        # Volume Down (-5)
        down_event = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Down, Qt.KeyboardModifier.NoModifier)
        self.player.keyPressEvent(down_event)
        app.processEvents()
        self.assertEqual(self.player.volume_slider.value(), initial_vol)

        # Fullscreen Toggle (F)
        f_event = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_F, Qt.KeyboardModifier.NoModifier)
        self.player.keyPressEvent(f_event)
        app.processEvents()
        self.assertTrue(self.player.isFullScreen())

        # Escape to Exit Fullscreen
        esc_event = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Escape, Qt.KeyboardModifier.NoModifier)
        self.player.keyPressEvent(esc_event)
        app.processEvents()
        self.assertFalse(self.player.isFullScreen())

        self.player.stop()

    # -------------------------------------------------------------
    # 3. Test Playlist Auto-Advance on Track Completion
    # -------------------------------------------------------------
    def test_playlist_auto_advance(self):
        self.player.add_to_playlist(self.audio_file)
        self.player.add_to_playlist(self.video_file)

        self.player.playlist.setCurrentRow(0)
        self.player.play_file(self.audio_file)
        app.processEvents()

        # Simulate VLC State Ended on current file
        # Mock VLC player state
        original_get_state = self.player.player.get_state
        try:
            self.player.player.get_state = lambda: vlc.State.Ended
            self.player.update_position()
            app.processEvents()

            # Should have advanced to row 1 (video_file)
            self.assertEqual(self.player.playlist.currentRow(), 1)
            self.assertEqual(self.player.current_file, os.path.abspath(self.video_file))

            # Simulate Ended on last item (row 1)
            self.player.update_position()
            app.processEvents()

            # Should have stopped since it reached the end of the playlist
            self.assertEqual(self.player.play_button.text(), "Play")
        finally:
            self.player.player.get_state = original_get_state
            self.player.stop()

    # -------------------------------------------------------------
    # 4. Test Mixed File Collection Filtering
    # -------------------------------------------------------------
    def test_collect_media_paths_filtering(self):
        # Create a dummy non-media file in test_media
        dummy_txt = MEDIA_DIR / "dummy_file.txt"
        dummy_txt.write_text("not a media file")
        try:
            collected = self.player.collect_media_paths([str(dummy_txt), str(MEDIA_DIR)])
            self.assertNotIn(str(dummy_txt), collected)
            for c in collected:
                ext = os.path.splitext(c)[1].lower()
                self.assertIn(ext, self.player.MEDIA_EXTENSIONS)
        finally:
            if dummy_txt.exists():
                dummy_txt.unlink()


if __name__ == "__main__":
    unittest.main(verbosity=2)
