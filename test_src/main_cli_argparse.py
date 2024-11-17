import argparse
from datetime import datetime


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--print",
        help="Something to print",
        default="Hello now is: ",
    )
    return parser.parse_args()


def main(args: argparse.Namespace) -> None:
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    print(f"{args.print} {timestamp} thats timestamp!")


if __name__ == "__main__":
    args = parse_args()
    main(args)
