import argparse
import json
from collections import Counter
from pathlib import Path

from ultralytics import YOLO


BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
MODELS_DIR = BASE_DIR / "models"


def analyze_video(model, video, confidence, force=False):
    video_dir = DATA_DIR / video["id"]
    decomposition_path = video_dir / "decomposition.json"
    result_path = video_dir / "objects.json"

    if result_path.exists() and not force:
        print(f'{video["id"]}: объекты уже распознаны')
        return json.loads(result_path.read_text(encoding="utf-8"))

    if not decomposition_path.exists():
        raise FileNotFoundError("Сначала выполни декомпозицию")

    decomposition = json.loads(
        decomposition_path.read_text(encoding="utf-8")
    )
    frames = decomposition["frames"]
    detections = []

    # Обрабатываем кадры небольшими группами, чтобы не расходовать лишнюю память.
    for start in range(0, len(frames), 16):
        batch = frames[start:start + 16]
        image_paths = [
            str(BASE_DIR / frame["file"]) for frame in batch
        ]
        results = model.predict(
            source=image_paths,
            conf=confidence,
            device="cpu",
            verbose=False,
        )

        for frame, result in zip(batch, results):
            for box in result.boxes:
                class_id = int(box.cls.item())
                detections.append({
                    "time": frame["time"],
                    "frame": frame["file"],
                    "class": model.names[class_id],
                    "confidence": round(float(box.conf.item()), 4),
                    "box": [
                        round(float(value), 2)
                        for value in box.xyxy[0].tolist()
                    ],
                })

    class_counts = Counter(
        detection["class"] for detection in detections
    )
    result = {
        "id": video["id"],
        "confidence_threshold": confidence,
        "frame_count": len(frames),
        "detection_count": len(detections),
        "class_counts": dict(class_counts.most_common()),
        "detections": detections,
    }
    result_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(
        f'{video["id"]}: кадров {len(frames)}, '
        f'детекций {len(detections)}'
    )
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--confidence",
        type=float,
        default=0.35,
        help="Минимальная уверенность детектора",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Повторить распознавание заново",
    )
    args = parser.parse_args()

    collection_path = DATA_DIR / "collection.json"
    if not collection_path.exists():
        print("Сначала запусти collect.py")
        return

    collection = json.loads(collection_path.read_text(encoding="utf-8"))

    MODELS_DIR.mkdir(exist_ok=True)
    model = YOLO(str(MODELS_DIR / "yolov8n.pt"))

    summaries = []
    errors = []

    for video in collection["videos"]:
        try:
            result = analyze_video(
                model,
                video,
                confidence=args.confidence,
                force=args.force,
            )
            summaries.append({
                "id": video["id"],
                "title": video["title"],
                "detection_count": result["detection_count"],
                "class_counts": result["class_counts"],
            })
        except Exception as error:
            errors.append({"id": video["id"], "reason": str(error)})
            print(f'{video["id"]}: ошибка — {error}')

    (DATA_DIR / "vision_summary.json").write_text(
        json.dumps(
            {"videos": summaries, "errors": errors},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"Обработано: {len(summaries)}, ошибок: {len(errors)}")


if __name__ == "__main__":
    main()