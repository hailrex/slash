import csv
import os
import sys
from datetime import datetime

from dotenv import load_dotenv, set_key
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn

from slash import SlashAPI

console = Console()

CSV_COLUMNS = [
    "Category", "Provider", "Provider Credentials", "Card Description",
    "Name on Card", "Card Number", "Expiration Month", "Expiration Year",
    "Card CVV", "Card Type", "Website", "Source", "Notes", "Card State",
]

EXPORT_DIR = "/Users/elihigdon/Downloads"


def get_output_path() -> str:
    now = datetime.now()
    timestamp = now.strftime("%m_%d_%Y_%H_%M_%S")
    return os.path.join(EXPORT_DIR, f"{timestamp}.csv")


def get_api_key() -> str:
    load_dotenv()
    api_key = os.getenv("SLASH_API_KEY")
    if api_key and api_key != "your_key_here":
        return api_key

    console.print("[yellow]No SLASH_API_KEY found in .env file.[/yellow]")
    api_key = Prompt.ask("Enter your Slash API key")
    if not api_key.strip():
        console.print("[red]API key cannot be empty. Exiting.[/red]")
        sys.exit(1)

    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if Confirm.ask("Save this key to .env for future use?"):
        if not os.path.exists(env_path):
            with open(env_path, "w") as f:
                f.write(f"SLASH_API_KEY={api_key}\n")
        else:
            set_key(env_path, "SLASH_API_KEY", api_key)
        console.print("[green]Saved to .env[/green]")

    return api_key


def format_pan(pan: str) -> str:
    """Format PAN with spaces every 4 digits like '4931 0936 8116 1825'."""
    pan = pan.replace(" ", "").replace("-", "")
    return " ".join(pan[i:i+4] for i in range(0, len(pan), 4))


def card_to_row(card: dict) -> dict:
    pan = card.get("pan", "")
    if pan:
        pan = format_pan(pan)
    status = card.get("status", "")
    card_state = "Active" if status == "active" else "Inactive"
    name = card.get("name", "")
    return {
        "Category": "walmart.com",
        "Provider": "Slash",
        "Provider Credentials": name,
        "Card Description": "",
        "Name on Card": "",
        "Card Number": pan,
        "Expiration Month": str(card.get("expiryMonth", "")).zfill(2),
        "Expiration Year": str(card.get("expiryYear", "")),
        "Card CVV": card.get("cvv", ""),
        "Card Type": "Visa",
        "Website": "walmart.com",
        "Source": name,
        "Notes": "",
        "Card State": card_state,
    }


def export_to_csv(cards: list[dict], filepath: str = None):
    if filepath is None:
        filepath = get_output_path()
    rows = [card_to_row(c) for c in cards]
    with open(filepath, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    console.print(f"[green]Exported {len(rows)} cards to:[/green] {filepath}")


def display_table(cards: list[dict]):
    table = Table(title="Slash Cards", show_lines=True)
    table.add_column("Provider Creds", style="cyan")
    table.add_column("Card Number", style="bold white")
    table.add_column("CVV", style="bold white")
    table.add_column("Expiry", style="green")
    table.add_column("State", style="yellow")

    for card in cards:
        row = card_to_row(card)
        expiry = f"{row['Expiration Month']}/{row['Expiration Year']}"
        table.add_row(
            row["Provider Credentials"],
            row["Card Number"],
            row["Card CVV"],
            expiry,
            row["Card State"],
        )

    console.print(table)


def make_progress() -> Progress:
    return Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        console=console,
    )


def menu():
    api_key = get_api_key()
    client = SlashAPI(api_key)

    while True:
        console.print(Panel(
            "[bold]1.[/bold] Fetch & export ALL cards to CSV\n"
            "[bold]2.[/bold] Fetch & preview cards in table (no export)\n"
            "[bold]3.[/bold] Export only ACTIVE cards to CSV\n"
            "[bold]4.[/bold] Export only INACTIVE/CANCELLED cards to CSV\n"
            "[bold]5.[/bold] Search cards by name\n"
            "[bold]6.[/bold] Exit",
            title="[bold cyan]=== Slash Card Exporter ===[/bold cyan]",
            border_style="cyan",
        ))

        choice = Prompt.ask("Select an option", choices=["1", "2", "3", "4", "5", "6"])

        if choice == "1":
            with make_progress() as progress:
                cards = client.fetch_all_cards(progress=progress)
            export_to_csv(cards)

        elif choice == "2":
            with make_progress() as progress:
                cards = client.fetch_all_cards(progress=progress)
            if cards:
                display_table(cards)
            else:
                console.print("[yellow]No cards found.[/yellow]")

        elif choice == "3":
            with make_progress() as progress:
                cards = client.fetch_all_cards(status_filter="active", progress=progress)
            export_to_csv(cards)

        elif choice == "4":
            with make_progress() as progress:
                inactive = client.fetch_all_cards(status_filter="inactive", progress=progress)
            with make_progress() as progress:
                closed = client.fetch_all_cards(status_filter="closed", progress=progress)
            cards = inactive + closed
            export_to_csv(cards)

        elif choice == "5":
            name = Prompt.ask("Enter card name to search")
            with make_progress() as progress:
                cards = client.search_cards_by_name(name, progress=progress)
            if cards:
                display_table(cards)
            else:
                console.print("[yellow]No cards matching that name.[/yellow]")

        elif choice == "6":
            console.print("[bold]Goodbye![/bold]")
            break

        console.print()


if __name__ == "__main__":
    menu()
