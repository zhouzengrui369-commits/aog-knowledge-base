#!/usr/bin/env bash
# Postbuild: rename URL-encoded city files to real Chinese filenames
#   - Next.js output:export 默认把 B-北京大兴.html 编码成 B-%E5%8C%97%E4%BA%AC%E5%A4%A7%E5%85%B4.html
#   - CloudBase 静态托管对 URL-encoded file 名支持不全, 公网访问 /city/C-重庆江北 返 404
#   - 解码后用真实中文名 (B-北京大兴.html) 公网能正常 200
set -euo pipefail

OUT="${1:-out}"
if [ ! -d "$OUT" ]; then
    echo "[postbuild] $OUT/ 不存在, 跳过"
    exit 0
fi

# 1. Rename city/ 下的 URL 编码 file 为真实中文名
if [ -d "$OUT/city" ]; then
    cd "$OUT/city"
    renamed=0
    failed=0
    for f in *.html *.txt; do
        [ -f "$f" ] || continue
        # 解码 (Python 比 bash 安全, 处理 %E5 %E4 这种多字节)
        decoded=$(python3 -c "import sys, urllib.parse; print(urllib.parse.unquote(sys.argv[1]))" "$f")
        if [ "$f" != "$decoded" ]; then
            if mv "$f" "$decoded" 2>/dev/null; then
                renamed=$((renamed + 1))
            else
                failed=$((failed + 1))
                echo "[postbuild] WARN: rename fail $f → $decoded"
            fi
        fi
    done
    cd - > /dev/null
    echo "[postbuild] ✓ city/ rename: $renamed 个 file 改成真实中文名, $failed 失败"
fi

# 2. Generate _redirects (Netlify 风格, CloudBase 不支持, 备选)
{
    echo "# AOG 知识库 — CloudBase 静态托管 _redirects"
    echo "# 作用: lowercase city URL (c-重庆江北) → uppercase (C-重庆江北)"
    echo ""
    for letter in a b c d e f g h i j k l m n o p q r s t u v w x y z; do
        upper=$(echo "$letter" | tr '[:lower:]' '[:upper:]')
        echo "/city/${letter}-:code   /city/${upper}-:code   307"
    done
} > "$OUT/_redirects"
echo "[postbuild] ✓ $OUT/_redirects 已生成 (26 条规则)"

# 3. Verify: city/ 下 223 个 file 全部是真实中文名 (非 % 开头)
if [ -d "$OUT/city" ]; then
    total=$(find "$OUT/city" -name "*.html" | wc -l | tr -d ' ')
    url_encoded=$(find "$OUT/city" -name "*.html" | grep -c '%' || echo 0)
    real_cn=$(find "$OUT/city" -name "*.html" | python3 -c "
import sys, urllib.parse
files = [l.strip() for l in sys.stdin if l.strip()]
real = [f for f in files if any(ord(c) > 127 for c in urllib.parse.unquote(f).replace('.html','')) and '%' not in f]
print(len(real))
")
    echo "[postbuild] verify city/: 总 ${total} file, URL 编码 ${url_encoded}, 真实中文 ${real_cn}"
    if [ "$total" != "223" ]; then
        echo "[postbuild] ⚠️  WARNING: city/ 总数 != 223 (期望 223 城市)"
    fi
    if [ "$url_encoded" != "0" ]; then
        echo "[postbuild] ⚠️  WARNING: city/ 仍有 URL 编码 file, 上面 rename 失败"
    fi
fi
