# UnknownLang

Adaptive AI reasoning benchmark platform that evaluates whether AI models can learn and reason within previously unseen, procedurally generated programming languages.

## Overview

UnknownLang generates controlled programming-language environments, provides specifications to AI models, evaluates their generated programs using independent deterministic interpreters, and measures their ability to generalize beyond provided examples.

## Features

- **Procedural Language Generation**: Creates entirely new programming languages on demand
- **Deterministic Execution**: Same seed always produces identical results
- **Independent Test Oracle**: Separate code path for verification
- **Benchmark Evaluation**: Standardized scoring and metrics
- **Zero Cost**: Uses free and open-source technologies

## Architecture

- **Backend**: Python + FastAPI
- **Parser**: Lark for grammar parsing
- **Frontend**: React + Vite
- **Database**: SQLite (post-MVP)

## Quick Start

```bash
# Install dependencies
pip install -e .

# Run the demo
unknownlang demo
```

## Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src
```

## License

MIT License
