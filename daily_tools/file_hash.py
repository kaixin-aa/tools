"""Compute file or stdin digests."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import BinaryIO


DEFAULT_CHUNK_SIZE = 65536
ALGORITHMS = tuple(
    name
    for name in (
        "md5",
        "sha1",
        "sha224",
        "sha256",
        "sha384",
        "sha512",
        "blake2b",
        "blake2s",
        "sha3_256",
        "sha3_512",
    )
    if name in hashlib.algorithms_guaranteed
)


def hash_stream(stream: BinaryIO, algorithm: str, chunk_size: int) -> str:
    """Return the hex digest for a binary stream."""
    digest = hashlib.new(algorithm)
    while True:
        chunk = stream.read(chunk_size)
        if not chunk:
            break
        digest.update(chunk)
    return digest.hexdigest()


def hash_path(path: Path, algorithm: str, chunk_size: int) -> str:
    """Return the hex digest for a filesystem path."""
    with path.open("rb") as handle:
        return hash_stream(handle, algorithm=algorithm, chunk_size=chunk_size)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Compute file or stdin digests with a selectable hash algorithm.",
    )
    parser.add_argument(
        "paths",
        nargs="*",
        type=Path,
        help="Files to hash. Reads stdin when omitted.",
    )
    parser.add_argument(
        "--algorithm",
        choices=ALGORITHMS,
        default="sha256",
        help="Hash algorithm to use. Defaults to sha256.",
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=DEFAULT_CHUNK_SIZE,
        help="Read size in bytes for incremental hashing.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Write machine-readable JSON instead of plain text.",
    )
    return parser


def run(args: argparse.Namespace, stdin: BinaryIO, stdout) -> int:
    if args.chunk_size <= 0:
        raise ValueError("chunk size must be a positive integer")

    rows: list[dict[str, str]] = []
    if args.paths:
        for path in args.paths:
            rows.append(
                {
                    "source": str(path),
                    "algorithm": args.algorithm,
                    "digest": hash_path(path, args.algorithm, args.chunk_size),
                }
            )
    else:
        rows.append(
            {
                "source": "-",
                "algorithm": args.algorithm,
                "digest": hash_stream(stdin, args.algorithm, args.chunk_size),
            }
        )

    if args.json:
        json.dump(rows, stdout, indent=2)
        stdout.write("\n")
    else:
        for row in rows:
            stdout.write(f"{row['algorithm']}  {row['digest']}  {row['source']}\n")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return run(args, sys.stdin.buffer, sys.stdout)


if __name__ == "__main__":
    raise SystemExit(main())
