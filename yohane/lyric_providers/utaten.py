from bs4 import BeautifulSoup
import requests

from yohane.lyrics import RichText, Ruby


def scan(node):
    result = []
    if node.name is None:  # Text node
        text = node.string.strip()
        if text:
            result.append(text)
    elif "class" in node.attrs and "ruby" in node.attrs["class"]:
        rb = node.find(class_="rb").get_text()
        rt = node.find(class_="rt").get_text()
        result.append(Ruby(rb, rt))
    elif node.name == "br":  # Line break
        result.append("\n")
    else:
        for child in node.contents:
            result.extend(scan(child))

    return result


def fetch_utaten(url: str) -> RichText:
    with requests.get(url) as r:
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "lxml")

    lyrics = soup.find(class_="hiragana")
    return RichText(scan(lyrics))
