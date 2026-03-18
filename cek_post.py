"""
Capture full-page screenshots for each contract address listed in ca.txt.

Each line in the input file must follow the format:
    email|ticker|contract_address

Only the contract address is used for the Zora Coin URL:
    https://zora.co/coin/base:{contract_address}
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Iterable, List, Tuple

from playwright.sync_api import Playwright, TimeoutError as PlaywrightTimeoutError, sync_playwright

LINE_PATTERN = re.compile(r"\s*\|\s*")
SAFE_CHARS = re.compile(r"[^A-Za-z0-9._-]+")


def parse_lines(lines: Iterable[str]) -> List[Tuple[str, str, str]]:
    """Return list of (email, ticker, contract) tuples from raw lines."""
    entries: List[Tuple[str, str, str]] = []
    for raw in lines:
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        parts = LINE_PATTERN.split(stripped, maxsplit=2)
        if len(parts) != 3:
            raise ValueError(f"Gagal parse baris: {raw!r}. Format harus email|ticker|contract.")
        email, ticker, contract = (part.strip() for part in parts)
        if not contract or contract == "-":
            # Skip baris yang tidak punya contract valid.
            continue
        entries.append((email, ticker, contract))
    if not entries:
        raise ValueError("File input kosong atau tidak punya baris valid.")
    return entries


def sanitize_filename(label: str, contract: str) -> str:
    base = label.strip() or contract
    safe = SAFE_CHARS.sub("_", base)
    return safe or contract


def take_screenshots(
    playwright: Playwright,
    entries: List[Tuple[str, str, str]],
    output_dir: Path,
    viewport: Tuple[int, int],
    timeout_ms: int,
    wait_after_load_ms: int,
) -> None:
    browser = playwright.chromium.launch(headless=True)
    context = browser.new_context(viewport={"width": viewport[0], "height": viewport[1]})
    page = context.new_page()
    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        for idx, (_, ticker, contract) in enumerate(entries, start=1):
            url = f"https://zora.co/coin/base:{contract}"
            filename = f"{idx:03d}_{sanitize_filename(ticker, contract)}.png"
            target_path = output_dir / filename
            print(f"[{idx}/{len(entries)}] Navigasi ke {url} -> {target_path}")
            page.goto(url, wait_until="networkidle", timeout=timeout_ms)
            if wait_after_load_ms > 0:
                page.wait_for_timeout(wait_after_load_ms)
            page.screenshot(path=str(target_path), full_page=True)
    finally:
        context.close()
        browser.close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Ambil screenshot full-page untuk tiap contract di ca.txt.")
    parser.add_argument("--input", default="ca.txt", help="File sumber daftar contract (default: ca.txt).")
    parser.add_argument("--output-dir", default="screenshots", help="Folder tujuan screenshot (default: screenshots).")
    parser.add_argument(
        "--viewport",
        default="1280x720",
        help="Ukuran viewport WIDTHxHEIGHT (default: 1280x720).",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=30_000,
        help="Timeout per halaman dalam ms (default: 30000).",
    )
    parser.add_argument(
        "--wait-after-load",
        type=int,
        default=5_000,
        help="Jeda (ms) setelah halaman selesai dimuat sebelum screenshot (default: 5000).",
    )
    return parser


def parse_viewport(value: str) -> Tuple[int, int]:
    try:
        width_str, height_str = value.lower().split("x", 1)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("Format viewport harus WIDTHxHEIGHT, misal 1366x768.") from exc
    return int(width_str), int(height_str)


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    viewport = parse_viewport(args.viewport)

    input_path = Path(args.input)
    if not input_path.exists():
        parser.error(f"File input tidak ditemukan: {input_path}")

    try:
        entries = parse_lines(input_path.read_text(encoding="utf-8").splitlines())
    except ValueError as exc:
        parser.error(str(exc))

    output_dir = Path(args.output_dir)

    try:
        with sync_playwright() as playwright:
            take_screenshots(
                playwright=playwright,
                entries=entries,
                output_dir=output_dir,
                viewport=viewport,
                timeout_ms=args.timeout,
                wait_after_load_ms=args.wait_after_load,
            )
    except PlaywrightTimeoutError as exc:
        parser.error(f"Halaman tidak selesai dimuat dalam {args.timeout} ms: {exc}")


if __name__ == "__main__":
    main()
