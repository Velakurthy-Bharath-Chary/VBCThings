from pathlib import Path
import re
from zipfile import BadZipFile, ZipFile
import xml.etree.ElementTree as ET

from pypdf import PdfReader


def load_text_file(file_path: str | Path) -> str:
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Document not found: {path}")
    if path.suffix.lower() not in {".txt", ".py"}:
        raise ValueError("Only TXT and Python source files are supported by this loader.")
    return path.read_text(encoding="utf-8")


def load_pdf_file(file_path: str | Path) -> str:
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Document not found: {path}")
    if path.suffix.lower() != ".pdf":
        raise ValueError("Only PDF files are supported by this loader.")
    reader = PdfReader(str(path))
    pages = []
    for page in reader.pages:
        page_text = page.extract_text()
        if page_text:
            pages.append(page_text)
    return "\n\n".join(pages)


def _office_xml_text(archive: ZipFile, member: str) -> str:
    info = archive.getinfo(member)
    if info.file_size > 20 * 1024 * 1024:
        raise ValueError("Office document XML section is too large.")
    root = ET.fromstring(archive.read(member))
    paragraphs = []
    for paragraph in root.iter():
        if paragraph.tag.rsplit("}", 1)[-1] == "p":
            text = "".join(
                node.text or ""
                for node in paragraph.iter()
                if node.tag.rsplit("}", 1)[-1] in {"t", "instrText"}
            ).strip()
            if text:
                paragraphs.append(text)
    return "\n".join(paragraphs)


def _open_office_archive(path: Path) -> ZipFile:
    archive = ZipFile(path)
    if sum(item.file_size for item in archive.infolist()) > 100 * 1024 * 1024:
        archive.close()
        raise ValueError("Office document expands beyond the supported size limit.")
    return archive


def load_docx_file(file_path: str | Path) -> str:
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Document not found: {path}")
    if path.suffix.lower() != ".docx":
        raise ValueError("Only DOCX files are supported by this loader.")
    try:
        with _open_office_archive(path) as archive:
            text = _office_xml_text(archive, "word/document.xml")
    except (BadZipFile, KeyError, ET.ParseError) as exc:
        raise ValueError("The uploaded DOCX file is invalid.") from exc
    return text


def load_pptx_file(file_path: str | Path) -> str:
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Document not found: {path}")
    if path.suffix.lower() != ".pptx":
        raise ValueError("Only PPTX files are supported by this loader.")
    try:
        with _open_office_archive(path) as archive:
            slide_names = sorted(
                (name for name in archive.namelist()
                 if re.fullmatch(r"ppt/slides/slide\d+\.xml", name)),
                key=lambda name: int(re.search(r"slide(\d+)", name).group(1)),
            )
            if not slide_names:
                raise ValueError("The uploaded PPTX contains no slides.")
            slides = [
                f"Slide {index}:\n{_office_xml_text(archive, name)}"
                for index, name in enumerate(slide_names, start=1)
            ]
    except (BadZipFile, KeyError, ET.ParseError) as exc:
        raise ValueError("The uploaded PPTX file is invalid.") from exc
    return "\n\n".join(slides)


# Loads TXT, Python source, PDF, DOCX, and PPTX text for RAG.
