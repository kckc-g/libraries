import contextvars

from contextlib import contextmanager


CHAT_CTX = contextvars.ContextVar("chat_context")


def context():
    return CHAT_CTX.get(None)


@contextmanager
def in_chat(app, channel_id: str | None = None, thread_id: str | None = None):
    token = CHAT_CTX.set((app, channel_id, thread_id))
    try:
        yield context
    finally:
        CHAT_CTX.reset(token)
