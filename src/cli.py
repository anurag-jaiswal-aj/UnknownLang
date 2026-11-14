"""Command-line interface for UnknownLang."""

import sys


def main():
    """Entry point for the CLI."""
    print("UnknownLang CLI - Work in progress")
    print("Usage: unknownlang <command>")
    print("")
    print("Commands:")
    print("  generate  Generate a new programming language")
    print("  evaluate  Evaluate a model on a challenge")
    print("  benchmark Run a full benchmark")
    print("  demo      Run a demo workflow")
    print("")
    return 0


if __name__ == "__main__":
    sys.exit(main())
