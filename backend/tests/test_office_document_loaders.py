from zipfile import ZipFile

import pytest

from app.rag.loaders import load_docx_file, load_pptx_file


def make_office_file(path, members):
    with ZipFile(path, "w") as archive:
        for name, content in members.items():
            archive.writestr(name, content)


def test_docx_loader_extracts_paragraphs_and_table_text(tmp_path):
    path = tmp_path / "lesson.docx"
    make_office_file(path, {
        "word/document.xml": (
            '<w:document xmlns:w="urn:word"><w:body>'
            '<w:p><w:r><w:t>Python functions</w:t></w:r></w:p>'
            '<w:tbl><w:tr><w:tc><w:p><w:r><w:t>Return values</w:t>'
            '</w:r></w:p></w:tc></w:tr></w:tbl>'
            '</w:body></w:document>'
        ),
    })
    assert load_docx_file(path) == "Python functions\nReturn values"


def test_pptx_loader_extracts_slides_in_numeric_order(tmp_path):
    path = tmp_path / "lesson.pptx"
    make_office_file(path, {
        "ppt/slides/slide2.xml": '<p:sld xmlns:p="p" xmlns:a="a"><a:p><a:r><a:t>Second</a:t></a:r></a:p></p:sld>',
        "ppt/slides/slide1.xml": '<p:sld xmlns:p="p" xmlns:a="a"><a:p><a:r><a:t>First</a:t></a:r></a:p></p:sld>',
    })
    assert load_pptx_file(path) == "Slide 1:\nFirst\n\nSlide 2:\nSecond"


@pytest.mark.parametrize("loader,suffix", [(load_docx_file, ".docx"), (load_pptx_file, ".pptx")])
def test_office_loaders_reject_invalid_zip(tmp_path, loader, suffix):
    path = tmp_path / f"invalid{suffix}"
    path.write_bytes(b"PK\x03\x04not a zip archive")
    with pytest.raises(ValueError, match="invalid"):
        loader(path)


# FILE PURPOSE:
# Verifies secure text extraction from Office Open XML documents and slides.
