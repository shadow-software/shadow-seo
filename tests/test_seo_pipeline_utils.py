from pathlib import Path
import sys


SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


from seo_pipeline_utils import (  # noqa: E402
    detect_business_type,
    html_parse_unreliable,
    page_type_for,
    severity_for_issue,
    url_slug,
    validate_public_url,
)


def test_url_slug_homepage():
    assert url_slug("https://example.com") == "homepage"


def test_url_slug_nested_path():
    assert url_slug("https://example.com/blog/seo-guide/?x=1") == "blog--seo-guide"


def test_detect_business_type_saas():
    parse_data = {
        "title": "Acme SEO Platform",
        "meta_description": "Research-first SEO workflow software",
        "h1": ["Ship SEO Workflows Faster"],
        "links": {"internal": [{"href": "https://example.com/pricing"}]},
    }
    business_type, industry = detect_business_type(parse_data, "Start free and book demo today", "https://example.com")
    assert business_type == "saas"
    assert industry == "software"


def test_html_parse_unreliable_empty_title_and_body():
    assert html_parse_unreliable({"title": "", "word_count": 0}, status_code=200, content_type="text/html")


def test_html_parse_unreliable_non_html():
    assert html_parse_unreliable({"title": "x", "word_count": 10}, status_code=200, content_type="application/json")


def test_page_type_for_help_hub():
    parse_data = {"schema": []}
    assert page_type_for("https://example.com/help", parse_data) == "help_hub"
    assert page_type_for("https://example.com/help/getting-started", parse_data) == "help_hub"


def test_severity_for_issue_noindex_is_not_critical():
    assert severity_for_issue("The page exposes a noindex directive.") == "high"


def test_validate_public_url_blocks_local_and_metadata_hosts():
    blocked = [
        "http://127.0.0.1",
        "http://localhost",
        "http://169.254.169.254/latest/meta-data",
        "http://metadata.google.internal/computeMetadata/v1",
    ]
    for target in blocked:
        try:
            validate_public_url(target)
        except ValueError as exc:
            assert "Blocked URL host" in str(exc)
        else:
            raise AssertionError(f"{target} should have been blocked")
