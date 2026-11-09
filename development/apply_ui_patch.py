from pathlib import Path
import re

path = Path.home() / "RoyalMediaPlayer" / "development" / "RoyalMediaPlayer.py"
source = path.read_text(encoding="utf-8-sig")

replacements = {
    '"ðŸ“‚ Open"': '"Open"',
    '"â®"': '"Previous"',
    '"â–¶"': '"Play"',
    '"â¹"': '"Stop"',
    '"â­"': '"Next"',
    '"â›¶"': '"Fullscreen"',
    '"ðŸ”Š"': '"Volume"',
    '"â¸"': '"Pause"',
}

for old, new in replacements.items():
    count = source.count(old)
    if count:
        source = source.replace(old, new)
        print(f"REPLACED {count}: {old} -> {new}")

pattern = (
    r'file_path, _ = QFileDialog\.getOpenFileName\('
    r'\s*self,\s*"Open Media",\s*"",\s*""".*?"""\s*\)'
)

replacement = '''file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Open Media",
            "",
            "Media Files (*.mp4 *.mkv *.avi *.mov *.wmv *.webm *.mp3 *.wav *.flac *.aac *.ogg *.m4a);;All Files (*)"
        )'''

source, count = re.subn(pattern, replacement, source, count=1, flags=re.S)

if count != 1:
    raise RuntimeError("File dialog filter was not matched. No changes saved.")

path.write_text(source, encoding="utf-8", newline="\n")
print("UI PATCH APPLIED")
