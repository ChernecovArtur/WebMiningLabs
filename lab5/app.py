import json
from pathlib import Path

import gradio as gr
import matplotlib
import matplotlib.pyplot as plt

matplotlib.use("Agg")


BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"

EVENT_NAMES = {
    "object": "Объект",
    "speech": "Речь",
    "volume": "Громкость",
}
EVENT_COLORS = {
    "object": "#0042db",
    "speech": "#16794c",
    "volume": "#b06000",
}


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def load_videos():
    collection = read_json(DATA_DIR / "collection.json")
    topics = read_json(DATA_DIR / "topics.json")
    clusters = {
        video["id"]: video["cluster"]
        for video in topics["videos"]
    }

    videos = {}
    for video in collection["videos"]:
        video_dir = DATA_DIR / video["id"]
        video["cluster"] = clusters[video["id"]]
        video["events"] = read_json(
            video_dir / "events.json"
        )["events"]
        video["objects"] = read_json(
            video_dir / "objects.json"
        )["class_counts"]
        video["transcript"] = read_json(
            video_dir / "speech.json"
        )["transcript"]
        videos[video["id"]] = video

    return videos


VIDEOS = load_videos()


def format_time(seconds):
    minutes = int(seconds // 60)
    remaining_seconds = int(seconds % 60)
    return f"{minutes:02d}:{remaining_seconds:02d}"


def event_description(event):
    if event["type"] == "speech":
        return event.get("text", "")
    if event["type"] == "volume":
        return f'Громкий звук, RMS {event.get("max_rms", 0):.3f}'
    return event["label"]


def get_event_rows(video):
    return [
        [
            format_time(event["start"]),
            format_time(event["end"]),
            EVENT_NAMES[event["type"]],
            event_description(event),
        ]
        for event in video["events"]
    ]


def get_object_rows(video):
    return [
        [class_name, count]
        for class_name, count in video["objects"].items()
    ]


def make_timeline(video):
    figure, axis = plt.subplots(figsize=(10, 2.6))
    positions = {"object": 2, "speech": 1, "volume": 0}

    for event in video["events"]:
        event_type = event["type"]
        axis.hlines(
            positions[event_type],
            event["start"],
            max(event["end"], event["start"] + 0.2),
            color=EVENT_COLORS[event_type],
            alpha=0.65,
            linewidth=4,
        )

    axis.set_yticks(
        [2, 1, 0],
        ["Объекты", "Речь", "Громкость"],
    )
    axis.set_xlabel("Время, секунды")
    axis.set_xlim(0, max(video.get("duration") or 1, 1))
    axis.grid(axis="x", alpha=0.2)
    axis.spines[["top", "right", "left"]].set_visible(False)
    figure.tight_layout()
    return figure


def video_result(video_id, start=0):
    video = VIDEOS[video_id]
    video_path = BASE_DIR / video["file"]

    player = gr.Video(
        value=str(video_path),
        playback_position=start,
        autoplay=start > 0,
        interactive=False,
        label=video["title"],
    )
    info = (
        f"### {video['title']}\n\n"
        f"**Тематический кластер:** {video['cluster']}\n\n"
        f"**Длительность:** {format_time(video.get('duration') or 0)}\n\n"
        f"**Событий:** {len(video['events'])}"
    )
    return (
        player,
        info,
        make_timeline(video),
        get_event_rows(video),
        get_object_rows(video),
        video["transcript"],
    )


def get_row_index(select_data):
    index = select_data.index
    return index[0] if isinstance(index, (tuple, list)) else index


def seek_event(video_id, select_data: gr.SelectData):
    video = VIDEOS[video_id]
    event = video["events"][get_row_index(select_data)]
    return gr.Video(
        value=str(BASE_DIR / video["file"]),
        playback_position=event["start"],
        autoplay=True,
        interactive=False,
    )


def search_events(query):
    query = query.strip().lower()
    if len(query) < 2:
        return [], []

    rows = []
    hits = []

    for video in VIDEOS.values():
        for event in video["events"]:
            searchable_text = " ".join([
                event.get("label", ""),
                event.get("text", ""),
            ]).lower()

            if query not in searchable_text:
                continue

            description = event_description(event)
            rows.append([
                video["title"],
                format_time(event["start"]),
                EVENT_NAMES[event["type"]],
                description,
            ])
            hits.append({
                "video_id": video["id"],
                "start": event["start"],
            })

    return rows, hits


def seek_search_result(hits, select_data: gr.SelectData):
    hit = hits[get_row_index(select_data)]
    return (
        *video_result(hit["video_id"], hit["start"]),
        gr.Dropdown(value=hit["video_id"]),
    )


def main():
    first_id = next(iter(VIDEOS))
    choices = [
        (video["title"], video_id)
        for video_id, video in VIDEOS.items()
    ]

    with gr.Blocks(
        title="Анализ видео",
        theme=gr.themes.Default(
            primary_hue="blue",
            neutral_hue="slate",
        ),
        css=".gradio-container {max-width: 1500px;}",
    ) as demo:
        gr.Markdown(
            "# Анализ видеоданных\n"
            "Поиск по объектам и речи, тематические группы и события."
        )

        with gr.Row():
            with gr.Column(scale=7):
                video_dropdown = gr.Dropdown(
                    choices=choices,
                    value=first_id,
                    label="Ролик",
                )
                player = gr.Video(
                    interactive=False,
                    label="Видео",
                )
                timeline = gr.Plot(
                    label="Временная шкала"
                )
                events_table = gr.Dataframe(
                    headers=["Начало", "Конец", "Тип", "Событие"],
                    interactive=False,
                    label="Нажми на строку, чтобы перейти к событию",
                )

            with gr.Column(scale=3):
                video_info = gr.Markdown()
                search_query = gr.Textbox(
                    label="Поиск по всем роликам",
                    placeholder="Например: курица, трактор или person",
                )
                search_button = gr.Button("Найти")
                search_table = gr.Dataframe(
                    headers=["Ролик", "Время", "Тип", "Результат"],
                    interactive=False,
                    label="Результаты поиска",
                )
                search_state = gr.State([])

        with gr.Row():
            transcript = gr.Textbox(
                label="Транскрипт",
                lines=8,
                interactive=False,
            )
            objects_table = gr.Dataframe(
                headers=["Объект", "Детекций"],
                interactive=False,
                label="Статистика объектов",
            )

        video_outputs = [
            player,
            video_info,
            timeline,
            events_table,
            objects_table,
            transcript,
        ]

        video_dropdown.change(
            lambda video_id: video_result(video_id),
            inputs=video_dropdown,
            outputs=video_outputs,
        )
        events_table.select(
            seek_event,
            inputs=video_dropdown,
            outputs=player,
        )
        search_button.click(
            search_events,
            inputs=search_query,
            outputs=[search_table, search_state],
        )
        search_query.submit(
            search_events,
            inputs=search_query,
            outputs=[search_table, search_state],
        )
        search_table.select(
            seek_search_result,
            inputs=search_state,
            outputs=[*video_outputs, video_dropdown],
        )
        demo.load(
            lambda: video_result(first_id),
            outputs=video_outputs,
        )

    demo.launch(
        inbrowser=True,
        allowed_paths=[str(DATA_DIR)],
    )


if __name__ == "__main__":
    main()