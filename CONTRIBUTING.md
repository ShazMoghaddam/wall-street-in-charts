# Contributing

Thanks for your interest. Issues and pull requests are welcome, especially data corrections.

## Getting set up

```bash
pip install -e ".[dev]"
cp .env.example .env   # add your own SEC contact email and FRED API key
python data/fetch.py
```

## Before you open a pull request

```bash
ruff check .
ruff format .
pytest
```

CI runs the same checks. Tests run offline against `data/processed/`, so they never need your secrets.

## Data corrections

If a figure looks wrong, please open an issue with the firm, the period, the value you expected and a link to the filing. Hand-made tables live in `data/manual/` and every row there needs a source.

## Style

- Plain, clear names and short docstrings that explain why, not just what.
- Keep secrets out of code, commits and logs.
