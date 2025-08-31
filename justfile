@_:
    just --list

test *args:
    uv run --group tests pytest {{ args }}

lint:
    uv run --group pre-commit pre-commit run --all-files

docs:
    uv run --group docs sphinx-build -M html docs/ docs/_build

docs-serve:
    uv run --group docs --with sphinx-autobuild sphinx-autobuild -M html docs/ docs/_build
