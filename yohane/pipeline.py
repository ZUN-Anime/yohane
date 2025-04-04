import logging
from pathlib import Path

import torch
import torchaudio
from torchaudio.functional import TokenSpan

from yohane.audio import Separator, compute_alignments
from yohane.lyrics import RichText, normalize_uroman
from yohane.subtitles import make_ass

logger = logging.getLogger(__name__)


class Yohane:
    def __init__(self, separator: Separator | None):
        self.separator = separator
        self.song: tuple[torch.Tensor, int] | None = None
        self.vocals: tuple[torch.Tensor, int] | None = None
        self.lyrics: RichText | None = None
        self.forced_alignment: tuple[torch.Tensor, list[list[TokenSpan]]] | None = None

    @property
    def forced_aligned_audio(self):
        return self.vocals if self.vocals is not None else self.song

    @property
    def off_vocal(self):
        if self.song is not None and self.vocals is not None:
            song_waveform, song_sample_rate = self.song
            vocals_waveform, vocals_sample_rate = self.vocals
            vocals_waveform_resampled = torchaudio.functional.resample(
                vocals_waveform, vocals_sample_rate, song_sample_rate
            )
            return song_waveform - vocals_waveform_resampled, song_sample_rate

    def load_song(self, song_file: Path):
        logger.info("Loading song")
        self.song = torchaudio.load(song_file.as_posix())

    def extract_vocals(self):
        if self.separator is not None:
            logger.info(f"Extracting vocals with {self.separator=}")
            assert self.song
            self.vocals = self.separator(*self.song)

    def load_lyrics(self, lyrics_str: RichText):
        logger.info("Loading lyrics")
        self.lyrics = lyrics_str

    def force_align(self):
        logger.info("Computing forced alignment")
        assert self.forced_aligned_audio is not None and self.lyrics is not None
        self.forced_alignment = compute_alignments(
            *self.forced_aligned_audio, normalize_uroman(str(self.lyrics.romanized)).split()
        )

    def make_subs(self):
        logger.info("Generating .ass")
        assert (
            self.lyrics is not None
            and self.forced_aligned_audio is not None
            and self.forced_alignment is not None
        )
        subs = make_ass(self.lyrics, *self.forced_aligned_audio, *self.forced_alignment)
        return subs
