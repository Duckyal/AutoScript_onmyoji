#!/bin/bash

cd "$(dirname "$0")"

echo "=== 同步 static 目录到 github.io ==="
echo ""

echo "1. 创建临时分支 gh-pages..."
git subtree split --prefix=static -b gh-pages

echo ""
echo "2. 推送到 github.io 仓库..."
git push frontend gh-pages:main --force

echo ""
echo "3. 清理临时分支..."
git branch -D gh-pages

echo ""
echo "=== 同步完成 ==="
echo ""
echo "访问地址: https://duckyal.github.io"
