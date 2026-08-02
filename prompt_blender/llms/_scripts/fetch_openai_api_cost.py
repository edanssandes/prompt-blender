#!/usr/bin/env python3
"""Fetch and print OpenAI Standard pricing as a Python costs dict."""

from __future__ import annotations

import re
import sys
from decimal import Decimal, InvalidOperation
from urllib.error import URLError
from urllib.request import urlopen


PRICING_URL = "https://developers.openai.com/api/docs/pricing.md"


def fetch_markdown(url: str) -> str:
	with urlopen(url, timeout=30) as response:  # nosec B310 - trusted docs URL
		charset = response.headers.get_content_charset() or "utf-8"
		return response.read().decode(charset, errors="replace")


def parse_money(cell: str) -> Decimal | None:
	token = cell.strip()
	if token in {"-", ""}:
		return None
	token = token.replace("$", "").replace(",", "")
	try:
		return Decimal(token)
	except InvalidOperation:
		return None


def normalize_model_name(model: str) -> str:
	# Remove context notes like: gpt-5.5 (<272K context length)
	return re.sub(r"\s*\(.*\)$", "", model.strip())


def extract_standard_costs(markdown: str) -> list[tuple[str, Decimal, Decimal]]:
	lines = markdown.splitlines()

	start = None
	for i, line in enumerate(lines):
		if line.strip() == "### Standard pricing data":
			start = i
			break

	if start is None:
		raise ValueError("Could not find '### Standard pricing data' section.")

	table_rows: list[str] = []
	in_table = False
	for line in lines[start + 1 :]:
		stripped = line.strip()
		if stripped.startswith("|"):
			in_table = True
			table_rows.append(stripped)
			continue
		if in_table:
			break

	if len(table_rows) < 3:
		raise ValueError("Standard pricing table is missing or incomplete.")

	header = [c.strip() for c in table_rows[0].strip("|").split("|")]
	try:
		model_idx = header.index("Model")
		input_idx = header.index("Short context input")
		output_idx = header.index("Short context output")
	except ValueError as exc:
		raise ValueError(
			"Expected table columns were not found in Standard pricing data."
		) from exc

	costs: list[tuple[str, Decimal, Decimal]] = []
	for row in table_rows[2:]:  # Skip header and separator row
		cells = [c.strip() for c in row.strip("|").split("|")]
		if len(cells) <= max(model_idx, input_idx, output_idx):
			continue

		model = normalize_model_name(cells[model_idx])
		input_price = parse_money(cells[input_idx])
		output_price = parse_money(cells[output_idx])

		if not model or input_price is None or output_price is None:
			continue

		costs.append((model, input_price, output_price))

	if not costs:
		raise ValueError("No Standard pricing entries were parsed.")

	return costs

def format_models_block(costs: list[tuple[str, Decimal, Decimal]], max_input_price: float=99.99) -> str:
    lines = ["models=["]
    for model, input_price, output_price in costs:
        if input_price > max_input_price:
            continue
        lines.append(f'    "{model}",')
    lines.append("]")
    return "\n".join(lines)

def format_costs_block(costs: list[tuple[str, Decimal, Decimal]]) -> str:
	lines = ["costs={", "        # Prices are USD per 1M tokens."]
	for model, input_price, output_price in costs:
		lines.append(
			"        "
			f"'{model}': {{'input': {input_price:.2f}, 'output': {output_price:.2f}}},"
		)
	lines.append("}")
	return "\n".join(lines)


def main() -> int:
	try:
		markdown = fetch_markdown(PRICING_URL)
		costs = extract_standard_costs(markdown)
	except (URLError, TimeoutError, ValueError) as exc:
		print(f"Error: {exc}", file=sys.stderr)
		return 1

	print(format_models_block(costs, max_input_price=2.00))
	print(format_costs_block(costs))
	return 0


if __name__ == "__main__":
	raise SystemExit(main())