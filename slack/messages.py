from typing import IO, Optional
import base64
import os
import requests

from io import BytesIO
from slack_bolt import App
from slack_sdk.web.client import WebClient

BOT_USER_ID = "U04BDAUG6PQ"


def send_message_with_metadata(
    client: WebClient,
    channel: str,
    text: str,
    event_type: str = None,
    event_fields: dict[str] = None,
    thread_ts: str = None,
):
    """
    Send a message to a Slack channel with metadata.
    Args:
        client (WebClient): The Slack WebClient instance.
        channel (str): The channel ID.
        text (str): The message text.
        event_type (str): The type of event.
        event_fields (dict[str], optional): Additional metadata fields.
        thread_ts (str, optional): Timestamp of the thread to reply to.
    """
    if event_type is None:
        metadata = None
    else:
        metadata = {"event_type": event_type, "event_payload": event_fields or {}}

    return client.chat_postMessage(
        channel=channel, text=text, thread_ts=thread_ts, metadata=metadata
    )


def fetch_latest_metadata_from_thread(
    client: WebClient,
    channel: str,
    ts: str,
    event_type: str = None,
    event_fields: str | list[str] = None,
) -> Optional[dict]:
    """
    Fetch the latest metadata from a thread in a Slack channel.
    Args:
        client (WebClient): The Slack WebClient instance.
        channel (str): The channel ID.
        ts (str): The timestamp of the thread.
        event_type (str, optional): The type of event to filter by.
        event_fields (str | list[str], optional): The fields to check in the metadata.
    Returns:
        Optional[dict]: The metadata if found, otherwise None.
    """

    if isinstance(event_fields, str):
        event_fields = [event_fields]

    cursor = None
    for _ in range(5):
        h = client.conversations_replies(
            channel=channel, ts=ts, limit=4, include_all_metadata=True, cursor=cursor
        )

        has_more = h.data["has_more"]

        msgs = h.data["messages"]
        msgs.reverse()

        # conversations_replies always returns root msg
        if has_more:
            msgs = msgs[:-1]

        for msg in h.data["messages"]:
            meta = msg.get("metadata")
            if meta:
                if event_type and meta.get("event_type") != event_type:
                    continue

                payload = meta["event_payload"]

                if not event_fields:
                    return payload

                for field in event_fields:
                    if field not in payload:
                        break
                else:
                    return payload

        if not has_more:
            return None

        cursor = h.data["response_metadata"]["next_cursor"]

    return None


def get_pdf_text_by_file_id(app: App, pdf_id: str) -> dict:
    for f in app.client.files_list():
        for ff in f["files"]:
            if ff["user"] == BOT_USER_ID and ff["name"] == pdf_id:
                return ff
    return None


def download_file(files_block):
    file_msgs = []

    for file in files_block:
        media_type = file["mimetype"]
        r = requests.get(
            file["url_private_download"],
            headers={"Authorization": f"Bearer {os.environ.get("SLACK_BOT_TOKEN")}"},
        )
        byte_content = r.content
        b64_str = base64.b64encode(byte_content).decode()

        file_msgs.append(
            {
                "data": b64_str,
                "media_type": media_type,
                "type": "base64",
            }
        )

    return file_msgs


def extract_m4a_bio(m: dict) -> IO[bytes]:
    file = m["files"][0]

    r = requests.get(
        file["url_private_download"],
        headers={"Authorization": f"Bearer {os.environ.get("SLACK_BOT_TOKEN")}"},
    )
    bio = BytesIO(r.content)
    bio.name = "1.m4a"

    return bio


# def handle_m4a(app: App, m: dict) -> str:
#     from openai import OpenAI

#     file = m["files"][0]
#     text = get_pdf_text_by_file_id(app, file["id"])
#     if not text:
#         r = requests.get(
#             file["url_private_download"],
#             headers={"Authorization": f"Bearer {os.environ.get("SLACK_BOT_TOKEN")}"},
#         )
#         bio = BytesIO(r.content)
#         bio.name = "1.m4a"

#         model = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
#         transcription = model.audio.transcriptions.create(model="whisper-1", file=bio)
#         file_content = transcription.text

#         app.client.files_upload_v2(filename=file["id"], content=file_content)
#     else:
#         r = requests.get(
#             text["url_private_download"],
#             headers={"Authorization": f"Bearer {os.environ.get("SLACK_BOT_TOKEN")}"},
#         )
#         file_content = r.content.decode("utf-8")
#     return file_content


def fetch_single_message(client: WebClient, channel: str, msg_ts: str):
    r = client.conversations_history(
        channel=channel, latest=msg_ts, inclusive=True, limit=1
    )

    for m in r:
        for m in m["messages"]:
            return m

    return None


def _parse_slack_msg_and_file(m: dict) -> list:
    files = m.get("files")

    if not files:
        return None

    file = files[0]
    filetype = file["filetype"]

    r = requests.get(
        file["url_private_download"],
        headers={"Authorization": f"Bearer {os.environ.get("SLACK_BOT_TOKEN")}"},
    )

    from claude.agent import claude_image_block_from_bytes

    return claude_image_block_from_bytes(filetype, r.content)


def _parse_slack_msg(m: dict) -> list:
    content = m.get("text")

    if not content:
        return None

    user = "assistant" if "bot_id" in m else "user"
    return {"role": user, "content": content}


def get_history_by_thread_ts(app: App, channel: str, thread_ts: str) -> list:
    msgs = app.client.conversations_replies(channel=channel, ts=thread_ts)["messages"]

    ret = []
    for m in msgs:
        file_content = _parse_slack_msg_and_file(m)
        if file_content:
            ret.append(file_content)

        content = _parse_slack_msg(m)
        if content:
            ret.append(content)

    if ret and ret[-1]["role"] == "user":
        return ret[:-1]

    return ret


def get_channel_id_by_name(app: App, name: str) -> str:
    name = name.lower()
    for page in app.client.conversations_list():
        for c in page["channels"]:
            if c["name"].lower() == name:
                return c["id"]
    return


def get_channel_history(app: App, channel_id: str):
    return app.client.conversations_history(channel=channel_id)


def test():
    c = "C08BSGX1WDA"
    from slack.admin import APP

    pages = get_channel_history(APP, c)
    for page in pages:
        for m in page["messages"]:
            return m

    return None
