#!/data/data/duckyal.KaguraX/files/usr/bin/bash
# ============================================================================
# proot_env.sh —— proot 运行环境自愈（幂等，可安全重复执行）
#
# 由 App 的 AssetsUtils 释放到 ~/，init_container.sh / start.sh /
# MainActivity(终端/更新/初始化) / AdbPairPanel(ADB 配对) 统一 source 它。
#
# 解决报错：
#   CANNOT LINK EXECUTABLE ".../usr/bin/proot": library "libtalloc.so.2" not found
#   CANNOT LINK EXECUTABLE ".../usr/bin/bash": library "libandroid-support.so" not found
#
# 根因（fork 改包名，bootstrap 内所有 ELF 的 DT_RUNPATH 仍是官方前缀
#   /data/data/com.termux/files/usr/lib，真实前缀是本包名）：
#   proot-distro 启动 proot 时构造「干净环境」（不含 LD_LIBRARY_PATH），
#   ELF 二进制找不到动态库直接 CANNOT LINK。直接敲 proot --version 正常，
#   是因为 Termux shell 自带 LD_LIBRARY_PATH=$PREFIX/lib；proot-distro 不继承。
#
# 修复方案（与 TermuxInstaller.ensureProotWrapper / ensureProotRunpath 统一）：
#   - App 启动时已把 proot 备份为 proot-real，并用 patchelf 把其 DT_RUNPATH 改为
#     本包名前缀 → proot-real 不依赖 LD_LIBRARY_PATH 即可启动，也不污染容器。
#   - 本脚本确保 wrapper（$PREFIX/bin/proot-as）存在且用 /system/bin/sh 作解释器
#     （Android 自带、静态链接，干净环境下可运行），exec proot-real，
#     并导出 PROOT_LOADER / PROOT_TMP_DIR（覆盖二进制内写死的官方路径），
#     最后通过 PD_PROOT_BIN（proot-distro 官方支持的 proot 覆盖机制）让
#     proot-distro 一律走 wrapper。
#   - 注意：wrapper 绝不能以 $PREFIX/bin/bash 为解释器（干净环境下 bash 自身
#     缺 libandroid-support.so 起不来），也不能导出 LD_LIBRARY_PATH（会随 proot
#     透传进容器，让容器内 glibc 程序误加载宿主库）。本脚本会检测旧版 wrapper
#     并自动重写为 /system/bin/sh 版。
#   - 2026-08 修复：删除「干净环境验证失败 → apt-get reinstall proot」逻辑——
#     重装后的 proot DT_RUNPATH 依旧是官方前缀，根本治不了本；且重装会覆盖
#     App 已生成的 wrapper，历史上还曾触发 bash CANNOT LINK 连环失败。
#   - 2026-09 修复：旧 fork/改名迁移(如 ASOnmyoji→KaguraX 的数据迁移或旧版恢复包)
#     会残留内嵌旧包名绝对路径的 wrapper(如指向 duckyal.ASOnmyoji.termux)。
#     它首行与 PROOT_NO_SECCOMP 标记均正常，旧版只凭这两点判断永不重写，exec 即报
#     ".../proot: inaccessible or not found"。重写判定额外校验 wrapper 内嵌路径
#     是否为当前 $PREFIX_DIR，不是则强制重写(见下方第 1 步)。
# ============================================================================

PREFIX_DIR=/data/data/duckyal.KaguraX/files/usr
WRAPPER="$PREFIX_DIR/bin/proot-as"

# ---------- 0. 首次安装等待 App 备份 proot → proot-real 并修复 RUNPATH ----------
#    全新安装场景: pkg install proot 完成后本脚本立即运行, 此刻 proot 还是真 ELF,
#    proot-real 尚不存在(App 的 ensureProotWrapper 只在 bootstrap 安装时跑过一次,
#    那时 proot 还没装, 建不出 wrapper)。MainActivity「一键初始化」会启动轮询,
#    检测到 proot 落盘后自动备份成 proot-real 并修复 DT_RUNPATH。
#    这里最多等 30 秒, 让 wrapper 优先走 proot-real 分支(不导出 LD_LIBRARY_PATH,
#    避免宿主库污染容器); 超时才退化为 fallback(仅提示, 容器内已 unset 兜底)。
if [ -x "$PREFIX_DIR/bin/proot" ] && [ ! -x "$PREFIX_DIR/bin/proot-real" ]; then
  echo "[proot_env] 首次安装检测: 等待 App 备份 proot→proot-real 并修复 RUNPATH(最长 30 秒)…"
  waited=0
  while [ "$waited" -lt 30 ] && [ ! -x "$PREFIX_DIR/bin/proot-real" ]; do
    sleep 1
    waited=$((waited + 1))
  done
  if [ -x "$PREFIX_DIR/bin/proot-real" ]; then
    echo "[proot_env] App 已完成 proot-real 备份与 RUNPATH 修复"
  else
    echo "[proot_env] 等待超时: proot-real 未生成, wrapper 将回退真 proot(容器内已 unset LD_LIBRARY_PATH 兜底)"
  fi
