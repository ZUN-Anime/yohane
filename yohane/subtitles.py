from dataclasses import dataclass
from functools import partial

from pysubs2 import SSAEvent, SSAFile
from torch import Tensor
from torchaudio.functional import TokenSpan
from torchaudio.pipelines import Wav2Vec2FABundle

from yohane.audio import fa_bundle
from yohane.lyrics import RichText, Syllable, normalize_uroman
from yohane.utils import get_identifier


@dataclass
class TimedSyllable:
    value: Syllable
    start_s: float  # s
    end_s: float  # s

    def k_duration(self, snap_to: float | None = None):
        k_s = (snap_to if snap_to is not None else self.end_s) - self.start_s  # s
        return round(k_s * 100)  # cs


def make_ass(
    lyrics: RichText,
    waveform: Tensor,
    sample_rate: int,
    emission: Tensor,
    token_spans: list[list[TokenSpan]],
):
    all_line_syllables = time_lyrics(
        lyrics, waveform, sample_rate, emission, token_spans
    )

    subs = SSAFile.load('sampleKaraokeMugen.ass')
    subs.info["Original Timing"] = get_identifier()

    marginV = False
    for line, syllables in zip(lyrics.lines, all_line_syllables):
        start_syl = syllables[0]
        end_syl = syllables[-1]
        assert start_syl is not None and end_syl is not None

        event = SSAEvent(round(start_syl.start_s * 1000), round(end_syl.end_s * 1000), style="Sample KM [Up]", effect="karaoke", type="Comment", marginv=int(marginV))
        event_roman = SSAEvent(round(start_syl.start_s * 1000), round(end_syl.end_s * 1000), style="Sample KM [Down]", effect="karaoke", type="Comment", marginv=int(marginV)-1)

        for i, syllable in enumerate(syllables):
            if syllable is None:  # space
                continue

            value = str(syllable.value)
            value_roman = syllable.value.roman

            snap_to_i = None
            if i < len(syllables) - 1:  # not last syllable in line
                if syllables[i + 1] is None:  # next is space
                    value += " "
                    value_roman += " "
                    snap_to_i = i + 2  # snap to syllable after the space
                else:
                    snap_to_i = i + 1  # snap to next syllable

            if snap_to_i is not None:
                snap_to_syl = syllables[snap_to_i]
                assert snap_to_syl is not None
                snap_to = snap_to_syl.start_s
            else:
                snap_to = None

            k_duration = syllable.k_duration(snap_to=snap_to)  # cs
            event.text += rf"{{\k{k_duration}}}{value}"
            event_roman.text += rf"{{\k{k_duration}}}{syllable.value.roman}"

        # save the raw line in a comment
        subs.append(event)
        subs.append(event_roman)
        marginV = not marginV

    return subs

# def 
def rstrip(l: list, value=None):
    while l and l[-1] == value:
        l.pop()

def cut_lines(lines: list[list[TimedSyllable | None]], by_roman: bool, max_length: int):
    """
    Cut lines to fit within a certain length
    """
    assert max_length > 0
    new_lines = []
    for line in lines:
        new_line = []
        line_length = 0
        for syllable in line:
            if syllable is None:
                syllable_length = 1
            elif by_roman:
                syllable_length = len(syllable.value.roman)
            else:
                syllable_length = len(str(syllable.value))
            if line_length + syllable_length > max_length:
                rstrip(new_line)
                new_lines.append(new_line)
                new_line = []
                line_length = 0
            new_line.append(syllable)
            line_length += syllable_length
        if new_line:
            rstrip(new_line)
            new_lines.append(new_line)
    return new_lines


def time_lyrics(
    lyrics: RichText,
    waveform: Tensor,
    sample_rate: int,
    emission: Tensor,
    token_spans: list[list[TokenSpan]],
):
    # audio processing parameters
    num_frames = emission.size(1)
    ratio = waveform.size(1) / num_frames
    tokenizer = fa_bundle.get_tokenizer()

    token_spans_iter = iter(token_spans)
    add_syllable = partial(_time_syllable, ratio, sample_rate, tokenizer)

    spans = next(token_spans_iter)
    span_idx = 0

    all_line_syllables: list[list[TimedSyllable | None]] = []

    for line in lyrics.lines:
        line_syllables: list[TimedSyllable | None] = []

        for syllable in line.syllables:
            if syllable.roman.isspace():
                # add a None to represent a space
                line_syllables.append(None)
                continue
            token_str = normalize_uroman(syllable.roman)
            t_start, t_end = None, None
            if token_str == "":
                # the syllable cannot be processed by the tokenizer
                # we append it to the previous syllable
                last_syllable = None
                if line_syllables:
                    last_syllable = line_syllables[-1]
                elif all_line_syllables:
                    last_syllable = all_line_syllables[-1][-1]

                line_syllables.append(TimedSyllable(syllable, last_syllable.end_s, last_syllable.end_s))
                continue
            if span_idx >= len(spans):
                # fetch the next spans
                spans = next(token_spans_iter)
                span_idx = 0
            nb_tokens, t_start, t_end = add_syllable(spans, token_str, span_idx)
            span_idx += nb_tokens
            timed_syllable = TimedSyllable(syllable, t_start, t_end)
            line_syllables.append(timed_syllable)

        if line_syllables:
            rstrip(line_syllables) # remove trailing space 
            all_line_syllables.append(line_syllables)

    try:
        next(token_spans_iter)  # make sure we used all spans
        raise RuntimeError("not all spans were used")
    except StopIteration:
        pass

    return all_line_syllables


def _time_syllable(
    ratio: float,
    sample_rate: float,
    tokenizer: Wav2Vec2FABundle.Tokenizer,
    spans: list[TokenSpan],
    token_str: str,
    span_idx: int,
):
    syllable_tokens = tokenizer([token_str])
    nb_tokens = len(syllable_tokens[0])
    assert syllable_tokens[0] == [span.token for span in spans[span_idx:span_idx + nb_tokens]]

    # start and end time of syllable
    x0 = ratio * spans[span_idx].start
    x1 = ratio * spans[span_idx + nb_tokens - 1].end
    t_start = x0 / sample_rate  # s
    t_end = x1 / sample_rate  # s

    return nb_tokens, t_start, t_end
