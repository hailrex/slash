import time
import requests
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn

BASE_URL = "https://api.slash.com"
VAULT_URL = "https://vault.slash.com"


class SlashAPI:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.session = requests.Session()
        self.session.headers.update({
            "X-API-Key": api_key,
            "Accept": "application/json",
        })

    def _request(self, method: str, url: str, params: dict = None):
        max_retries = 5
        for attempt in range(max_retries):
            try:
                response = self.session.request(method, url, params=params, timeout=30)
            except requests.exceptions.ConnectionError:
                wait = 2 ** attempt
                print(f"  Connection failed, retrying in {wait}s... ({attempt + 1}/{max_retries})")
                time.sleep(wait)
                continue
            if response.status_code == 429:
                retry_after = int(response.headers.get("Retry-After", 2 ** attempt))
                time.sleep(retry_after)
                continue
            response.raise_for_status()
            return response.json()
        raise Exception("Max retries exceeded — check your internet connection")

    def _fetch_card_detail(self, card_id: str):
        """Fetch a single card with full PAN and CVV from the vault endpoint."""
        url = f"{VAULT_URL}/card/{card_id}"
        params = {"include_pan": "true", "include_cvv": "true"}
        return self._request("GET", url, params=params)

    def fetch_all_cards(self, status_filter: str = None, progress: Progress = None):
        """Fetch all cards with automatic pagination, then get full details for each."""
        all_cards = []
        cursor = None
        task = None

        if progress:
            task = progress.add_task("[cyan]Fetching card list...", total=None)

        # Step 1: Get all card IDs from list endpoint
        while True:
            params = {}
            if cursor:
                params["cursor"] = cursor
            if status_filter:
                params["filter:status"] = status_filter

            data = self._request("GET", f"{BASE_URL}/card", params=params)
            items = data.get("items", [])
            metadata = data.get("metadata", {})

            all_cards.extend(items)

            if progress and task is not None:
                progress.update(task, description=f"[cyan]Listed {len(all_cards)} cards...")

            next_cursor = metadata.get("nextCursor")
            if not next_cursor:
                break
            cursor = next_cursor

        if progress and task is not None:
            progress.update(task, description=f"[cyan]Fetching full details for {len(all_cards)} cards...")

        # Step 2: Fetch full details (PAN + CVV) for each card
        detailed_cards = []
        for i, card in enumerate(all_cards):
            card_id = card.get("id")
            if card_id:
                try:
                    detail = self._fetch_card_detail(card_id)
                    detailed_cards.append(detail)
                except Exception:
                    detailed_cards.append(card)  # fallback to list data
            else:
                detailed_cards.append(card)

            if progress and task is not None:
                progress.update(task, description=f"[cyan]Card details {i + 1}/{len(all_cards)}...")

        if progress and task is not None:
            progress.update(task, description=f"[green]Done! Fetched {len(detailed_cards)} cards with full details.")

        return detailed_cards

    def search_cards_by_name(self, name: str, progress: Progress = None):
        """Fetch all cards and filter by name (case-insensitive)."""
        all_cards = self.fetch_all_cards(progress=progress)
        return [c for c in all_cards if name.lower() in c.get("name", "").lower()]
