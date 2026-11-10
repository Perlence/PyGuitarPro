@_:
    just --list

test *args:
    uv run --no-default-groups --group tests pytest {{ args }}

lint:
    uv run --no-default-groups --group pre-commit pre-commit run --all-files

docs:
    uv run --no-default-groups --group docs sphinx-build -M html docs/ docs/_build

docs-serve:
    uv run --no-default-groups --group docs --with sphinx-autobuild sphinx-autobuild -M html docs/ docs/_build
