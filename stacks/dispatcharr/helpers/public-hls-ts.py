#!/usr/bin/env python3
"""Remux a public Streamlink HLS feed into Dispatcharr's MPEG-TS input."""

import argparse
import signal
import subprocess
import sys
from urllib.parse import urlsplit


def interrupted(signum, _frame):
    raise SystemExit(128 + signum)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("url")
    args = parser.parse_args()
    if urlsplit(args.url).scheme not in {"http", "https"}:
        parser.error("An HTTP or HTTPS stream URL is required")
    signal.signal(signal.SIGTERM, interrupted)
    signal.signal(signal.SIGINT, interrupted)
    children = []
    try:
        source = subprocess.Popen(
            ["streamlink", "--no-config", "--no-plugin-sideloading",
             "--loglevel", "error", "--stdout", args.url, "best"],
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
        )
        children.append(source)
        muxer = subprocess.Popen(
            ["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error",
             "-fflags", "+genpts+discardcorrupt", "-i", "pipe:0",
             "-map", "0:v:0", "-map", "0:a:0?", "-c", "copy", "-sn", "-dn",
             "-avoid_negative_ts", "make_zero",
             "-mpegts_flags", "+pat_pmt_at_frames+resend_headers+initial_discontinuity",
             "-flush_packets", "1", "-f", "mpegts", "pipe:1"],
            stdin=source.stdout,
        )
        children.append(muxer)
        source.stdout.close()
        return muxer.wait()
    finally:
        for child in reversed(children):
            if child.poll() is None:
                child.terminate()
        for child in reversed(children):
            try:
                child.wait(timeout=5)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait()


if __name__ == "__main__":
    sys.exit(main())
