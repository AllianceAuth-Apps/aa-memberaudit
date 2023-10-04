"""Logic for converting Eve Online XML into other formats."""

import unicodedata

import bleach
import bs4

from eveuniverse.core import evexml

from allianceauth.services.hooks import get_extension_logger
from app_utils.logging import LoggerAddTag

from memberaudit import __title__

logger = LoggerAddTag(get_extension_logger(__name__), __title__)

DEFAULT_FONT_SIZE = 13

EVEXML_ALLOWED_TAGS = [
    "a",
    "b",
    "br",
    "font",
    "i",
    "u",
]

EVEXML_ALLOWED_ATTRIBUTES = {
    "a": ["href"],
    "font": ["size"],
}

EVEXML_ALLOWED_PROTOCOLS = {
    "http",
    "https",
    "showinfo",
    "killreport",
}


def eve_xml_to_html(xml_doc: str, add_default_style: bool = False) -> str:
    """Convert Eve Online XML to HTML.

    Args:
    - xml_doc: XML document
    - add_default_style: When set true will add the default style to all unstyled fragments
    """
    xml_doc = unicodedata.normalize("NFKC", xml_doc)
    xml_doc = bleach.clean(
        xml_doc,
        protocols=EVEXML_ALLOWED_PROTOCOLS,
        tags=EVEXML_ALLOWED_TAGS,
        attributes=EVEXML_ALLOWED_ATTRIBUTES,
        strip=True,
    )
    soup = bs4.BeautifulSoup(xml_doc, "html.parser")
    _convert_font_tag(soup)
    _convert_a_tag(soup)
    if add_default_style:
        _add_default_style(soup)
    return str(soup)


def _convert_font_tag(soup):
    """Convert the font tags into HTML style."""
    for element in soup.find_all("font"):
        if not element.contents:
            # Element is empty, just remove it from tree as it won't render visibly.
            element.decompose()
            continue
        element.name = "span"
        styles = []
        if "size" in element.attrs:
            # Cast to int and use the absolute value, otherwise use default font size.
            # Prevents a limited CSS injection via this attribute.
            try:
                size = abs(int(element["size"]))
            except ValueError:
                size = DEFAULT_FONT_SIZE
            styles.append(f"font-size: {size}px")
            del element["size"]
        if styles:
            element["style"] = "; ".join(styles)


def _convert_a_tag(soup: bs4.BeautifulSoup):
    """Convert links into HTML."""
    for element in soup.find_all("a"):
        if not element.contents:
            # Element is empty, just remove it from tree as it won't render visibly.
            element.decompose()
            continue
        # Verify if the href attr exists as it can be removed by Bleach for unsupported protocols.
        # Otherwise, we replace this element with its children.
        if not element.get("href"):
            element.replace_with_children()
            continue
        new_href = evexml.eve_link_to_url(element["href"])
        if new_href:
            element["href"] = new_href
            element["target"] = "_blank"
        else:
            element["href"] = "#"


def _add_default_style(soup: bs4.BeautifulSoup):
    """Add default style to all unstyled fragments."""
    for element in soup.children:
        if isinstance(element, bs4.NavigableString):
            new_tag = soup.new_tag("span")
            new_tag["style"] = f"font-size: {DEFAULT_FONT_SIZE}px"
            element.wrap(new_tag)
