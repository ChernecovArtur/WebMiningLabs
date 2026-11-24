import json
from pathlib import Path

import yt_dlp


BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
SOURCES_FILE = BASE_DIR / "videos.txt"


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
        file_path = None

        downloads = info.get("requested_downloads", [])
        if downloads:
            file_path = downloads[0].get("filepath")

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
        "file": str(file_path.relative_to(BASE_DIR)),
    }

    metadata_path = video_dir / "meta.json"
    metadata_path.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
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
            metadata = collect_video(source)
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