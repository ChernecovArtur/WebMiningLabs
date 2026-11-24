import argparse
import json
import subprocess
from pathlib import Path


BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"


def run_ffmpeg(arguments):
    subprocess.run(
        ["ffmpeg", "-loglevel", "error", "-y", *arguments],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=True,
    )


def decompose_video(video, force=False):
    video_dir = DATA_DIR / video["id"]
    result_path = video_dir / "decomposition.json"

    if result_path.exists() and not force:
        print(f'{video["id"]}: декомпозиция уже выполнена')
        return

    video_path = BASE_DIR / video["file"]
    frames_dir = video_dir / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)

    duration = video.get("duration") or 0

    # На длинных роликах уменьшаем частоту, чтобы не получать лишние кадры.
    fps = min(1.0, max(0.1, 240 / duration)) if duration else 1.0

    run_ffmpeg([
        "-i", str(video_path),
        "-vf", f"fps={fps:.6f}",
        "-q:v", "2",
        str(frames_dir / "frame_%05d.jpg"),
    ])

    frames = []
    for index, frame_path in enumerate(sorted(frames_dir.glob("frame_*.jpg"))):
        frames.append({
            "time": round(index / fps, 3),
            "file": str(frame_path.relative_to(BASE_DIR)),
        })

    audio_path = video_dir / "audio.wav"
    audio_error = ""

    try:
        run_ffmpeg([
            "-i", str(video_path),
            "-vn",
            "-ac", "1",
            "-ar", "16000",
            str(audio_path),
        ])
    except subprocess.CalledProcessError as error:
        audio_path = None
        audio_error = error.stderr.strip()

    result = {
        "id": video["id"],
        "fps": round(fps, 6),
        "frames": frames,
        "audio": (
            str(audio_path.relative_to(BASE_DIR)) if audio_path else None
        ),
        "audio_error": audio_error,
    }
    result_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(
        f'{video["id"]}: кадров {len(frames)}, '
        f'FPS {fps:.2f}, аудио {"есть" if audio_path else "нет"}'
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--force",
        action="store_true",
        help="Повторить декомпозицию заново",
    )
    args = parser.parse_args()

    collection_path = DATA_DIR / "collection.json"
    if not collection_path.exists():
        print("Сначала запусти collect.py")
        return

    collection = json.loads(collection_path.read_text(encoding="utf-8"))
    errors = []

    for video in collection["videos"]:
        try:
            decompose_video(video, force=args.force)
        except Exception as error:
            errors.append({"id": video["id"], "reason": str(error)})
            print(f'{video["id"]}: ошибка — {error}')

    print(
        f'Обработано: {len(collection["videos"]) - len(errors)}, '
        f'ошибок: {len(errors)}'
    )


if __name__ == "__main__":
    main()