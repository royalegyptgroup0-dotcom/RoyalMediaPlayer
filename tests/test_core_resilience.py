"""Focused regression tests for core behavior that does not require VLC.

These tests deliberately run without a VLC installation so basic UI behavior,
path handling, and failure cleanup remain verifiable on clean machines.
"""
import os
import sys
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

BASE_DIR = Path(__file__).resolve().parent.parent
DEV_DIR = BASE_DIR / "development"
sys.path.insert(0, str(DEV_DIR))

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication
import RoyalMediaPlayer as player_module
from RoyalMediaPlayer import RoyalMediaPlayer, format_time


app = QApplication.instance() or QApplication(sys.argv)


class TestCoreResilience(unittest.TestCase):
    def setUp(self):
        self.original_vlc = player_module.vlc
        player_module.vlc = None
        self.window = RoyalMediaPlayer()
        self.window.show()
        app.processEvents()

    def tearDown(self):
        if self.window is not None:
            self.window.close()
            app.processEvents()
        player_module.vlc = self.original_vlc

    def test_format_time_boundaries(self):
        self.assertEqual(format_time(None), "00:00")
        self.assertEqual(format_time(-1), "00:00")
        self.assertEqual(format_time(59_999), "00:59")
        self.assertEqual(format_time(60_000), "01:00")
        self.assertEqual(format_time(3_600_000), "01:00:00")
        self.assertEqual(format_time(86_400_000), "24:00:00")

    def test_collect_media_paths_filters_and_deduplicates(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            nested = root / "nested"
            nested.mkdir()
            media_a = root / "first.MP3"
            media_b = nested / "second.mp4"
            ignored = root / "notes.txt"
            media_a.write_bytes(b"audio placeholder")
            media_b.write_bytes(b"video placeholder")
            ignored.write_text("not media", encoding="utf-8")

            paths = self.window.collect_media_paths([
                str(root),
                str(media_a),
                str(ignored),
            ])

            normalized = {os.path.normcase(os.path.abspath(path)) for path in paths}
            self.assertEqual(len(paths), 2)
            self.assertEqual(
                normalized,
                {
                    os.path.normcase(os.path.abspath(str(media_a))),
                    os.path.normcase(os.path.abspath(str(media_b))),
                },
            )

    def test_playlist_rejects_duplicate_normalized_path(self):
        with tempfile.TemporaryDirectory() as temporary:
            media = Path(temporary) / "track.wav"
            media.write_bytes(b"placeholder")

            self.assertTrue(self.window.add_to_playlist(str(media)))
            self.assertFalse(self.window.add_to_playlist(str(media.parent / "." / media.name)))
            self.assertEqual(self.window.playlist.count(), 1)
            self.assertEqual(
                os.path.normcase(self.window.playlist.item(0).data(Qt.ItemDataRole.UserRole)),
                os.path.normcase(os.path.abspath(str(media))),
            )

    def test_unavailable_backend_fails_gracefully(self):
        self.assertFalse(self.window._vlc_available)
        self.assertFalse(self.window.play_button.isEnabled())
        self.assertEqual(self.window.play_button.text(), "Play")

        result = self.window.play_file("missing-file.mp4")

        self.assertFalse(result)
        self.assertIsNone(self.window.current_file)
        self.assertIsNone(self.window.current_media)
        self.assertEqual(self.window.play_button.text(), "Play")
        self.assertIn("Unable to play", self.window.video_label.text())

    def test_failure_cleanup_continues_when_stop_raises(self):
        class FakeMedia:
            released = False

            def release(self):
                self.released = True

        class FakePlayer:
            def stop(self):
                raise RuntimeError("simulated stop failure")

            def set_media(self, media):
                self.detached = media is None

            def release(self):
                pass

        media = FakeMedia()
        self.window.current_media = media
        self.window.player = FakePlayer()

        self.window._handle_playback_failure("failed.mp4", "simulated failure")

        self.assertTrue(self.window.player.detached)
        self.assertTrue(media.released)
        self.assertIsNone(self.window.current_media)

    def test_media_is_retained_until_player_release_if_detach_fails(self):
        class FakePlayer:
            released = False

            def stop(self):
                pass

            def set_media(self, media):
                if media is None:
                    raise RuntimeError("simulated detach failure")

            def release(self):
                self.released = True

        class FakeMedia:
            released = False

            def release(self):
                if not player.released:
                    raise AssertionError("media released while player still owns it")
                self.released = True

        player = FakePlayer()
        media = FakeMedia()
        self.window.player = player
        self.window.current_media = media

        self.window._handle_playback_failure("failed.mp4", "simulated failure")

        self.assertIs(self.window.current_media, media)
        self.assertFalse(media.released)

        # Shutdown releases the player first, then safely retries media release.
        self.window.close()
        app.processEvents()
        self.assertTrue(player.released)
        self.assertTrue(media.released)
        self.assertIsNone(self.window.current_media)
        self.window = None

    def test_new_media_is_released_when_backend_rejects_it(self):
        with tempfile.TemporaryDirectory() as temporary:
            media_path = Path(temporary) / "rejected.mp4"
            media_path.write_bytes(b"placeholder")

            class FakeMedia:
                released = False

                def release(self):
                    self.released = True

            class FakeInstance:
                def __init__(self):
                    self.media = FakeMedia()

                def media_new(self, _path):
                    return self.media

                def release(self):
                    pass

            class RejectingPlayer:
                def stop(self):
                    pass

                def release(self):
                    pass

                def set_media(self, media):
                    if media is not None:
                        raise RuntimeError("simulated set_media failure")

            fake_instance = FakeInstance()
            self.window.instance = fake_instance
            self.window.player = RejectingPlayer()
            self.window._vlc_available = True

            result = self.window.play_file(str(media_path))

            self.assertFalse(result)
            self.assertTrue(fake_instance.media.released)
            self.assertIsNone(self.window.current_file)
            self.assertIsNone(self.window.current_media)
            self.assertEqual(self.window.play_button.text(), "Play")


if __name__ == "__main__":
    unittest.main(verbosity=2)
