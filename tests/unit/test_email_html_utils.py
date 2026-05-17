from src.utils.email_html_utils import markdown_bold_to_html, strip_markdown_bold


def test_strip_markdown_bold() -> None:
    assert strip_markdown_bold("Hello **World**") == "Hello World"
    assert strip_markdown_bold("**Python** at **TCS**") == "Python at TCS"


def test_markdown_bold_to_html() -> None:
    html = markdown_bold_to_html("Hi **Utsab**,\nuse **Python**.")
    assert "<strong>Utsab</strong>" in html
    assert "<strong>Python</strong>" in html
    assert "**" not in html
    assert "<br>" in html


def test_markdown_bold_escapes_html_in_plain_text() -> None:
    html = markdown_bold_to_html("Hello <script> & **safe**")
    assert "<script>" not in html
    assert "&amp;" in html
    assert "<strong>safe</strong>" in html
