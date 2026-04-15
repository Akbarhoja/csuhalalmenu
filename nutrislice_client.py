from __future__ import annotations

import json
import logging
import re
from collections.abc import Iterable
from datetime import date, datetime, timedelta
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from constants import MEAL_SLUGS, NUTRISLICE_BASE_URL
from models import DiningLocation
from utils import normalize_whitespace, slug_to_title

LOGGER = logging.getLogger(__name__)


class NutrisliceClient:
    def __init__(self, *, timeout_seconds: float = 8.0) -> None:
        self._timeout = timeout_seconds
        self._api_base_url = self._derive_api_base_url(NUTRISLICE_BASE_URL)
        self._site_host = urlparse(NUTRISLICE_BASE_URL).netloc
        self._cached_locations: list[DiningLocation] | None = None
        self._cached_locations_at: datetime | None = None
        self._locations_ttl = timedelta(hours=6)

    async def discover_locations(self) -> list[DiningLocation]:
        if self._cached_locations is not None and self._cached_locations_at is not None:
            if datetime.utcnow() - self._cached_locations_at < self._locations_ttl:
                return self._cached_locations

        async with self._build_api_client() as client:
            locations = await self._discover_from_api(client)
            if locations:
                LOGGER.info("Discovered %s dining locations from Nutrislice API.", len(locations))
                self._cached_locations = locations
                self._cached_locations_at = datetime.utcnow()
                return locations

        async with self._build_site_client() as client:
            locations = await self._discover_from_homepage(client)
            if locations:
                LOGGER.info("Discovered %s dining locations from Nutrislice homepage.", len(locations))
                self._cached_locations = locations
                self._cached_locations_at = datetime.utcnow()
                return locations

        raise RuntimeError("Unable to discover CSU dining locations from Nutrislice.")

    async def fetch_menu_payload(
        self,
        *,
        location_slug: str,
        meal_name: str,
        target_date: date,
    ) -> Any:
        meal_slug = MEAL_SLUGS[meal_name]
        endpoint = (
            f"/weeks/school/{location_slug}/menu-type/{meal_slug}/"
            f"{target_date:%Y/%m/%d}/"
        )
        async with self._build_api_client() as client:
            response = await self._request_text(client, endpoint)
        return self._safe_json_loads(response)

    def _build_api_client(self) -> httpx.AsyncClient:
        headers = {
            "User-Agent": "csu-halal-bot/1.0 (+https://csumenus.nutrislice.com)",
            "Accept": "application/json, text/html;q=0.9, */*;q=0.8",
            "x-nutrislice-origin": self._site_host,
        }
        return httpx.AsyncClient(
            base_url=self._api_base_url,
            timeout=self._timeout,
            headers=headers,
            follow_redirects=True,
        )

    def _build_site_client(self) -> httpx.AsyncClient:
        headers = {
            "User-Agent": "csu-halal-bot/1.0 (+https://csumenus.nutrislice.com)",
            "Accept": "application/json, text/html;q=0.9, */*;q=0.8",
        }
        return httpx.AsyncClient(
            base_url=NUTRISLICE_BASE_URL,
            timeout=self._timeout,
            headers=headers,
            follow_redirects=True,
        )

    async def _discover_from_api(self, client: httpx.AsyncClient) -> list[DiningLocation]:
        payload = self._safe_json_loads(await self._request_text(client, "/schools/"))
        if isinstance(payload, list):
            return self._extract_locations_from_payload(payload, top_level_only=True)
        return self._extract_locations_from_payload(payload)

    async def _discover_from_homepage(self, client: httpx.AsyncClient) -> list[DiningLocation]:
        html = await self._request_text(client, "/")
        discovered = self._extract_locations_from_html(html)
        return sorted(discovered, key=lambda item: item.name.casefold())

    async def _request_text(self, client: httpx.AsyncClient, endpoint: str) -> str:
        async for attempt in AsyncRetrying(
            retry=retry_if_exception_type((httpx.TimeoutException, httpx.TransportError)),
            stop=stop_after_attempt(2),
            wait=wait_exponential(multiplier=0.4, min=0.4, max=1.2),
            reraise=True,
        ):
            with attempt:
                response = await client.get(endpoint)
                response.raise_for_status()
                return response.text
        raise RuntimeError(f"Request failed for endpoint {endpoint}")

    def _extract_locations_from_payload(self, payload: Any, *, top_level_only: bool = False) -> list[DiningLocation]:
        discovered: dict[str, DiningLocation] = {}
        nodes = payload if top_level_only and isinstance(payload, list) else self._walk(payload)
        for node in nodes:
            if not isinstance(node, dict):
                continue

            slug = self._first_string(node, ("slug", "school_slug", "location_slug", "site_slug"))
            name = self._first_string(node, ("name", "school", "title", "location_name", "display_name"))
            if not slug:
                continue

            cleaned_slug = self._clean_location_slug(slug)
            if not cleaned_slug:
                continue

            cleaned_name = normalize_whitespace(name) if name else slug_to_title(cleaned_slug)
            discovered[cleaned_slug.casefold()] = DiningLocation(name=cleaned_name, slug=cleaned_slug)

        return sorted(discovered.values(), key=lambda item: item.name.casefold())

    def _extract_locations_from_html(self, html: str) -> list[DiningLocation]:
        discovered: dict[str, DiningLocation] = {}
        soup = BeautifulSoup(html, "html.parser")

        for anchor in soup.select("a[href]"):
            href = anchor.get("href", "")
            slug = self._slug_from_menu_url(href)
            if not slug:
                continue
            name = normalize_whitespace(anchor.get_text(" ", strip=True)) or slug_to_title(slug)
            discovered[slug.casefold()] = DiningLocation(name=name, slug=slug)

        patterns = (
            r'"slug"\s*:\s*"(?P<slug>[^"]+)"\s*,\s*"name"\s*:\s*"(?P<name>[^"]+)"',
            r'"name"\s*:\s*"(?P<name>[^"]+)"\s*,\s*"slug"\s*:\s*"(?P<slug>[^"]+)"',
        )
        for pattern in patterns:
            for match in re.finditer(pattern, html):
                slug = self._clean_location_slug(match.group("slug"))
                if not slug:
                    continue
                name = normalize_whitespace(match.group("name"))
                discovered[slug.casefold()] = DiningLocation(name=name, slug=slug)

        return list(discovered.values())

    def _slug_from_menu_url(self, href: str) -> str | None:
        full_url = urljoin(NUTRISLICE_BASE_URL + "/", href)
        match = re.search(r"/menu/([^/?#]+)/?", full_url)
        if not match:
            return None
        return self._clean_location_slug(match.group(1))

    def _clean_location_slug(self, raw_slug: str) -> str | None:
        cleaned = raw_slug.strip().strip("/")
        if not cleaned:
            return None
        if "/" in cleaned:
            cleaned = cleaned.split("/", maxsplit=1)[0]
        return cleaned

    def _safe_json_loads(self, value: str) -> Any:
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value

    def _derive_api_base_url(self, site_url: str) -> str:
        parsed = urlparse(site_url)
        host = parsed.netloc
        if host.endswith(".nutrislice.com"):
            api_host = host[: -len("nutrislice.com")] + "api.nutrislice.com"
        else:
            raise ValueError(f"Unsupported Nutrislice host: {host}")
        return f"{parsed.scheme}://{api_host}/menu/api"

    def _walk(self, payload: Any) -> Iterable[Any]:
        yield payload
        if isinstance(payload, dict):
            for value in payload.values():
                yield from self._walk(value)
        elif isinstance(payload, list):
            for value in payload:
                yield from self._walk(value)

    def _first_string(self, payload: dict[str, Any], keys: tuple[str, ...]) -> str | None:
        for key in keys:
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return None
