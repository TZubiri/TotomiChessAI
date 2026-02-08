import argparse

from chess import convert_legacy_savefile_to_pgn


def parse_args():
    parser = argparse.ArgumentParser(description="Convert legacy chess save logs to PGN")
    parser.add_argument("input_path", help="Path to legacy save file (for example chess_save.txt)")
    parser.add_argument(
        "output_path",
        nargs="?",
        default=None,
        help="Destination PGN path (defaults to input filename with .pgn extension)",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    output_path = convert_legacy_savefile_to_pgn(args.input_path, args.output_path)
    print(f"Converted to {output_path}")


if __name__ == "__main__":
    main()
