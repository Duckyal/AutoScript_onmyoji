#!/data/data/duckyal.KaguraX/files/usr/bin/bash
# ============================================================================
# start.sh —— 启动 KaguraX 项目（由 MainActivity「启动项目」按钮调用）
#
# 整体思路：
#   1. 先登录 Debian 容器（proot-distro login debian）。proot 与 Android 共享
#      网络栈，容器内启动的 HTTP 服务可直接监听 127.0.0.1:8000，
#      App 的 WebView 直连 http://127.0.0.1:8000 即可访问。
#   2. 在容器内进入项目目录 /root/app，用 uv（项目要求的包管理器）运行：
#        uv run python main.py --host 127.0.0.1 --port 8000
#
# 关键约定：
#   - 依赖只通过 uv 管理（uv sync / uv run），禁止 pip3 install -r 或系统 python3。
#   - uv 会自动下载满足 pyproject.toml（Python 3.10-3.13）的独立 Python，
#     无需在容器里 apt 安装 python3。
#   - 该脚本由 App 通过 TermuxRunner 以 bash -c "~/start.sh" 方式调用，
#     因此 shebang 必须是 Termux bash 的绝对路径。
#
# 修复日志：
#   2026-09  启动前 .venv 依赖真实导入校验：之前中断的 uv sync 可能在
#            site-packages 留空包目录(如 fastapi/), uv 按 dist-info 标记认为已装
#            好不重装, import 报 unknown location。校验失败自动重建 .venv(下方)。
# ============================================================================

# proot 运行环境自愈（libtalloc / PD_PROOT_BIN，详见 proot_env.sh 头注释）
. ~/proot_env.sh 2>/dev/null || true

# 版本自检标记：便于确认设备 ~/start.sh 是否已更新(旧版无此行)
echo "[start.sh] v2 (2026-09-07: .venv 导入自检+自动重建)"

proot-distro login debian -- bash -c '
  # 固定容器内 PATH(剔除 proot-distro 追加的宿主 Termux bin),命令一律走容器内版本；
  # 同时清掉 proot_env.sh wrapper 透传进来的宿主 LD_LIBRARY_PATH,避免误加载宿主库。
  export PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:$HOME/.local/bin"
  unset LD_LIBRARY_PATH
  if [ ! -d /root/app ]; then
    echo "[start.sh] 项目尚未初始化:容器内 /root/app 不存在。"
    echo "[start.sh] 请先在 App 主界面点击「一键初始化/初始化项目」完成项目安装(约 5-10 分钟),再点「启动项目」。"
    exit 1
  fi
  cd /root/app
  # 2026-09: 之前中断的 uv sync 可能在 .venv 留下空包目录(如 fastapi/), uv 按
  # dist-info 标记认为依赖齐全不会重装, import 报 unknown location。启动前真实
  # 导入校验, 不通过则重建 .venv(uv 缓存完好时重装较快)。
  if ! .venv/bin/python -c "import fastapi, uvicorn, uiautomator2" 2>/dev/null; then
    echo "[start.sh] 检测到 .venv 依赖不完整(疑似之前中断安装残留),正在重建虚拟环境…"
    rm -rf /root/app/.venv
    # 预清理 uv 易损缓存(archive-v0=解压目录/builds-v0=构建隔离), 防止中断残留
    # 损坏条目让 uv sync 构建 antlr4 等 sdist 时报 No such file; wheels 保留可少下载。
    rm -rf /root/.cache/uv/archive-v0 /root/.cache/uv/builds-v0 \
           /root/.cache/uv/archive /root/.cache/uv/builds 2>/dev/null || true
    export UV_DEFAULT_INDEX="https://pypi.tuna.tsinghua.edu.cn/simple"
    export UV_LINK_MODE=copy
    export UV_CONCURRENT_BUILDS=1
    export UV_CONCURRENT_INSTALLS=1
    uv sync
    if ! .venv/bin/python -c "import fastapi, uvicorn, uiautomator2" 2>/dev/null; then
      echo "[start.sh] .venv 重建后依赖校验仍失败,请重新执行「一键初始化」"
      exit 1
    fi
  fi
  uv run python main.py --host 127.0.0.1 --port 8000
' || {
  echo "[start.sh] 容器登录或项目启动失败，请检查上方终端输出定位原因。"
  exit 1
}
