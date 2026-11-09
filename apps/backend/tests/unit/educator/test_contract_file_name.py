import pytest

from app.contexts.educator.application.contract_files import parse_pdf_file_name
from app.shared.errors import BusinessRuleViolation

pytestmark = pytest.mark.unit


def test_parse_pdf_file_name() -> None:
    assert parse_pdf_file_name(" 계약서 최종.PDF ") == ("계약서 최종.PDF", "pdf")
    assert parse_pdf_file_name("가" * 96 + ".pdf")[0] == "가" * 96 + ".pdf"  # 정확히 100자


@pytest.mark.parametrize(
    ("raw", "code"),
    [
        ("", "invalid_file_name"),
        ("가" * 97 + ".pdf", "file_name_too_long"),
        ("../secret.pdf", "invalid_file_name"),
        ("a\\b.pdf", "invalid_file_name"),
        ("계약서\n.pdf", "invalid_file_name"),
        ("계약서.docx", "unsupported_file_type"),
        (".pdf", "unsupported_file_type"),
        ("계약서", "unsupported_file_type"),
    ],
)
def test_parse_pdf_file_name_rejects(raw: str, code: str) -> None:
    with pytest.raises(BusinessRuleViolation) as exc:
        parse_pdf_file_name(raw)
    assert exc.value.code == code
