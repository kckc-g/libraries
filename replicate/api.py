import os
import time
import requests
from typing import Literal

_api_key = os.environ.get("REPLICATE_API_TOKEN")

BASE_URL = "https://api.replicate.com/v1"
FLUX_MODEL = "black-forest-labs/flux-2-pro"


class ReplicateError(Exception):
    pass


class ReplicateClient:
    def __init__(self, api_key: str = None):
        self.api_key = api_key or _api_key
        if not self.api_key:
            raise ValueError("REPLICATE_API_TOKEN environment variable not set")
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }
        )

    def _post(self, url: str, json: dict) -> dict:
        r = self.session.post(url, json=json, timeout=60)
        if r.status_code not in (200, 201):
            raise ReplicateError(f"POST {url} failed: {r.status_code} - {r.text}")
        return r.json()

    def _get(self, url: str) -> dict:
        r = self.session.get(url, timeout=60)
        if r.status_code != 200:
            raise ReplicateError(f"GET {url} failed: {r.status_code} - {r.text}")
        return r.json()

    def create_prediction(
        self,
        prompt: str,
        *,
        model: str = FLUX_MODEL,
        resolution: str = "2 MP",
        aspect_ratio: str = "3:2",
        input_images: list = None,
        output_format: Literal["png", "jpg", "webp"] = "png",
        safety_tolerance: int = 2,
    ) -> dict:
        """Create an image generation prediction. Returns the prediction object."""
        url = f"{BASE_URL}/models/{model}/predictions"
        payload = {
            "input": {
                "prompt": prompt,
                "resolution": resolution,
                "aspect_ratio": aspect_ratio,
                "input_images": input_images or [],
                "output_format": output_format,
                "safety_tolerance": safety_tolerance,
            }
        }
        return self._post(url, payload)

    def get_prediction(self, prediction_id: str) -> dict:
        """Get the current status of a prediction."""
        url = f"{BASE_URL}/predictions/{prediction_id}"
        return self._get(url)

    def wait_for_prediction(
        self, prediction_id: str, *, poll_interval: float = 1.0, timeout: float = 300
    ) -> dict:
        """Poll a prediction until it completes or fails."""
        start = time.time()
        while True:
            prediction = self.get_prediction(prediction_id)
            status = prediction.get("status")

            if status == "succeeded":
                return prediction
            elif status in ("failed", "canceled"):
                error = prediction.get("error", "Unknown error")
                raise ReplicateError(f"Prediction {status}: {error}")

            if time.time() - start > timeout:
                raise ReplicateError(f"Prediction timed out after {timeout}s")

            time.sleep(poll_interval)

    def generate_image(
        self,
        prompt: str,
        *,
        model: str = FLUX_MODEL,
        resolution: str = "2 MP",
        aspect_ratio: str = "3:2",
        input_images: list = None,
        output_format: Literal["png", "jpg", "webp"] = "png",
        safety_tolerance: int = 2,
        poll_interval: float = 1.0,
        timeout: float = 300,
    ) -> str:
        """Generate an image and wait for completion. Returns the output URL."""
        prediction = self.create_prediction(
            prompt,
            model=model,
            resolution=resolution,
            aspect_ratio=aspect_ratio,
            input_images=input_images,
            output_format=output_format,
            safety_tolerance=safety_tolerance,
        )

        prediction_id = prediction["id"]
        result = self.wait_for_prediction(
            prediction_id, poll_interval=poll_interval, timeout=timeout
        )

        output = result.get("output")
        if isinstance(output, list) and output:
            return output[0]
        return output

    def download_image(self, url: str, target_path: str) -> None:
        """Download an image from a URL to a local file."""
        r = requests.get(url, timeout=120)
        if r.status_code != 200:
            raise ReplicateError(f"Failed to download image: {r.status_code}")
        with open(target_path, "wb") as f:
            f.write(r.content)


REPLICATE_API = ReplicateClient()
