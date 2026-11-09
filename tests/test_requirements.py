import os
import sys
import time
import unittest
from pathlib import Path

# Headless platform for automated verification
os.environ["QT_QPA_PLATFORM"] = "offscreen"

BASE_DIR = Path(__file__).resolve().parent.parent
DEV_DIR = BASE_DIR / "development"
MEDIA_DIR = BASE_DIR / "test_media"
sys.path.insert(0, str(DEV_DIR))

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt, QUrl, QMimeData, QPoint
from PySide6.QtGui import QKeyEvent

import vlc
import RoyalMediaPlayer as rmp
from RoyalMediaPlayer import RoyalMediaPlayer, find_vlc_directory, format_time


app = QApplication.instance() or QApplication(sys.argv)


class TestRequirements(unittest.TestCase):

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
    # Req 1: Media Lifecycle & Safe Resource Release
    # -------------------------------------------------------------
    def test_01_media_lifecycle_safe_release(self):
        # Play first file
        self.player.play_file(self.audio_file)
        first_media = self.player.current_media
        self.assertIsNotNone(first_media)

        # Play second file: verify first_media is replaced and current_media is new
        self.player.play_file(self.video_file)
        second_media = self.player.current_media
        self.assertIsNotNone(second_media)
        self.assertNotEqual(first_media, second_media)

        # Stop player: current_media retained until new media or close
        self.player.stop()
        self.assertEqual(self.player.play_button.text(), "Play")

    # -------------------------------------------------------------
    # Req 2: Play Failure Cleans Stale Metadata
    # -------------------------------------------------------------
    def test_02_play_failure_clears_stale_info(self):
        # First play a valid audio file
        self.player.play_file(self.audio_file)
        self.assertIn("sample_audio.mp3", self.player.video_label.text())

        # Now attempt to play an invalid / non-existent file
        fake_file = "C:/non_existent_folder/fake_media.mp4"
        success = self.player.play_file(fake_file)
        self.assertFalse(success)

        # Verify stale metadata is wiped out
        self.assertIsNone(self.player.current_file)
        self.assertIsNone(self.player.current_media)
        self.assertEqual(self.player.time_label.text(), "00:00 / 00:00")
        self.assertEqual(self.player.position_slider.value(), 0)
        self.assertEqual(self.player.play_button.text(), "Play")
        self.assertIn("Unable to play", self.player.video_label.text())
        self.assertIn("fake_media.mp4", self.player.video_label.text())

    # -------------------------------------------------------------
    # Req 3: current_file matches playlist selection always
    # -------------------------------------------------------------
    def test_03_playlist_selection_matches_current_file(self):
        # Add multiple files
        self.player.add_to_playlist(self.audio_file)
        self.player.add_to_playlist(self.audio2_file)
        self.player.add_to_playlist(self.video_file)
        self.player.add_to_playlist(self.video2_file)

        # Directly play 3rd file (index 2)
        self.player.play_file(self.video_file)
        app.processEvents()

        # Check playlist selection is row 2
        self.assertEqual(self.player.playlist.currentRow(), 2)
        current_item = self.player.playlist.currentItem()
        self.assertEqual(
            os.path.normcase(current_item.data(Qt.ItemDataRole.UserRole)),
            os.path.normcase(os.path.abspath(self.video_file)),
        )

        # Play 1st file (index 0)
        self.player.play_file(self.audio_file)
        app.processEvents()
        self.assertEqual(self.player.playlist.currentRow(), 0)

    # -------------------------------------------------------------
    # Req 4: Auto-advance skips missing / unplayable files
    # -------------------------------------------------------------
    def test_04_skip_missing_files_in_next_and_previous(self):
        missing_file1 = "C:/test_missing/ghost1.mp4"
        missing_file2 = "C:/test_missing/ghost2.mp4"

        # Construct playlist: audio_file (row 0), missing1 (row 1), missing2 (row 2), video_file (row 3)
        self.player.playlist.addItem("sample_audio.mp3")
        self.player.playlist.item(0).setData(Qt.ItemDataRole.UserRole, self.audio_file)

        self.player.playlist.addItem("ghost1.mp4")
        self.player.playlist.item(1).setData(Qt.ItemDataRole.UserRole, missing_file1)

        self.player.playlist.addItem("ghost2.mp4")
        self.player.playlist.item(2).setData(Qt.ItemDataRole.UserRole, missing_file2)

        self.player.playlist.addItem("sample_video.mp4")
        self.player.playlist.item(3).setData(Qt.ItemDataRole.UserRole, self.video_file)

        # Start on row 0
        self.player.playlist.setCurrentRow(0)
        self.player.play_file(self.audio_file)

        # Call next(): should skip ghost1 and ghost2, and land on row 3 (video_file)
        advanced = self.player.next()
        app.processEvents()
        self.assertTrue(advanced)
        self.assertEqual(self.player.playlist.currentRow(), 3)
        self.assertEqual(self.player.current_file, os.path.abspath(self.video_file))

        # Call previous(): should skip backward past ghost2 and ghost1, landing on row 0
        went_back = self.player.previous()
        app.processEvents()
        self.assertTrue(went_back)
        self.assertEqual(self.player.playlist.currentRow(), 0)
        self.assertEqual(self.player.current_file, os.path.abspath(self.audio_file))

    # -------------------------------------------------------------
    # Req 5: Fault-Tolerant closeEvent Cleanup Steps
    # -------------------------------------------------------------
    def test_05_close_event_fault_tolerance(self):
        self.player.play_file(self.audio_file)
        app.processEvents()

        # Monkey-patch timer.stop to simulate an unexpected crash/exception
        def broken_stop():
            raise RuntimeError("Simulated timer stop failure")

        self.player.timer.stop = broken_stop

        # Trigger closeEvent
        self.player.close()
        app.processEvents()

        # All subsequent cleanup steps should STILL have executed
        self.assertTrue(self.player._closing)
        self.assertIsNone(self.player.player)
        self.assertIsNone(self.player.instance)
        self.assertIsNone(self.player.current_media)

    # -------------------------------------------------------------
    # Req 6: VLC Initialization Verification & Fallback UI
    # -------------------------------------------------------------
    def test_06_vlc_verification(self):
        self.assertTrue(self.player._vlc_available)
        self.assertIsNotNone(self.player.instance)
        self.assertIsNotNone(self.player.player)

    # -------------------------------------------------------------
    # Req 7: os.add_dll_directory Handle Retention
    # -------------------------------------------------------------
    def test_07_dll_directory_handle_retention(self):
        if sys.platform.startswith("win") and hasattr(os, "add_dll_directory"):
            # Handle must be retained at module level
            self.assertIsNotNone(rmp._VLC_DLL_DIRECTORY_HANDLE)

    # -------------------------------------------------------------
    # Req 8: Dynamic VLC Discovery
    # -------------------------------------------------------------
    def test_08_dynamic_vlc_discovery(self):
        discovered_path = find_vlc_directory()
        self.assertIsNotNone(discovered_path)
        self.assertTrue(os.path.isdir(discovered_path))
        self.assertTrue(os.path.isfile(os.path.join(discovered_path, "libvlc.dll")))

    # -------------------------------------------------------------
    # Req 9: Extended Keyboard Shortcuts (N, P, S, etc.)
    # -------------------------------------------------------------
    def test_09_extended_keyboard_shortcuts(self):
        self.player.add_to_playlist(self.audio_file)
        self.player.add_to_playlist(self.video_file)
        self.player.playlist.setCurrentRow(0)
        self.player.play_file(self.audio_file)

        # N: Next
        n_event = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_N, Qt.KeyboardModifier.NoModifier)
        self.player.keyPressEvent(n_event)
        app.processEvents()
        self.assertEqual(self.player.playlist.currentRow(), 1)

        # P: Previous
        p_event = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_P, Qt.KeyboardModifier.NoModifier)
        self.player.keyPressEvent(p_event)
        app.processEvents()
        self.assertEqual(self.player.playlist.currentRow(), 0)

        # S: Stop
        s_event = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_S, Qt.KeyboardModifier.NoModifier)
        self.player.keyPressEvent(s_event)
        app.processEvents()
        self.assertEqual(self.player.play_button.text(), "Play")

    # -------------------------------------------------------------
    # Req 10: Error Path Resilience
    # -------------------------------------------------------------
    def test_10_error_path_resilience(self):
        # Empty/None seek
        self.player.seek(500)
        # Volume clamp below 0 and above 100
        self.player.change_volume(-50)
        self.assertEqual(self.player.volume_label.text(), "Volume 0%")
        self.player.change_volume(200)
        self.assertEqual(self.player.volume_label.text(), "Volume 100%")
        # format_time with negative and extreme values
        self.assertEqual(format_time(-1000), "00:00")
        self.assertEqual(format_time(None), "00:00")
        self.assertEqual(format_time(0), "00:00")


    # -------------------------------------------------------------
    # Req 11: Asynchronous VLC Error Auto-Advance
    # -------------------------------------------------------------
    def test_11_async_vlc_error_advances_once(self):
        self.player.add_to_playlist(self.audio_file)
        self.player.add_to_playlist(self.video_file)
        self.player.playlist.setCurrentRow(0)
        self.assertTrue(self.player.play_file(self.audio_file))

        # Simulate VLC reporting a decode/open failure after play() succeeded.
        self.player.player.get_state = lambda: vlc.State.Error
        self.player.update_position()

        self.assertEqual(self.player.playlist.currentRow(), 1)
        self.assertEqual(self.player.current_file, os.path.abspath(self.video_file))

        # Once the next file is active, a non-error state must not skip again.
        self.player.player.get_state = lambda: vlc.State.Playing
        self.player.update_position()
        self.assertEqual(self.player.playlist.currentRow(), 1)

    # -------------------------------------------------------------
    # Req 12: Consecutive Asynchronous VLC Errors
    # -------------------------------------------------------------
    def test_12_consecutive_async_errors_stop_cleanly(self):
        self.player.add_to_playlist(self.audio_file)
        self.player.add_to_playlist(self.audio2_file)
        self.player.add_to_playlist(self.video_file)
        self.player.playlist.setCurrentRow(0)
        self.assertTrue(self.player.play_file(self.audio_file))

        # Simulate each attempted file failing asynchronously.
        self.player.player.get_state = lambda: vlc.State.Error
        self.player.update_position()
        self.assertEqual(self.player.playlist.currentRow(), 1)

        self.player.update_position()
        self.assertEqual(self.player.playlist.currentRow(), 2)

        self.player.update_position()
        self.assertEqual(self.player.play_button.text(), "Play")
        self.assertIn("No more playable files", self.player.video_label.text())


if __name__ == "__main__":
    unittest.main(verbosity=2)
