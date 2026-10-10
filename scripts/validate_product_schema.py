#!/usr/bin/env python3
"""
Local Product / Merchant / Review schema contract validator.

Pure ruleset mirroring Google Product snippet + Merchant listings + Review
nesting guidance. No network required for core validation; URL fetch is optional.

Usage:
    python validate_product_schema.py path/to/snippet.json --json
    python validate_product_schema.py path/to/page.html --json
    python validate_product_schema.py '{"@type":"Product",...}' --json
    python validate_product_schema.py https://example.com/products/foo --json
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from seo_pipeline_utils import DEFAULT_TIMEOUT, build_session, validate_public_url


PRODUCT_TYPES = frozenset({"Product", "ProductGroup"})
REVIEW_HOST_TYPES = frozenset({"Product", "ProductGroup", "SoftwareApplication", "WebApplication"})
OFFER_TYPES = frozenset({"Offer", "AggregateOffer"})
GTIN_KEYS = ("gtin", "gtin8", "gtin12", "gtin13", "gtin14", "isbn", "mpn", "sku")
PRODUCT_URL_TOKENS = (
    "/products/",
    "/product/",
    "/shop/",
    "/p/",
    "/item/",
    "/collections/",
)
DEFAULT_SAMPLE_LIMIT = 8


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _type_names(node: Any) -> set[str]:
    if not isinstance(node, dict):
        return set()
    raw = node.get("@type")
    if isinstance(raw, list):
        return {str(item) for item in raw if item}
    if isinstance(raw, str) and raw:
        return {raw}
    return set()


def _has_type(node: Any, *names: str) -> bool:
    return bool(_type_names(node) & set(names))


def _is_absolute_url(value: Any) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False
    parsed = urlparse(value.strip())
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _nonempty(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (int, float)):
        return True
    if isinstance(value, list):
        return any(_nonempty(item) for item in value)
    if isinstance(value, dict):
        return any(_nonempty(item) for item in value.values())
    return True


def _finding(severity: str, code: str, path: str, message: str) -> dict[str, str]:
    return {
        "severity": severity,
        "code": code,
        "path": path,
        "message": message,
    }


def extract_jsonld_blocks(html: str) -> list[Any]:
    """Parse JSON-LD script blocks from an HTML document."""
    soup = BeautifulSoup(html, "lxml")
    blocks: list[Any] = []
    for node in soup.find_all("script", attrs={"type": "application/ld+json"}):
        raw = node.string or node.get_text()
        if not raw or not raw.strip():
            continue
        try:
            blocks.append(json.loads(raw))
        except json.JSONDecodeError:
            continue
    return blocks


def normalize_roots(payload: Any) -> list[Any]:
    """Flatten @graph / list wrappers into a list of top-level schema nodes."""
    roots: list[Any] = []

    def visit(node: Any) -> None:
        if isinstance(node, list):
            for child in node:
                visit(child)
            return
        if not isinstance(node, dict):
            return
        graph = node.get("@graph")
        if isinstance(graph, list):
            for child in graph:
                visit(child)
            # Keep the wrapper if it also declares a concrete @type.
            if _type_names(node):
                roots.append(node)
            return
        roots.append(node)

    visit(payload)
    return roots


def load_schema_input(source: str | dict[str, Any] | list[Any], *, timeout: int = DEFAULT_TIMEOUT) -> list[Any]:
    """
    Accept JSON-LD object/list, HTML string, filesystem path, or http(s) URL.

    Returns a list of top-level schema nodes (with @graph already expanded).
    """
    if isinstance(source, (dict, list)):
        return normalize_roots(source)

    text = str(source).strip()
    if not text:
        return []

    # Inline JSON
    if text[0] in "[{":
        try:
            return normalize_roots(json.loads(text))
        except json.JSONDecodeError:
            pass

    # Filesystem path
    path = Path(text)
    if path.is_file():
        content = path.read_text(encoding="utf-8", errors="ignore")
        if path.suffix.lower() in {".html", ".htm", ".php", ".vue", ".jsx", ".tsx"}:
            return normalize_roots(extract_jsonld_blocks(content))
        try:
            return normalize_roots(json.loads(content))
        except json.JSONDecodeError:
            return normalize_roots(extract_jsonld_blocks(content))

    # HTML blob
    if "<script" in text.lower() and "ld+json" in text.lower():
        return normalize_roots(extract_jsonld_blocks(text))

    # URL fetch
    if text.startswith(("http://", "https://")):
        url = validate_public_url(text)
        session = build_session()
        response = session.get(url, timeout=timeout, allow_redirects=True)
        response.raise_for_status()
        return normalize_roots(extract_jsonld_blocks(response.text))

    raise ValueError(
        "Unsupported input. Pass JSON-LD, an HTML/JSON file path, an HTML string, or an http(s) URL."
    )


def _image_values(product: dict[str, Any]) -> list[str]:
    values: list[str] = []
    for item in _as_list(product.get("image")):
        if isinstance(item, str):
            values.append(item)
        elif isinstance(item, dict):
            url = item.get("url") or item.get("contentUrl")
            if isinstance(url, str):
                values.append(url)
    return values


def _has_brand_or_identifier(product: dict[str, Any]) -> bool:
    brand = product.get("brand")
    if isinstance(brand, str) and brand.strip():
        return True
    if isinstance(brand, dict) and _nonempty(brand.get("name")):
        return True
    return any(_nonempty(product.get(key)) for key in GTIN_KEYS)


def _validate_offer(offer: dict[str, Any], path: str) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    types = _type_names(offer)

    if "AggregateOffer" in types:
        has_price = _nonempty(offer.get("price")) or (
            _nonempty(offer.get("lowPrice")) and _nonempty(offer.get("highPrice"))
        )
        if not has_price:
            findings.append(
                _finding(
                    "error",
                    "offer.missing_price",
                    f"{path}.lowPrice|highPrice|price",
                    "AggregateOffer needs price, or both lowPrice and highPrice.",
                )
            )
    else:
        if not _nonempty(offer.get("price")):
            findings.append(
                _finding(
                    "error",
                    "offer.missing_price",
                    f"{path}.price",
                    "Offer is missing a numeric price (no currency symbol).",
                )
            )

    if not _nonempty(offer.get("priceCurrency")):
        findings.append(
            _finding(
                "error",
                "offer.missing_currency",
                f"{path}.priceCurrency",
                "Offer/AggregateOffer is missing priceCurrency (ISO 4217).",
            )
        )

    if not _nonempty(offer.get("availability")):
        findings.append(
            _finding(
                "warning",
                "offer.missing_availability",
                f"{path}.availability",
                "Offer is missing availability (recommended Schema.org URL enum).",
            )
        )

    if not _nonempty(offer.get("shippingDetails")):
        findings.append(
            _finding(
                "warning",
                "offer.missing_shippingDetails",
                f"{path}.shippingDetails",
                "Merchant listings recommend shippingDetails on the Offer.",
            )
        )

    if not _nonempty(offer.get("hasMerchantReturnPolicy")):
        findings.append(
            _finding(
                "warning",
                "offer.missing_return_policy",
                f"{path}.hasMerchantReturnPolicy",
                "Merchant listings recommend hasMerchantReturnPolicy on the Offer.",
            )
        )

    if not _nonempty(offer.get("validFrom")):
        findings.append(
            _finding(
                "warning",
                "offer.missing_validFrom",
                f"{path}.validFrom",
                "Offer is missing validFrom (ISO 8601).",
            )
        )

    if not _nonempty(offer.get("priceValidUntil")):
        findings.append(
            _finding(
                "warning",
                "offer.missing_priceValidUntil",
                f"{path}.priceValidUntil",
                "Offer is missing priceValidUntil (ISO 8601).",
            )
        )

    return findings


def _validate_nested_reviews(reviews: Any, path: str) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    for index, review in enumerate(_as_list(reviews)):
        if not isinstance(review, dict):
            continue
        if not _has_type(review, "Review") and "itemReviewed" not in review and "reviewRating" not in review:
            # Untyped review-shaped object still checked for itemReviewed nesting.
            pass
        review_path = f"{path}[{index}]" if isinstance(reviews, list) else path
        if "itemReviewed" in review:
            findings.append(
                _finding(
                    "error",
                    "review.nested_itemReviewed",
                    f"{review_path}.itemReviewed",
                    "Review nested under Product/SoftwareApplication must omit itemReviewed "
                    "(GSC Product/Review directional conflict).",
                )
            )
    return findings


def validate_product_node(product: dict[str, Any], path: str = "$.Product") -> list[dict[str, str]]:
    """Validate a single Product / ProductGroup node."""
    findings: list[dict[str, str]] = []

    if not _nonempty(product.get("name")):
        findings.append(
            _finding("error", "product.missing_name", f"{path}.name", "Product is missing name.")
        )

    images = _image_values(product)
    if not images:
        findings.append(
            _finding("error", "product.missing_image", f"{path}.image", "Product is missing image.")
        )
    elif not all(_is_absolute_url(url) for url in images):
        findings.append(
            _finding(
                "error",
                "product.missing_image",
                f"{path}.image",
                "Product image must be absolute http(s) URL(s).",
            )
        )

    offers = product.get("offers")
    has_offers = _nonempty(offers)
    has_rating = _nonempty(product.get("aggregateRating"))
    has_review = _nonempty(product.get("review"))
    if not (has_offers or has_rating or has_review):
        findings.append(
            _finding(
                "error",
                "product.missing_offers_or_rating",
                path,
                "Product needs offers, aggregateRating, or review for rich-result eligibility.",
            )
        )

    if not _has_brand_or_identifier(product):
        findings.append(
            _finding(
                "warning",
                "product.missing_brand_or_gtin",
                f"{path}.brand|gtin|mpn|sku",
                "Product should include brand and/or gtin/mpn/sku.",
            )
        )

    for index, offer in enumerate(_as_list(offers)):
        if not isinstance(offer, dict):
            continue
        offer_types = _type_names(offer)
        if offer_types and not (offer_types & OFFER_TYPES):
            continue
        offer_path = f"{path}.offers[{index}]" if isinstance(offers, list) else f"{path}.offers"
        findings.extend(_validate_offer(offer, offer_path))

    if has_review:
        findings.extend(_validate_nested_reviews(product.get("review"), f"{path}.review"))

    return findings


def validate_standalone_review(review: dict[str, Any], path: str = "$.Review") -> list[dict[str, str]]:
    """Validate a top-level Review that is not nested under a product host."""
    if _nonempty(review.get("itemReviewed")):
        return []
    return [
        _finding(
            "warning",
            "review.standalone_needs_itemReviewed",
            f"{path}.itemReviewed",
            "Top-level Review should include itemReviewed.",
        )
    ]


def _walk_for_validation(
    node: Any,
    path: str,
    *,
    nested_under_review_host: bool,
    findings: list[dict[str, str]],
    seen_product_ids: set[int],
) -> None:
    if isinstance(node, list):
        for index, child in enumerate(node):
            _walk_for_validation(
                child,
                f"{path}[{index}]",
                nested_under_review_host=nested_under_review_host,
                findings=findings,
                seen_product_ids=seen_product_ids,
            )
        return

    if not isinstance(node, dict):
        return

    types = _type_names(node)
    is_review_host = bool(types & REVIEW_HOST_TYPES)
    is_product = bool(types & PRODUCT_TYPES)

    if is_product:
        node_id = id(node)
        if node_id not in seen_product_ids:
            seen_product_ids.add(node_id)
            findings.extend(validate_product_node(node, path))
    elif "Review" in types and not nested_under_review_host and not is_review_host:
        findings.extend(validate_standalone_review(node, path))

    # Nested reviews under SoftwareApplication (non-Product host) still need the nesting rule.
    if is_review_host and not is_product and _nonempty(node.get("review")):
        findings.extend(_validate_nested_reviews(node.get("review"), f"{path}.review"))

    next_nested = nested_under_review_host or is_review_host
    for key, value in node.items():
        if key in {"@context", "@type", "@id"}:
            continue
        # Product.review already validated inside validate_product_node.
        if is_product and key == "review":
            continue
        if is_review_host and not is_product and key == "review":
            continue
        child_path = f"{path}.{key}"
        if isinstance(value, (dict, list)):
            _walk_for_validation(
                value,
                child_path,
                nested_under_review_host=next_nested,
                findings=findings,
                seen_product_ids=seen_product_ids,
            )


def validate_product_schema(source: str | dict[str, Any] | list[Any], *, timeout: int = DEFAULT_TIMEOUT) -> dict[str, Any]:
    """
    Validate Product/Merchant/Review contract rules against schema input.

    Returns structured findings with severities error|warning.
    """
    roots = load_schema_input(source, timeout=timeout)
    findings: list[dict[str, str]] = []
    seen_product_ids: set[int] = set()

    for index, root in enumerate(roots):
        path = f"$[{index}]" if len(roots) > 1 else "$"
        if isinstance(root, dict) and _type_names(root):
            type_label = sorted(_type_names(root))[0]
            path = f"$.{type_label}" if len(roots) == 1 else f"$[{index}].{type_label}"
        _walk_for_validation(
            root,
            path,
            nested_under_review_host=False,
            findings=findings,
            seen_product_ids=seen_product_ids,
        )

    # Deduplicate while preserving order
    unique: list[dict[str, str]] = []
    seen: set[tuple[str, str, str, str]] = set()
    for item in findings:
        key = (item["severity"], item["code"], item["path"], item["message"])
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)

    errors = [item for item in unique if item["severity"] == "error"]
    warnings = [item for item in unique if item["severity"] == "warning"]
    return {
        "ok": not errors,
        "product_nodes": len(seen_product_ids),
        "findings": unique,
        "error_count": len(errors),
        "warning_count": len(warnings),
        "codes": sorted({item["code"] for item in unique}),
    }


def format_finding(finding: dict[str, str]) -> str:
    """Single-line issue string for analyze_schema / audit reports."""
    return f"[{finding['severity']}] {finding['code']} at {finding['path']}: {finding['message']}"


def is_product_url(url: str) -> bool:
    """Heuristic: path looks like a product or collection detail URL."""
    path = urlparse(url).path.lower()
    if any(token in path for token in PRODUCT_URL_TOKENS):
        # Prefer detail pages over bare /products or /collections indexes.
        stripped = path.rstrip("/")
        if stripped.endswith(("/products", "/product", "/shop", "/collections", "/collection")):
            return False
        return True
    return bool(re.search(r"/products?/[^/]+", path))


def sample_product_urls(
    urls: list[str],
    *,
    limit: int = DEFAULT_SAMPLE_LIMIT,
    base_url: str | None = None,
) -> list[str]:
    """Deduplicate and sample product-like URLs (default 5–10)."""
    sampled: list[str] = []
    seen: set[str] = set()
    for raw in urls:
        if not raw:
            continue
        candidate = urljoin(base_url, raw) if base_url else raw
        if not candidate.startswith(("http://", "https://")):
            continue
        if not is_product_url(candidate):
            continue
        normalized = candidate.split("#", 1)[0]
        if normalized in seen:
            continue
        seen.add(normalized)
        sampled.append(normalized)
        if len(sampled) >= max(1, limit):
            break
    return sampled


def audit_sampled_product_schemas(
    urls: list[str],
    *,
    timeout: int = DEFAULT_TIMEOUT,
    limit: int = DEFAULT_SAMPLE_LIMIT,
    base_url: str | None = None,
) -> dict[str, Any]:
    """
    Fetch and validate a sample of product URLs.

    Fails closed when any sampled product returns error-severity findings.
    """
    sample = sample_product_urls(urls, limit=limit, base_url=base_url)
    pages: list[dict[str, Any]] = []
    all_findings: list[dict[str, str]] = []

    session = build_session()
    for url in sample:
        page: dict[str, Any] = {"url": url, "ok": False, "findings": [], "error": None}
        try:
            safe_url = validate_public_url(url)
            response = session.get(safe_url, timeout=timeout, allow_redirects=True)
            response.raise_for_status()
            result = validate_product_schema(response.text, timeout=timeout)
            page["url"] = response.url
            page["ok"] = result["ok"]
            page["findings"] = result["findings"]
            page["product_nodes"] = result["product_nodes"]
            if result["product_nodes"] == 0:
                missing = _finding(
                    "error",
                    "product.missing_jsonld",
                    "$",
                    "Sampled product URL has no Product JSON-LD markup.",
                )
                page["findings"] = [missing]
                page["ok"] = False
            for finding in page["findings"]:
                annotated = dict(finding)
                annotated["message"] = f"{url}: {finding['message']}"
                all_findings.append(annotated)
        except Exception as exc:  # noqa: BLE001
            page["error"] = str(exc)
            failure = _finding(
                "error",
                "product.missing_jsonld",
                "$",
                f"Failed to fetch/validate sampled product URL: {exc}",
            )
            page["findings"] = [failure]
            annotated = dict(failure)
            annotated["message"] = f"{url}: {failure['message']}"
            all_findings.append(annotated)
        pages.append(page)

    errors = [item for item in all_findings if item["severity"] == "error"]
    return {
        "sampled_urls": [page["url"] for page in pages],
        "sample_count": len(pages),
        "pages": pages,
        "findings": all_findings,
        "error_count": len(errors),
        "ok": not errors,
        "failed_closed": bool(errors),
    }


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Validate Product/Merchant JSON-LD locally")
    parser.add_argument("source", help="JSON-LD, HTML/JSON file, HTML string, or URL")
    parser.add_argument("--timeout", "-t", type=int, default=DEFAULT_TIMEOUT, help="Fetch timeout")
    parser.add_argument("--json", "-j", action="store_true", help="Output JSON")
    args = parser.parse_args()

    result = validate_product_schema(args.source, timeout=args.timeout)
    if args.json:
        print(json.dumps(result, indent=2))
        raise SystemExit(0 if result["ok"] else 1)

    print("Product Schema Validation")
    print("=" * 40)
    print(f"Product nodes: {result['product_nodes']}")
    print(f"Errors: {result['error_count']}  Warnings: {result['warning_count']}")
    if result["findings"]:
        print("\nFindings:")
        for finding in result["findings"]:
            print(f"- {format_finding(finding)}")
    else:
        print("\nNo Product/Merchant contract issues found.")
    raise SystemExit(0 if result["ok"] else 1)


if __name__ == "__main__":
    main()
