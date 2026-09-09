#!/data/data/duckyal.KaguraX/files/usr/bin/bash
# ============================================================================
# restore_container.sh —— 从「容器恢复包」快速恢复 Debian 容器(免在线安装)
#
# 背景：在线初始化(proot-distro install + 容器内 apt/uv/git)在国内网络慢且易受
#    DNS/断网影响；恢复包方案把「已初始化好的 rootfs + /root/app/.venv + 宿主
#    proot 运行时」打包压缩, 上传 GitHub Release, 本脚本下载并解压即用,
#    把初始化从「10-30 分钟在线安装」压缩到「下载一次 + 解压几分钟」。
#
# 调用位置：MainActivity「一键初始化」命令链, pkg install proot 之后、
#   proot-distro install 之前。本脚本失败(exit 2, 无恢复包)不阻断,
#   由命令链继续走在线安装兜底。
#
# 恢复包(需与脚本内 URL 一致, 用户可自定义 ~/restore_url.conf):
#   restore_container.tar.gz  容器 rootfs(含 /root/app 代码与 .venv 依赖)
#   restore_proot.tar.gz      宿主 proot 运行时(proot-real/loader/wrapper)
#   两者归档内统一带 usr/ 前缀, 解压时 --strip-components=1 剥掉后落到 $PREFIX。
#
# 用法:
#   ~/restore_container.sh           自动检测: 容器已就绪则跳过;
#                                    否则找本地包 → 下载 → 解压到 $PREFIX
# ============================================================================

set -u

PREFIX_DIR=/data/data/duckyal.KaguraX/files/usr
HOME_DIR=/data/data/duckyal.KaguraX/files/home
ROOTFS="$PREFIX_DIR/var/lib/proot-distro/containers/debian/rootfs"

# ---------- 1. 容器已就绪则直接跳过(重跑/已恢复场景) ----------
if [ -f "$ROOTFS/bin/bash" ] && [ -f "$ROOTFS/etc/os-release" ]; then
  echo "[restore] 容器已就绪, 跳过恢复包"
  exit 0
fi

# ---------- 2. 定位恢复包(本地 > 自定义 URL > 内置 URL) ----------
CONTAINER_PKG="$HOME_DIR/restore_container.tar.gz"
PROOT_PKG="$HOME_DIR/restore_proot.tar.gz"

RESTORE_URL=""
[ -f "$HOME_DIR/restore_url.conf" ] && RESTORE_URL=$(head -1 "$HOME_DIR/restore_url.conf")
[ -z "$RESTORE_URL" ] && RESTORE_URL="https://github.com/Duckyal/KaguraX/releases/download/container-v1/restore_container.tar.gz"

dl() { # $1=url $2=out
  local url="$1" out="$2"
  for base in "" "https://ghfast.top/" "https://gh-proxy.com/"; do
    echo "[restore] 下载尝试: $base$url"
    if curl -fL --connect-timeout 15 -m 600 -o "$out.part" "$base$url"; then
      mv "$out.part" "$out"
      return 0
    fi
    rm -f "$out.part"
  done
  return 1
}

if [ ! -f "$CONTAINER_PKG" ]; then
  echo "[restore] 未找到本地 $CONTAINER_PKG"
  # 容器包 URL 去掉文件名即 proot 包所在目录
  PROOT_URL="${RESTORE_URL%/restore_container.tar.gz}/restore_proot.tar.gz"
  if ! dl "$RESTORE_URL" "$CONTAINER_PKG"; then
    echo "[restore] 恢复包下载失败, 将走在线安装(较慢)"
    exit 2
  fi
fi

if [ ! -f "$PROOT_PKG" ]; then
  # 容器包已有(本地放置)时, proot 包仍可能缺失, 尝试按目录规则下载
  PROOT_URL="${RESTORE_URL%/restore_container.tar.gz}/restore_proot.tar.gz"
  dl "$PROOT_URL" "$PROOT_PKG" || echo "[restore] proot 运行时包缺失(可继续, 由 proot_env.sh 兜底)"
fi

# ---------- 3. 解压到 $PREFIX ----------
# 注意: 恢复包归档内统一带 usr/ 前缀(打包自 termux 根目录的 usr 目录),
# 必须 --strip-components=1 剥掉, 否则会解出 $PREFIX/usr/usr/... 嵌套目录,
# 校验必然失败。旧版脚本未 strip 会在设备上留下 $PREFIX/usr/... 错误残留,
# 解压前顺手清理(这些路径都是恢复包专属产物, 删除安全)。
for p in "$PREFIX_DIR/usr/var/lib/proot-distro" "$PREFIX_DIR/usr/bin/proot-real" \
         "$PREFIX_DIR/usr/bin/proot-as" "$PREFIX_DIR/usr/libexec/proot"; do
  [ -e "$p" ] && { echo "[restore] 清理旧版错误解压残留: $p"; rm -rf "$p"; }
done
echo "[restore] 解压容器恢复包 → $PREFIX_DIR (约 1-3 分钟)…"
tar -xzf "$CONTAINER_PKG" -C "$PREFIX_DIR" --strip-components=1
if [ -f "$PROOT_PKG" ]; then
  echo "[restore] 解压 proot 运行时…"
  tar -xzf "$PROOT_PKG" -C "$PREFIX_DIR" --strip-components=1
fi

# ---------- 4. 校验 ----------
if [ -f "$ROOTFS/bin/bash" ] && [ -x "$PREFIX_DIR/bin/proot-real" ]; then
  echo "[restore] 恢复包校验通过: 容器 + proot 运行时就绪"
  exit 0
fi
echo "[restore] 恢复包解压后校验失败, 将走在线安装兜底"
exit 2