fi

# ---------- 1. 确保 wrapper 存在且为 /system/bin/sh 版（旧 bash 版自动重写） ----------
#    proot / proot-real 任一存在即可生成 wrapper(在线装 proot 前、恢复包场景下
#    proot-real 可能已就位)。重写判定除「首行 /system/bin/sh + PROOT_NO_SECCOMP
#    标记」外，还须校验 wrapper 内嵌路径是当前 $PREFIX_DIR —— 旧 fork/改名迁移
#    (如 ASOnmyoji→KaguraX 数据迁移、旧版恢复包)会残留内嵌旧包名绝对路径的
#    wrapper，标记检测识别不了，exec 时直接报 ".../proot: inaccessible or not
#    found" (2026-09 修复)。
if [ -x "$PREFIX_DIR/bin/proot" ] || [ -x "$PREFIX_DIR/bin/proot-real" ]; then
  NEED_REWRITE=1
  if [ -f "$WRAPPER" ]; then
    IFS= read -r firstline < "$WRAPPER" 2>/dev/null || NEED_REWRITE=1
    case "$firstline" in
      "#!/system/bin/sh")
        content=$(<"$WRAPPER") 2>/dev/null || content=""
        case "$content" in
          *PROOT_NO_SECCOMP*) NEED_REWRITE=0 ;;
        esac
        case "$content" in
          *"$PREFIX_DIR"*) ;;          # 内嵌路径仍是当前前缀 → 可复用
          *) NEED_REWRITE=1 ;;         # 旧包名/改名残留 → 强制重写
        esac
        ;;
    esac
  fi

  if [ "$NEED_REWRITE" = 1 ]; then
    cat > "$WRAPPER" <<'WRAP'
#!/system/bin/sh
# proot wrapper（由 proot_env.sh 自动生成）：干净环境(无 LD_LIBRARY_PATH)下也可启动。
# 优先 exec proot-real（DT_RUNPATH 已由 App 启动时修为本包名前缀，不依赖
# LD_LIBRARY_PATH，也不会把宿主库路径带进容器）；proot-real 缺失时回退真 proot
# （此时仍需 LD_LIBRARY_PATH，容器内脚本已 unset，污染可控）。
export PROOT_LOADER=/data/data/duckyal.KaguraX/files/usr/libexec/proot/loader
export PROOT_TMP_DIR=${PROOT_TMP_DIR:-/data/data/duckyal.KaguraX/files/usr/tmp}
# 禁用 seccomp 过滤器: 部分 ROM(VCN/热点/加速器环境)下 proot 的 seccomp 误拦
# socket/connect 等网络 syscall, 导致容器内 TCP/UDP 全不通(curl http_code=000)。
export PROOT_NO_SECCOMP=1
if [ -x /data/data/duckyal.KaguraX/files/usr/bin/proot-real ]; then
  exec /data/data/duckyal.KaguraX/files/usr/bin/proot-real "$@"
fi
export LD_LIBRARY_PATH=/data/data/duckyal.KaguraX/files/usr/lib
exec /data/data/duckyal.KaguraX/files/usr/bin/proot "$@"
WRAP
    chmod 700 "$WRAPPER" 2>/dev/null || true
    echo "[proot_env] 已生成/重写 /system/bin/sh 版 proot wrapper: $WRAPPER"
  fi

  # ---------- 2. 干净环境下验证 wrapper 链（失败仅提示，不阻断） ----------
  #    wrapper → proot-real 的 RUNPATH 修复由 App 启动时(ensureProotRunpath)完成；
  #    此处无法补 ELF，失败时提示重启 App 让其重新修复。
  if ! env -i HOME="$HOME" PATH="$PATH" TERM="$TERM" "$WRAPPER" --version >/dev/null 2>&1; then
    echo "[proot_env] 干净环境下 wrapper 无法运行(proot-real 的 RUNPATH 可能未修复),建议重启 App 使其重新修复"
  fi

  # ---------- 3. 让 proot-distro 一律走 wrapper ----------
  export PD_PROOT_BIN="$WRAPPER"
fi
