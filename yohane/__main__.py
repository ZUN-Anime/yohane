import logging
import os
from io import TextIOWrapper
from pathlib import Path

import click

from yohane.audio_processing import compute_alignments, prepare_audio
from yohane.subtitles import make_ass
from yohane.text_processing import Lyrics

logger = logging.getLogger(__name__)


@click.command()
@click.argument("audio_file", type=click.Path(exists=True, path_type=Path))
@click.argument("lyrics_file", type=click.File())
@click.argument("extract_vocals", default=True)
def main(audio_file: Path, lyrics_file: TextIOWrapper, extract_vocals: bool):
    logger.info("Preparing audio...")
    waveform = prepare_audio(audio_file, extract_vocals)

    logger.info("Preparing lyrics...")
    lyrics = Lyrics(lyrics_file.read())

    logger.info("Computing forced alignment...")
    emission, token_spans = compute_alignments(waveform, lyrics.transcript)

    logger.info("Generating ASS...")
    subs = make_ass(lyrics, waveform, emission, token_spans)
    subs_file = audio_file.with_suffix(".ass")
    subs.save(subs_file.as_posix())
    logger.info(f"Saved to '{subs_file.as_posix()}'")


if __name__ == "__main__":
    logging.basicConfig(level=os.environ.get("LOGLEVEL", "INFO").upper())
    main()
