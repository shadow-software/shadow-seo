from pathlib import Path
import sys


SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "product_schema"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


from validate_product_schema import (  # noqa: E402
    audit_sampled_product_schemas,
    is_product_url,
    sample_product_urls,
    validate_product_schema,
)


def _codes(result: dict) -> set[str]:
    return {item["code"] for item in result["findings"]}


def test_good_product_offer_is_clean():
    result = validate_product_schema(FIXTURES / "good_product_offer.json")
    assert result["ok"] is True
    assert result["error_count"] == 0
    assert result["product_nodes"] == 1


def test_nested_item_reviewed_is_error():
    result = validate_product_schema(FIXTURES / "nested_item_reviewed.json")
    assert result["ok"] is False
    assert "review.nested_itemReviewed" in _codes(result)
    nested = [item for item in result["findings"] if item["code"] == "review.nested_itemReviewed"]
    assert nested[0]["severity"] == "error"


def test_missing_shipping_details_is_warning():
    result = validate_product_schema(FIXTURES / "missing_shipping.json")
    assert result["ok"] is True
    assert "offer.missing_shippingDetails" in _codes(result)
    warning = next(item for item in result["findings"] if item["code"] == "offer.missing_shippingDetails")
    assert warning["severity"] == "warning"


def test_product_without_offers_or_rating_is_error():
    result = validate_product_schema(FIXTURES / "missing_offers_and_rating.json")
    assert result["ok"] is False
    assert "product.missing_offers_or_rating" in _codes(result)


def test_aggregate_offer_shape_passes_price_rules():
    result = validate_product_schema(FIXTURES / "aggregate_offer.json")
    assert result["ok"] is True
    assert "offer.missing_price" not in _codes(result)
    assert "offer.missing_currency" not in _codes(result)


def test_maritime_like_html_nested_and_fixed():
    nested = validate_product_schema(FIXTURES / "maritime_like_nested.html")
    fixed = validate_product_schema(FIXTURES / "maritime_like_fixed.html")
    assert "review.nested_itemReviewed" in _codes(nested)
    assert nested["ok"] is False
    assert "review.nested_itemReviewed" not in _codes(fixed)
    assert fixed["ok"] is True


def test_standalone_review_warns_without_item_reviewed():
    payload = {
        "@context": "https://schema.org",
        "@type": "Review",
        "author": {"@type": "Person", "name": "Sam"},
        "reviewRating": {"@type": "Rating", "ratingValue": "4"},
        "reviewBody": "Solid product.",
    }
    result = validate_product_schema(payload)
    assert "review.standalone_needs_itemReviewed" in _codes(result)


def test_software_application_nested_item_reviewed():
    payload = {
        "@context": "https://schema.org",
        "@type": "SoftwareApplication",
        "name": "Harbor Ops",
        "review": {
            "@type": "Review",
            "itemReviewed": {"@id": "https://example.com/#app"},
            "author": {"@type": "Person", "name": "Pat"},
            "reviewRating": {"@type": "Rating", "ratingValue": "5"},
        },
    }
    result = validate_product_schema(payload)
    assert "review.nested_itemReviewed" in _codes(result)


def test_sample_product_urls_prefers_detail_pages():
    urls = [
        "https://shop.example.com/products",
        "https://shop.example.com/products/alpha",
        "https://shop.example.com/blog/hello",
        "https://shop.example.com/collections/indica/beta",
    ]
    sampled = sample_product_urls(urls, limit=5)
    assert sampled == [
        "https://shop.example.com/products/alpha",
        "https://shop.example.com/collections/indica/beta",
    ]
    assert is_product_url("https://shop.example.com/products/alpha")
    assert not is_product_url("https://shop.example.com/products")


def test_audit_sampled_product_schemas_fails_closed(monkeypatch):
    html = (FIXTURES / "maritime_like_nested.html").read_text(encoding="utf-8")

    class FakeResponse:
        status_code = 200
        url = "https://shop.example.com/products/coastal-blend"
        text = html

        def raise_for_status(self) -> None:
            return None

    class FakeSession:
        def get(self, url, timeout=20, allow_redirects=True):  # noqa: ANN001
            return FakeResponse()

    monkeypatch.setattr("validate_product_schema.build_session", lambda: FakeSession())
    monkeypatch.setattr("validate_product_schema.validate_public_url", lambda url: url)

    result = audit_sampled_product_schemas(
        ["https://shop.example.com/products/coastal-blend"],
        limit=3,
    )
    assert result["failed_closed"] is True
    assert result["ok"] is False
    assert any(item["code"] == "review.nested_itemReviewed" for item in result["findings"])
