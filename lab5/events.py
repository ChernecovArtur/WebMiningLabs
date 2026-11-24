import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path


BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"


def build_object_events(objects, fps):
    grouped = defaultdict(list)

    for detection in objects["detections"]:
        grouped[detection["class"]].append(detection)

    events = []
    frame_step = 1 / fps if fps else 1.0
    allowed_gap = frame_step * 1.5

    for class_name, detections in grouped.items():
        detections.sort(key=lambda item: item["time"])
        current = []

        for detection in detections:
            if current:
                gap = detection["time"] - current[-1]["time"]
                if gap > allowed_gap:
                    events.append(make_object_event(
                        class_name, current, frame_step
                    ))
                    current = []

            current.append(detection)

        if current:
            events.append(make_object_event(
                class_name, current, frame_step
            ))

    return events


def make_object_event(class_name, detections, frame_step):
    confidence = sum(
        item["confidence"] for item in detections
    ) / len(detections)

    return {
        "type": "object",
        "label": class_name,
        "start": detections[0]["time"],
        "end": round(detections[-1]["time"] + frame_step, 3),
        "confidence": round(confidence, 4),
        "frame_count": len(detections),
    }


def build_speech_events(speech):
    return [
        {
            "type": "speech",
            "label": "Речь",
            "start": segment["start"],
            "end": segment["end"],
            "text": segment["text"],
        }
        for segment in speech["segments"]
    ]


def build_volume_events(speech):
    threshold = speech.get("volume_threshold")
    if threshold is None:
        return []

    loud_windows = [
        window for window in speech["volume_windows"]
        if window["rms"] > threshold
    ]

    events = []
    current = []

    for window in loud_windows:
        if current:
            previous_end = current[-1]["end"]
            if window["start"] - previous_end > 0.01:
                events.append(make_volume_event(current))
                current = []

        current.append(window)

    if current:
        events.append(make_volume_event(current))

    return events


def make_volume_event(windows):
    return {
        "type": "volume",
        "label": "Громкий звук",
        "start": windows[0]["start"],
        "end": windows[-1]["end"],
        "max_rms": max(window["rms"] for window in windows),
    }


def build_events(video, force=False):
    video_dir = DATA_DIR / video["id"]
    result_path = video_dir / "events.json"

    if result_path.exists() and not force:
        print(f'{video["id"]}: события уже построены')
        return

    objects_path = video_dir / "objects.json"
    speech_path = video_dir / "speech.json"
    decomposition_path = video_dir / "decomposition.json"

    objects = json.loads(objects_path.read_text(encoding="utf-8"))
    speech = json.loads(speech_path.read_text(encoding="utf-8"))
    decomposition = json.loads(
        decomposition_path.read_text(encoding="utf-8")
    )

    events = []
    events.extend(build_object_events(
        objects,
        decomposition["fps"],
    ))
    events.extend(build_speech_events(speech))
    events.extend(build_volume_events(speech))
    events.sort(key=lambda event: (event["start"], event["type"]))

    counts = Counter(event["type"] for event in events)
    result = {
        "id": video["id"],
        "event_count": len(events),
        "event_counts": dict(counts),
        "events": events,
    }
    result_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f'{video["id"]}: событий {len(events)} — {dict(counts)}')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    collection_path = DATA_DIR / "collection.json"
    collection = json.loads(collection_path.read_text(encoding="utf-8"))

    processed = 0
    for video in collection["videos"]:
        try:
            build_events(video, force=args.force)
            processed += 1
        except FileNotFoundError:
            print(f'{video["id"]}: не хватает результатов анализа')
        except Exception as error:
            print(f'{video["id"]}: ошибка — {error}')

    print(f"Обработано: {processed}")


if __name__ == "__main__":
    main()