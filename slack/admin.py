import os

from slack_bolt import App
from slack_sdk.web.client import WebClient
from .constants import ADMIN_CHANNEL as ADMIN_CHANNEL_ID

APP = App(
    token=os.environ["SLACK_ADMIN_BOT_TOKEN"],
)


class ChannelMessage:
    def __init__(
        self, slack_client, timeout_seconds=100, *, channel_id=ADMIN_CHANNEL_ID
    ):
        self.channel_id = channel_id

        if isinstance(slack_client, WebClient):
            self._slack_client: WebClient = slack_client
        elif isinstance(slack_client, App):
            self._slack_client: WebClient = slack_client.client
        else:
            raise ValueError(f"Unsupported slack client type: {slack_client.__class__}")

        self._timeout_seconds = timeout_seconds

    @property
    def client(self):
        return self._slack_client

    def upload_file_content(self, filename, content, *, thread_ts: str = None):
        r = self._slack_client.files_upload_v2(
            channel=self.channel_id,
            filename=filename,
            content=content,
            thread_ts=thread_ts,
        )

        if not r.data["ok"]:
            return None

        if thread_ts:
            return thread_ts  # if it is provided the sent msg will have it

        return r.data.get("ts")

    def upload_file(self, filepath, *, thread_ts: str = None):
        with open(filepath, "rb") as f:
            r = self._slack_client.files_upload_v2(
                channel=self.channel_id,
                filename="attachment",
                file=f,
                thread_ts=thread_ts,
            )
        if not r.data["ok"]:
            return None
        if thread_ts:
            return thread_ts  # if it is provided the sent msg will have it
        return r.data.get("ts")

    def send_msg(self, msg, *, markdown: bool = False, thread_ts: str = None):
        if markdown:
            msg = f"""```\n{msg}\n```"""

        r = self._slack_client.chat_postMessage(
            channel=self.channel_id, text=msg, thread_ts=thread_ts
        )
        if not r.data["ok"]:
            return None
        if thread_ts:
            return thread_ts  # if it is provided the sent msg will have it
        return r.data.get("ts")

    def input(self, msg):
        resp = self.send_msg(msg)
        return self.wait_for_reply(resp)

    def delete_msg_and_all_thread(self, thread_ts: str):
        replies = self._slack_client.conversations_replies(
            channel=self.channel_id, ts=thread_ts
        )

        for reply in replies.data("messages", []):
            if reply.get("subtype") == "tombstone":
                continue
            self._slack_client.chat_delete(channel=self.channel_id, ts=reply.get("ts"))

    def wait_for_reply(self, sent_response):
        assert sent_response, f"Response is not ok"
        ts = sent_response

        for _ in range(self._timeout_seconds * 2):
            for p in self._slack_client.conversations_replies(
                channel=self.channel_id, ts=ts, limit=1
            ):
                if len(p.data["messages"]) > 1:
                    return p.data["messages"][-1].get("text", "")

        return None


ADMIN_CLIENT = ChannelMessage(APP)
