import os
from typing import IO
from elevenlabs import ElevenLabs, VoiceSettings
from itertools import groupby

_api_key = os.environ["ELEVEN_LABS_API_KEY"]

ELEVEN_LABS_API = ElevenLabs(base_url="https://api.elevenlabs.io", api_key=_api_key)

MODEL_ID = "scribe_v1"

VOICE_ID = {
    "CN_FEMALE": "9lHjugDhwqoxA5MhX0az",  # Anna Su
    "SG_FEMALE": "SDNKIYEpTz0h56jQX8rA",  # Anthea
}


def text_to_speech(text, voice_id=VOICE_ID["SG_FEMALE"]):
    return ELEVEN_LABS_API.text_to_speech.convert(
        voice_id=voice_id,
        output_format="mp3_44100_128",
        text=text,
        model_id="eleven_multilingual_v2",
        voice_settings=VoiceSettings(speed=0.89),
    )


def single_speaker_transcribe_stream(file: IO[bytes]):
    ret = ELEVEN_LABS_API.speech_to_text.convert(
        model_id=MODEL_ID,
        num_speakers=1,
        tag_audio_events=False,
        diarize=True,
        file=file,
    )

    return ret.text


def single_speaker_transcribe_file(file: str):
    assert os.path.exists(file)

    with open(file, "rb") as f:
        ret = ELEVEN_LABS_API.speech_to_text.convert(
            model_id=MODEL_ID,
            num_speakers=1,
            tag_audio_events=False,
            diarize=True,
            file=f,
        )

    return ret.text


def multi_speaker_transcribe_file(file: str):
    assert os.path.exists(file)

    with open(file, "rb") as f:
        ret = ELEVEN_LABS_API.speech_to_text.convert(
            model_id=MODEL_ID,
            num_speakers=3,
            tag_audio_events=False,
            diarize=True,
            file=f,
        )

    words = ret.words

    results = []

    for g, ws in groupby(words, key=lambda ww: ww.speaker_id):
        results.append({"speaker": g, "content": "".join([w.text for w in ws])})

    return results
