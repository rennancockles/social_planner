import contextlib

import httpx2

from app.settings import settings

UNSPLASH_RANDOM_URL = "https://api.unsplash.com/photos/random"
UNSPLASH_PHOTOS_URL = "https://api.unsplash.com/photos"


def _auth_headers() -> dict[str, str]:
    return {"Authorization": f"Client-ID {settings.unsplash_access_key}"}


def search_image(query: str) -> bytes:
    with httpx2.Client(timeout=15) as http:
        response = http.get(
            UNSPLASH_RANDOM_URL,
            params={"query": query, "orientation": "squarish"},
            headers=_auth_headers(),
        )
        response.raise_for_status()
        photo = response.json()
        if not photo:
            raise RuntimeError(f"No Unsplash results for query: {query!r}")

        image_response = http.get(photo["urls"]["regular"])
        image_response.raise_for_status()
        return image_response.content


def suggest_images(query: str, count: int = 4) -> list[dict[str, str]]:
    with httpx2.Client(timeout=15) as http:
        response = http.get(
            UNSPLASH_RANDOM_URL,
            params={"query": query, "orientation": "squarish", "count": count},
            headers=_auth_headers(),
        )
        response.raise_for_status()
        photos = response.json() or []
        return [{"id": photo["id"], "thumb_url": photo["urls"]["small"]} for photo in photos]


def fetch_image_bytes_by_id(photo_id: str) -> bytes:
    with httpx2.Client(timeout=15) as http:
        response = http.get(f"{UNSPLASH_PHOTOS_URL}/{photo_id}", headers=_auth_headers())
        response.raise_for_status()
        photo = response.json()

        with contextlib.suppress(httpx2.HTTPError):
            http.get(f"{UNSPLASH_PHOTOS_URL}/{photo_id}/download", headers=_auth_headers())

        image_response = http.get(photo["urls"]["regular"])
        image_response.raise_for_status()
        return image_response.content
