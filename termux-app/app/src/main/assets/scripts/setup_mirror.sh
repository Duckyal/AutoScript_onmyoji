#!/data/data/duckyal.KaguraX/files/usr/bin/bash
# ============================================================================
# setup_mirror.sh —— 将 Termux apt 源切换为清华镜像(由「一键初始化」最先调用)
#
# 为什么需要它:
#   官方源 packages.termux.dev / packages-cf.termux.dev 在国内访问极不稳定,
#   pkg update / pkg install 经常超时失败,必须先换源。
#
# 做法:
#   1. 备份原 sources.list → sources.list.bak
#   2. 写入清华源 mirrors.tuna.tsinghua.edu.cn/termux/apt/termux-main
#   3. 清掉 sources.list.d 下的其它配置,避免多个源互相干扰
#   4. 修复 GPG NO_PUBKEY:内置 bootstrap 的 termux-keyring(旧版)缺少 Termux
#      2025 年启用的新签名 key(指纹 CC72CF8BA7DBFA0182877D045A897D96E57CF20C),
#      apt update 验签失败、仓库被禁用。App 已把官方 termux-autobuilds.gpg(内含
#      该 key)作为 assets 内置、由 AssetsUtils 释放到 ~/termux-autobuilds.gpg,
#      这里优先本地 cp 到 $PREFIX/etc/apt/trusted.gpg.d/(零网络依赖,恢复包场景
#      也能修复),本地缺失时才在线下载兜底。文件与 termux-keyring 包安装的符号
#      链接同名,之后装新版 termux-keyring 也不冲突。
#
# 幂等:重复执行也只是把源写成清华 + 刷新 key,不报错。
# ============================================================================

MIRROR_URL="https://mirrors.tuna.tsinghua.edu.cn/termux/apt/termux-main"
SOURCES_LIST="$PREFIX/etc/apt/sources.list"
SOURCES_D="$PREFIX/etc/apt/sources.list.d"

# 1. 备份原配置(只备份一次,不覆盖已有 .bak)
if [ -f "$SOURCES_LIST" ] && [ ! -f "$SOURCES_LIST.bak" ]; then
    cp "$SOURCES_LIST" "$SOURCES_LIST.bak"
fi

# 2. 写入清华源
mkdir -p "$SOURCES_D"
cat > "$SOURCES_LIST" <<EOF
# Termux 清华镜像源(由 App 一键初始化自动配置,原配置见 sources.list.bak)
deb $MIRROR_URL stable main
EOF

# 3. 清理 sources.list.d 下的旧配置(避免多源冲突导致 pkg 报错)
rm -f "$SOURCES_D/"*.list "$SOURCES_D/"*.sources 2>/dev/null || true

# 4. 修复 GPG NO_PUBKEY(见文件头说明):
#    优先用 App 内置、已由 AssetsUtils 释放到 ~/termux-autobuilds.gpg 的 key,
#    本地 cp 零网络依赖(恢复包/纯离线场景也可靠);本地缺失时才在线下载兜底。
KEY_FILE="$PREFIX/etc/apt/trusted.gpg.d/termux-autobuilds.gpg"
KEY_OK=0
mkdir -p "$PREFIX/etc/apt/trusted.gpg.d"

KEY_LOCAL="$HOME/termux-autobuilds.gpg"
if [ -f "$KEY_LOCAL" ] && cp -f "$KEY_LOCAL" "$KEY_FILE" 2>/dev/null; then
    KEY_OK=1
    echo "[setup_mirror] 已用内置签名 key 修复信任(本地 ~/termux-autobuilds.gpg)"
fi

# 在线下载兜底:先用临时文件再 mv 原子替换,失败不会留下空文件;失败不阻断后续。
if [ "$KEY_OK" != "1" ]; then
    KEY_TMP="$KEY_FILE.tmp"

    # curl 统一选项:--connect-timeout 只限制 TCP 连接,连接建立后传输挂起(慢网/被墙)
    # 会无限等待,必须再加 --max-time 整体超时(含下载);--retry 让每个源自动重试,
    # 避免单个源偶发失败直接判死。
    CURL_OPTS="-fsSL --connect-timeout 15 --max-time 60 --retry 2 --retry-delay 2 --retry-all-errors"

    # 候选源按可达性排序:官方 raw 直连 → jsDelivr CDN(国内可达性好) → github.com
    # 直连 → 各加速代理。任一成功即停,全部失败仅警告(apt update 可能报 NO_PUBKEY)。
    KEY_URLS=(
        "https://raw.githubusercontent.com/termux/termux-packages/master/packages/termux-keyring/termux-autobuilds.gpg"
        "https://cdn.jsdelivr.net/gh/termux/termux-packages@master/packages/termux-keyring/termux-autobuilds.gpg"
        "https://github.com/termux/termux-packages/raw/master/packages/termux-keyring/termux-autobuilds.gpg"
        "https://ghfast.top/https://raw.githubusercontent.com/termux/termux-packages/master/packages/termux-keyring/termux-autobuilds.gpg"
        "https://gh-proxy.com/https://raw.githubusercontent.com/termux/termux-packages/master/packages/termux-keyring/termux-autobuilds.gpg"
        "https://ghproxy.net/https://raw.githubusercontent.com/termux/termux-packages/master/packages/termux-keyring/termux-autobuilds.gpg"
    )
    for key_url in "${KEY_URLS[@]}"; do
        echo "[setup_mirror] 下载 Termux 签名 key: $key_url"
        if curl $CURL_OPTS -o "$KEY_TMP" "$key_url"; then
            mv -f "$KEY_TMP" "$KEY_FILE"
            KEY_OK=1
            break
        fi
        rm -f "$KEY_TMP"
        echo "[setup_mirror] 该源下载失败,换下一个..."
    done
    if [ "$KEY_OK" = "1" ]; then
        echo "[setup_mirror] Termux 签名 key 已就绪(修复 NO_PUBKEY)"
    else
        echo "[setup_mirror] 警告:key 下载失败(6 个源均超时),apt update 可能仍报 NO_PUBKEY;可稍后重试一键初始化"
    fi
fi

echo "[setup_mirror] Termux 源已切换为清华镜像: $MIRROR_URL"
