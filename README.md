# RoyalMediaPlayer

A modern, robust media player built with **PySide6 (Qt 6)** and **python-vlc (libvlc 3.x)** for high-performance audio and video playback on Windows.

## Repository Overview

- `RoyalMediaPlayer.py`: Original root file (Read-Only baseline).
- `development/RoyalMediaPlayer.py`: Fully repaired, hardened, and verified development code.
- `tests/`: Automated test suites covering Qt, VLC, audio/video playback, playlist management, drag & drop, and graceful shutdown.
- `test_media/`: Sample media files generated for reproducible testing.
- `backups/`: Historical safety backups with SHA256 verification logs.

---

## Technical Highlights & Features

1. **Robust VLC Engine & Media Lifecycle**:
   - Safe asynchronous media transition (sets new media before releasing previous media).
   - Dynamic VLC installation discovery (Windows Registry, Environment variables, standard directories).
   - Long-lived `os.add_dll_directory` handle protection against Python garbage collection.
2. **Audio & Video Presentation**:
   - Full video embedding via native Windows window handle (`set_hwnd`).
   - Dynamic track feedback (`🎵 Now Playing: <filename>`) for audio-only files.
   - Synchronized digital timer display (`MM:SS / MM:SS`).
3. **Smooth Seek & Volume Control**:
   - Non-fighting slider: ignores timer position updates while user is actively dragging (`isSliderDown()`).
   - Seeking executed smoothly on slider release (`sliderReleased`).
4. **Smart Playlist Management & Drag-and-Drop**:
   - `QEvent.Type.DragMove` handled alongside `DragEnter` and `Drop` across all widgets.
   - Auto-advance on track completion with automatic skipping of missing/corrupt files.
   - 1:1 synchronization between current playing file and selected playlist item.
5. **Fault-Tolerant Clean Exit**:
   - Isolated cleanup steps (`timer.stop()`, `player.set_hwnd(0)`, `player.stop()`, `media.release()`, `player.release()`, `instance.release()`).

---

## Running the Automated Test Suites

```bash
# Run all 22 automated tests
python -m unittest discover -s tests -p "test_*.py" -v
```

---

## Verification Hashes (SHA256)

| Target | File Path | SHA256 Hash |
| :--- | :--- | :--- |
| **Original Root** | `RoyalMediaPlayer.py` | `2B2B1F5B31E6AB8DC9A2C318141562C457DD143C5DF522DF0590B54DE7568325` |
| **Development** | `development/RoyalMediaPlayer.py` | `BC61D3954BAF661729544589388BFFEBEAB226B79A9AE8579C9804933AE930AC` |

---

## License & Credits

Developed for the Royal Media Player Project by Royal Egypt Group.
