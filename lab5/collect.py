import hashlib
import json
import shutil
import subprocess
from pathlib import Path

import yt_dlp


BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
SOURCES_FILE = BASE_DIR / "videos.txt"


def save_metadata(video_dir, metadata):
    video_dir.mkdir(parents=True, exist_ok=True)
    (video_dir / "meta.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def collect_video(url):
    video_options = {
        "outtmpl": str(DATA_DIR / "%(id)s" / "video.%(ext)s"),
        "format": "bv*[height<=720]+ba/b[height<=720]/b",
        "merge_output_format": "mp4",
        "noplaylist": True,
        "sleep_interval_requests": 1,
    }

    with yt_dlp.YoutubeDL(video_options) as ydl:
        info = ydl.extract_info(url, download=True)
        downloads = info.get("requested_downloads", [])

        if downloads:
            file_path = downloads[0].get("filepath")
        else:
            file_path = None

        if not file_path:
            file_path = ydl.prepare_filename(info)

    file_path = Path(file_path).resolve()
    video_dir = DATA_DIR / info["id"]

    # После объединения видео и звука расширение могло измениться.
    if not file_path.exists():
        candidates = [
            path for path in video_dir.glob("video.*")
            if path.suffix not in {".part", ".ytdl"}
        ]
        if not candidates:
            raise FileNotFoundError("Скачанный видеофайл не найден")
        file_path = candidates[0]

    metadata = {
        "id": info["id"],
        "title": info.get("title", ""),
        "description": info.get("description", ""),
        "duration": info.get("duration"),
        "uploader": info.get("uploader", ""),
        "upload_date": info.get("upload_date", ""),
        "view_count": info.get("view_count"),
        "tags": info.get("tags", []),
        "webpage_url": info.get("webpage_url", url),
        "source_type": "hosting",
        "file": str(file_path.relative_to(BASE_DIR)),
    }
    save_metadata(video_dir, metadata)
    return metadata


def collect_local(source):
    path = Path(source).expanduser()

    if not path.is_absolute():
        # Сначала ищем относительно lab5, затем относительно места запуска.
        near_script = BASE_DIR / path
        path = near_script if near_script.exists() else Path.cwd() / path

    path = path.resolve()

    if not path.is_file():
        raise FileNotFoundError(f"Локальный файл не найден: {path}")

    command = [
        "ffprobe",
        "-v", "error",
        "-show_format",
        "-show_streams",
        "-of", "json",
        str(path),
    ]
    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=True,
    )
    probe = json.loads(result.stdout)

    video_stream = next(
        (
            stream for stream in probe.get("streams", [])
            if stream.get("codec_type") == "video"
        ),
        {},
    )
    format_info = probe.get("format", {})
    duration = format_info.get("duration")

    path_hash = hashlib.sha1(
        str(path).encode("utf-8")
    ).hexdigest()[:10]
    video_id = f"local_{path_hash}"
    video_dir = DATA_DIR / video_id
    video_dir.mkdir(parents=True, exist_ok=True)

    destination = video_dir / f"video{path.suffix.lower()}"
    if path != destination.resolve():
        shutil.copy2(path, destination)

    metadata = {
        "id": video_id,
        "title": path.stem,
        "description": "",
        "duration": round(float(duration)) if duration else None,
        "uploader": "",
        "upload_date": "",
        "view_count": None,
        "tags": [],
        "webpage_url": "",
        "source_type": "local",
        "width": video_stream.get("width"),
        "height": video_stream.get("height"),
        "codec": video_stream.get("codec_name", ""),
        "file": str(destination.relative_to(BASE_DIR)),
    }
    save_metadata(video_dir, metadata)
    return metadata


def main():
    if not SOURCES_FILE.exists():
        print("Файл videos.txt не найден")
        return

    sources = [
        line.strip()
        for line in SOURCES_FILE.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    ]

    videos = []
    skipped = []

    for source in sources:
        try:
            if source.startswith(("http://", "https://")):
                metadata = collect_video(source)
            else:
                metadata = collect_local(source)

            videos.append(metadata)
            print(f'Сохранено: {metadata["id"]} | {metadata["title"]}')
        except Exception as error:
            skipped.append({"source": source, "reason": str(error)})
            print(f"Пропущено: {source}\nПричина: {error}")

    DATA_DIR.mkdir(exist_ok=True)
    result = {"videos": videos, "skipped": skipped}
    (DATA_DIR / "collection.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"Готово: {len(videos)}, пропущено: {len(skipped)}")


if __name__ == "__main__":
    main()