#!/bin/bash
# Publica una versión nueva: ./scripts/release.sh 0.2.0
# Los usuarios la reciben con: hhcap update
set -euo pipefail
cd "$(dirname "$0")/.."
v="${1:?uso: scripts/release.sh X.Y.Z}"
[[ "$v" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || { echo "versión inválida: $v"; exit 1; }
[ -z "$(git status --porcelain)" ] || { echo "hay cambios sin commitear"; exit 1; }
python3 -m unittest discover -s tests -q
sed -i '' "s/^__version__ = .*/__version__ = \"$v\"/" hhcap/__init__.py
sed -i '' "s/^version = .*/version = \"$v\"/" pyproject.toml
sed -i '' "s/tag: \"v[0-9.]*\"/tag: \"v$v\"/" Formula/hhcap.rb
git commit -qam "hhcap $v"
git tag "v$v"
git push -q origin HEAD "v$v"
echo "Publicado v$v. Los usuarios actualizan con: hhcap update"
