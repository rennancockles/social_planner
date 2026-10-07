import httpx2

from app.settings import settings

UNSPLASH_RANDOM_URL = "https://api.unsplash.com/photos/random"


def search_image(query: str) -> bytes:
    with httpx2.Client(timeout=15) as http:
        response = http.get(
            UNSPLASH_RANDOM_URL,
            params={"query": query, "orientation": "squarish"},
            headers={"Authorization": f"Client-ID {settings.unsplash_access_key}"},
        )
        response.raise_for_status()
        photo = response.json()
        if not photo:
            raise RuntimeError(f"No Unsplash results for query: {query!r}")

        image_response = http.get(photo["urls"]["regular"])
        image_response.raise_for_status()
        return image_response.content
