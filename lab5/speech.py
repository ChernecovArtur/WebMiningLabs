import argparse
import json
import wave
from pathlib import Path

import numpy as np
from faster_whisper import WhisperModel


BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"


def read_audio(audio_path):
    with wave.open(str(audio_path), "rb") as audio_file:
        sample_rate = audio_file.getframerate()
        sample_width = audio_file.getsampwidth()
        channels = audio_file.getnchannels()
        samples = audio_file.readframes(audio_file.getnframes())

    if sample_width != 2 or channels != 1:
        raise ValueError("Нужен монофонический WAV с 16-битными отсчётами")

    audio = np.frombuffer(samples, dtype=np.int16)
    return audio.astype(np.float32) / 32768.0, sample_rate


def analyze_volume(audio, sample_rate, window_seconds=1.0):
    window_size = int(sample_rate * window_seconds)
    windows = []

    for start_sample in range(0, len(audio), window_size):
        part = audio[start_sample:start_sample + window_size]
        if len(part) == 0:
            continue

        rms = float(np.sqrt(np.mean(part ** 2)))
        start = start_sample / sample_rate
        windows.append({
            "start": round(start, 3),
            "end": round(start + len(part) / sample_rate, 3),
            "rms": round(rms, 6),
        })

    values = np.array([window["rms"] for window in windows])

    if len(values):
        # Порог подстраивается под громкость конкретного ролика.
        threshold = max(
            float(values.mean() + values.std()),
            0.02,
        )
    else:
        threshold = 0.02

    return windows, round(threshold, 6)


def analyze_speech(model, video, language, force=False):
    video_dir = DATA_DIR / video["id"]
    decomposition_path = video_dir / "decomposition.json"
    result_path = video_dir / "speech.json"

    if result_path.exists() and not force:
        print(f'{video["id"]}: речь уже проанализирована')
        return json.loads(result_path.read_text(encoding="utf-8"))

    decomposition = json.loads(
        decomposition_path.read_text(encoding="utf-8")
    )

    if not decomposition.get("audio"):
        result = {
            "id": video["id"],
            "segments": [],
            "transcript": "",
            "volume_windows": [],
            "volume_threshold": None,
            "warning": "Аудиодорожка отсутствует",
        }
    else:
        audio_path = BASE_DIR / decomposition["audio"]
        audio, sample_rate = read_audio(audio_path)
        volume_windows, threshold = analyze_volume(audio, sample_rate)

        segments_iterator, info = model.transcribe(
            audio,
            language=language,
            beam_size=5,
            vad_filter=True,
            condition_on_previous_text=False,
        )

        segments = []
        for segment in segments_iterator:
            text = segment.text.strip()
            if text:
                segments.append({
                    "start": round(segment.start, 3),
                    "end": round(segment.end, 3),
                    "text": text,
                })

        transcript = " ".join(
            segment["text"] for segment in segments
        )
        warning = "" if transcript else "Речь не распознана"

        result = {
            "id": video["id"],
            "language": info.language,
            "segments": segments,
            "transcript": transcript,
            "volume_windows": volume_windows,
            "volume_threshold": threshold,
            "warning": warning,
        }

    result_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (video_dir / "transcript.txt").write_text(
        result["transcript"],
        encoding="utf-8",
    )

    loud_windows = sum(
        window["rms"] > (result["volume_threshold"] or 1)
        for window in result["volume_windows"]
    )
    print(
        f'{video["id"]}: сегментов речи {len(result["segments"])}, '
        f'громких окон {loud_windows}'
        + (f' — {result["warning"]}' if result["warning"] else "")
    )
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="base")
    parser.add_argument("--language", default="ru")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    collection_path = DATA_DIR / "collection.json"
    if not collection_path.exists():
        print("Сначала запусти collect.py")
        return

    collection = json.loads(collection_path.read_text(encoding="utf-8"))
    model = WhisperModel(
        args.model,
        device="cpu",
        compute_type="int8",
    )

    processed = 0
    errors = []

    for video in collection["videos"]:
        try:
            analyze_speech(
                model,
                video,
                language=args.language,
                force=args.force,
            )
            processed += 1
        except Exception as error:
            errors.append({"id": video["id"], "reason": str(error)})
            print(f'{video["id"]}: ошибка — {error}')

    print(f"Обработано: {processed}, ошибок: {len(errors)}")


if __name__ == "__main__":
    main()