#!/usr/bin/env python3
"""Validate local links and essential HTML structure for the static site."""

from __future__ import annotations

import re
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit


SITE_ROOT = Path(__file__).resolve().parent.parent
VERIFICATION_FILES = {"google625f6ce16110ecf0.html"}
EXTERNAL_SCHEMES = {"data", "http", "https", "javascript", "mailto", "tel"}
BLOCK_ELEMENTS = (
    "article",
    "aside",
    "div",
    "footer",
    "form",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "header",
    "main",
    "nav",
    "ol",
    "section",
    "table",
    "ul",
)


class PageParser(HTMLParser):
    """Collect validation facts without treating HTML comments as live markup."""

    def __init__(self, source: Path) -> None:
        super().__init__(convert_charrefs=True)
        self.source = source
        self.doctype = False
        self.has_html_lang = False
        self.has_charset = False
        self.has_viewport = False
        self.has_title = False
        self.ids: set[str] = set()
        self.duplicate_ids: set[str] = set()
        self.references: list[tuple[int, str, str]] = []
        self.markup_errors: list[str] = []

    def handle_decl(self, decl: str) -> None:
        if decl.lower().strip() == "doctype html":
            self.doctype = True

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        self._handle_tag(tag, attrs)

    def handle_startendtag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        self._handle_tag(tag, attrs)

    def _handle_tag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        tag = tag.lower()
        attributes = {
            name.lower(): value for name, value in attrs if value is not None
        }

        if tag == "html" and attributes.get("lang", "").strip():
            self.has_html_lang = True
        elif tag == "meta":
            if attributes.get("charset", "").strip():
                self.has_charset = True
            if attributes.get("name", "").lower() == "viewport":
                self.has_viewport = True
        elif tag == "title":
            self.has_title = True

        element_id = attributes.get("id")
        if element_id:
            if element_id in self.ids:
                self.duplicate_ids.add(element_id)
            self.ids.add(element_id)

        for attribute in ("href", "src"):
            reference = attributes.get(attribute)
            if reference:
                self.references.append((self.getpos()[0], attribute, reference))

        if tag == "a" and "active" in attributes.get("class", "").split():
            if attributes.get("aria-current") != "page":
                self.markup_errors.append(
                    f"line {self.getpos()[0]}: active link must use "
                    'aria-current="page"'
                )

        if tag == "img" and self.source.parent == SITE_ROOT:
            required_image_attributes = ("alt", "decoding", "height", "width")
            for attribute in required_image_attributes:
                if not attributes.get(attribute, "").strip():
                    self.markup_errors.append(
                        f"line {self.getpos()[0]}: img missing {attribute}"
                    )

            if "srcset" in attributes:
                if not attributes.get("sizes", "").strip():
                    self.markup_errors.append(
                        f"line {self.getpos()[0]}: responsive img missing sizes"
                    )
                for candidate in attributes["srcset"].split(","):
                    source = candidate.strip().split(maxsplit=1)[0]
                    if source:
                        self.references.append(
                            (self.getpos()[0], "srcset", source)
                        )


def relative(path: Path) -> str:
    return path.relative_to(SITE_ROOT).as_posix()


def load_pages() -> tuple[dict[Path, PageParser], list[str]]:
    pages: dict[Path, PageParser] = {}
    errors: list[str] = []

    for source in sorted(SITE_ROOT.rglob("*.html")):
        parser = PageParser(source)
        text = source.read_text(encoding="utf-8")
        parser.feed(text)
        parser.close()
        pages[source.resolve()] = parser

        if source.name in VERIFICATION_FILES:
            continue

        page_name = relative(source)
        required = (
            (parser.doctype, "HTML5 doctype"),
            (parser.has_html_lang, "non-empty html[lang]"),
            (parser.has_charset, "character encoding"),
            (parser.has_viewport, "viewport metadata"),
            (parser.has_title, "document title"),
        )
        for present, description in required:
            if not present:
                errors.append(f"{page_name}: missing {description}")

        for duplicate_id in sorted(parser.duplicate_ids):
            errors.append(f'{page_name}: duplicate id="{duplicate_id}"')

        for markup_error in parser.markup_errors:
            errors.append(f"{page_name}:{markup_error}")

        # The hand-authored root pages use explicit paragraph end tags. Catch
        # accidental block content before </p>, while leaving generated TeX4ht
        # pages to their own optional-tag conventions.
        if source.parent == SITE_ROOT:
            uncommented = re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)
            block_pattern = "|".join(BLOCK_ELEMENTS)
            invalid_paragraph = re.search(
                rf"<p\b[^>]*>(?:(?!</p>).)*<({block_pattern})\b",
                uncommented,
                flags=re.IGNORECASE | re.DOTALL,
            )
            if invalid_paragraph:
                errors.append(
                    f"{page_name}: <{invalid_paragraph.group(1).lower()}> "
                    "must not be nested inside <p>"
                )

    return pages, errors


def validate_references(
    pages: dict[Path, PageParser], errors: list[str]
) -> None:
    for source, parser in pages.items():
        for line, attribute, reference in parser.references:
            parsed = urlsplit(reference)
            if parsed.scheme.lower() in EXTERNAL_SCHEMES or reference.startswith("//"):
                continue

            decoded_path = unquote(parsed.path)
            target = (
                source
                if not decoded_path
                else (source.parent / decoded_path).resolve()
            )
            source_name = relative(source)

            try:
                target.relative_to(SITE_ROOT)
            except ValueError:
                errors.append(
                    f"{source_name}:{line}: {attribute} escapes the site root: "
                    f"{reference}"
                )
                continue

            if not target.exists():
                errors.append(
                    f"{source_name}:{line}: missing {attribute} target: {reference}"
                )
                continue

            if parsed.fragment and target.suffix.lower() == ".html":
                target_parser = pages.get(target)
                fragment = unquote(parsed.fragment)
                if target_parser is None or fragment not in target_parser.ids:
                    errors.append(
                        f"{source_name}:{line}: missing fragment target: {reference}"
                    )


def main() -> int:
    pages, errors = load_pages()
    validate_references(pages, errors)

    if errors:
        print("Site validation failed:")
        for error in errors:
            print(f"  - {error}")
        return 1

    content_pages = sum(
        page.name not in VERIFICATION_FILES for page in pages
    )
    print(
        f"Validated {content_pages} HTML pages: required metadata, "
        "HTML structure checks, IDs, and local links are valid."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
