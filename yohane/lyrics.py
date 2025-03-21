from dataclasses import dataclass
from functools import cached_property

import regex as re
import uroman as ur

uroman = ur.Uroman()   # load uroman data (takes about a second or so)
@dataclass
class Ruby:
    rb: str
    rt: str

    def __str__(self):
        return f"[{self.rb}]({self.rt})"

@dataclass
class Syllable:
    kana: str
    kanji: str
    roman: str

    def __str__(self):
        return (f"{self.kanji}|" if self.kanji else "") + self.kana


def normalize_uroman(text: str):
    text = text.lower()
    text = text.replace("’", "'")
    text = re.sub("([^a-z'-*\n ])", " ", text)
    text = re.sub("\n[\n ]+", "\n", text)
    text = re.sub(" +", " ", text)
    return text.strip()


@dataclass
class RichText:
    raw: list[str|Ruby] 

    def __str__(self):
        return "".join(str(ele) for ele in self.raw)

    @cached_property
    def lines(self):
        res = []
        line = []
        for ele in self.raw:
            if type(ele) is Ruby:
                line.append(ele)
            else:
                assert type(ele) is str
                # if '\n' not in ele:
                #     line.append(ele)
                # else:
                #     for l in ele.splitlines():
                #         if l:
                #             line.append(l)
                #         if line:
                #             res.append(line)
                #             line = []
                for s in ele.splitlines(keepends=True):
                    if s.endswith('\n'):
                        s = s.removesuffix('\n')
                        if s:
                            line.append(s)
                        if line:
                            res.append(line)
                            line = []
                    elif s:
                        line.append(s)
        if line:
            res.append(line)
        return [RichText(line) for line in res]

    # @cached_property
    # def words(self):
    #     res = []
    #     for ele in self.raw:
    #         if type(ele) is Ruby:
    #             res.append(ele)
    #         else:
    #             assert type(ele) is str
    #             res.extend(ele.split())
    #     return [RichText([w]) for w in res]

    @cached_property
    def syllables(self) -> list[Syllable]:
        res = []
        for ele in self.raw:
            if isinstance(ele, Ruby):
                first = True
                for edge in uroman.romanize_string(ele.rt, rom_format=ur.RomFormat.EDGES):
                    res.append(
                        Syllable(
                            ele.rt[edge.start : edge.end],
                            ele.rb if first else "#",
                            edge.txt,
                        )
                    )
                    first = False
            else:
                for edge in uroman.romanize_string(ele, rom_format=ur.RomFormat.EDGES):
                    res.append(Syllable(ele[edge.start : edge.end], None, edge.txt))
        return res

    @cached_property
    def romanized(self):
        romans = [uroman.romanize_string(ele.rt if type(ele) is Ruby else str(ele)) for ele in self.raw]
        return RichText(romans)

    @staticmethod
    def parse(text: str):
        """
        Parse a string containing furigana formatted as [kanji](furigana)
        and return a list of tokens.
        """
        # Compile a regex pattern to match [kanji](furigana)
        pattern = re.compile(r'\[([^\]]+)\]\(([^\)]+)\)')
        tokens = []
        last_index = 0

        # Find all furigana segments
        for match in pattern.finditer(text):
            start, end = match.span()
            # Add any text before the current match as plain text
            if start > last_index:
                tokens.append(text[last_index:start])
            # Extract the Kanji and furigana parts
            kanji = match.group(1)
            furigana = match.group(2)
            tokens.append(Ruby(kanji, furigana))
            last_index = end

        # Add any remaining text after the last furigana segment
        if last_index < len(text):
            tokens.append(text[last_index:])

        return RichText(tokens)


# @dataclass
# class _Text:
#     raw: str

#     @cached_property
#     def normalized(self):
#         return normalize_uroman(self.raw)

#     @cached_property
#     def transcript(self):
#         return self.normalized.split()


# @dataclass
# class Lyrics(_Text):
#     @cached_property
#     def lines(self):
#         return [Line(line) for line in filter(None, self.raw.splitlines())]


# @dataclass
# class Line(_Text):
#     @cached_property
#     def words(self):
#         return [Word(word) for word in filter(None, self.transcript)]


# @dataclass
# class Word(_Text):
#     @cached_property
#     def syllables(self):
#         return auto_split(self.normalized)


# # https://docs.karaokes.moe/aegisub/auto-split.lua
# AUTO_SPLIT_RE = re.compile(
#     r"(?i)(?:(?<=[^sc])(?=h))|(?:(?<=[^kstnhfmrwpbdgzcj])(?=y))|(?:(?<=[^t])(?=s))|(?:(?=[ktnfmrwpbdgzcj]))|(?:(?<=[aeiou]|[^[:alnum:]])(?=[aeiou]))"
# )


# def auto_split(word: str):
#     splitter_str, _ = AUTO_SPLIT_RE.subn("#@", word)
#     syllables = re.split("#@", splitter_str, flags=re.MULTILINE)
#     syllables = list(filter(None, syllables))
#     return syllables
