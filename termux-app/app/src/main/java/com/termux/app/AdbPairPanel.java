package com.termux.app;

import com.termux.R;

import android.app.Activity;
import android.content.Context;
import android.content.SharedPreferences;
import android.graphics.Color;
import android.os.Handler;
import android.os.Looper;
import android.view.View;
import android.widget.Button;
import android.widget.EditText;
import android.widget.TextView;
import android.widget.Toast;

import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.util.Map;

/**
 * AdbPairPanel —— 主界面内嵌的 ADB 无线配对面板（取代原弹窗，逻辑直接铺在主界面）。
 *
 * 它把原 AdbPairDialog 的界面与逻辑全部搬到 MainActivity 的卡片上：
 *   - 顶部状态条：App 进程内执行 adb devices，实时显示
 *     「已连接：<ip:port>」（绿）/「未连接 · 请先首次配对」/「未连接 · 请点击连接」等
 *   - 「连接 / 首次配对」互斥切换：一次只展开一个区块（默认展开「连接」），
 *     切换标题高亮当前区块，避免连接输入框与配对输入框同时占页面
 *   - 「连接」区块：连接地址 + 「连接」按钮，记住上次地址自动填入
 *   - 「首次配对」区块：配对地址 + 6 位配对码 + 「配对」按钮
 *     （配对码每次都会变，不保存；配对成功后自动用同 IP:5555 发起连接）
 *
 * 设计要点（沿用原 AdbPairDialog）：
 *   1. 状态检测用 Runtime.exec 在 App 进程内执行 adb devices，只认实时事实、不做缓存；
 *   2. 配对/连接全程后台静默执行（Runtime.exec），结果用 Toast 反馈，不再跳转终端；
 *   3. 面板是 Activity 布局的一部分，结果 Toast 直接浮在页面上方，不存在被弹窗挡住的问题；
 *   4. MainActivity.onResume 时调用 {@link #refresh()}，回到主界面即重新检测连接状态。
 *
 * 构造后自动绑定主界面 activity_main.xml 中 ADB 区块的控件并做一次状态检测。
 */
public final class AdbPairPanel {

    /** Termux 自带 bash 的绝对路径（Runtime.exec 不加载 Termux 环境，需显式指定） */
    private static final String TERMUX_BASH = "/data/data/duckyal.KaguraX/files/usr/bin/bash";

    /** Termux 可执行目录（proot-distro 等命令所在的 PATH 前缀） */
    private static final String TERMUX_BIN = "/data/data/duckyal.KaguraX/files/usr/bin";

    /** Termux 前缀目录（含 lib/tmp 等） */
    private static final String TERMUX_PREFIX = "/data/data/duckyal.KaguraX/files/usr";

    /** Termux 主目录（bash 的 HOME） */
    private static final String TERMUX_HOME = "/data/data/duckyal.KaguraX/files/home";

    /** SharedPreferences 文件名（App 私有，无需权限；沿用弹窗版本，旧数据可直接续用） */
    private static final String PREFS_NAME = "adb_pair_prefs";

    /** 记住的连接地址 key */
    private static final String KEY_LAST_CONNECT_ADDRESS = "last_connect_address";

    /** 是否完成过首次配对 key（用于未连接时的引导文案与连接前的配对引导） */
    private static final String KEY_HAS_PAIRED = "has_paired";

    /**
     * 2026-09 修正：Android 11+ 无线调试的「连接端口」并非固定 5555，而是每次开关
     * 无线调试都会变化的随机端口（被控端设置页实时显示 IP:端口）。所以连接一律按被控端
     * 当前显示填写：本类只记住上次完整地址以复用 IP，绝不默认补 5555，避免“连不上反复
     * 开关几次才能好”的假象（端口不对时 connect 会 connection refused）。
     */

    /** Runtime.exec 等待 adb devices 输出的最长时间（毫秒），防止进程挂起卡死子线程 */
    private static final long EXEC_TIMEOUT_MS = 20000;

    /** Runtime.exec 等待配对/连接命令的最长时间（毫秒）：adb 网络操作可能稍慢 */
    private static final long OP_TIMEOUT_MS = 30000;

    /** adb connect 的最大尝试次数（含首次）：配对刚成功后立即 connect 偶发失败，重试兜底 */
    private static final int MAX_CONNECT_ATTEMPTS = 3;

    /** 两次 connect 尝试之间的间隔（毫秒） */
    private static final long CONNECT_RETRY_DELAY_MS = 2000;

    /** connect 后等待设备出现在 adb devices 的固定时长（秒，与 connect 同会话内 sleep） */
    private static final String CONNECT_SETTLE_SLEEP_S = "1.5";

    /** 状态刷新序号：用于丢弃过期的状态检测结果（避免慢线程覆盖新结果） */
    private int mStatusSeq;

    private final Activity activity;          // 页面 Activity（找控件/跑 UI）
    private final Context appContext;         // Application context（Toast/偏好，防泄漏）
    private final Handler mainHandler = new Handler(Looper.getMainLooper());

    // 控件引用（activity_main.xml ADB 区块）
    private TextView tvStatus;                // 顶部连接状态
    private Button btnConnectTab;             // 「连接」切换标题（高亮=当前区块）
    private Button btnPairTab;                // 「首次配对」切换标题
    private View layoutConnectSection;        // 日常连接区块（默认显示）
    private View layoutPairSection;           // 首次配对区块（与连接互斥，默认隐藏）
    private EditText etPairAddress;           // 配对地址
    private EditText etPairCode;              // 配对码
    private Button btnPair;                   // 「配对」按钮
    private EditText etConnectAddress;        // 连接地址
    private Button btnConnect;                // 「连接」按钮

    /**
     * 构造：绑定主界面 activity_main.xml 中 ADB 区块的全部控件、设置监听并做一次状态检测。
     * 必须在 {@code setContentView(R.layout.activity_main)} 之后调用。
     */
    public AdbPairPanel(Activity activity) {
        this.activity = activity;
        this.appContext = activity.getApplicationContext();

        bindViews(activity);
        setListeners();
        loadSavedConnectAddress();
        prefillPairAddressFromConnect();   // 用上次连接 IP 预填配对地址（仅需补系统显示的端口）
        showConnectSection();              // 默认只展开「连接」区块（标签高亮同步）
        refresh();                         // 绑定后立即检测一次连接状态
    }

    // ==================== 绑定与监听 ====================

    /** 绑定布局控件（id 与 activity_main.xml ADB 区块一一对应） */
    private void bindViews(Activity activity) {
        tvStatus = activity.findViewById(R.id.tv_adb_status);
        btnConnectTab = activity.findViewById(R.id.btn_connect_tab);
        btnPairTab = activity.findViewById(R.id.btn_pair_tab);
        layoutConnectSection = activity.findViewById(R.id.layout_connect_section);
        layoutPairSection = activity.findViewById(R.id.layout_pair_section);
        etPairAddress = activity.findViewById(R.id.et_pair_address);
        etPairCode = activity.findViewById(R.id.et_pair_code);
        btnPair = activity.findViewById(R.id.btn_pair);
        etConnectAddress = activity.findViewById(R.id.et_connect_address);
        btnConnect = activity.findViewById(R.id.btn_connect);
    }

    /** 设置监听 */
    private void setListeners() {
        btnConnectTab.setOnClickListener(v -> showConnectSection());
        btnPairTab.setOnClickListener(v -> showPairSection());
        btnPair.setOnClickListener(v -> onPairClicked());
        btnConnect.setOnClickListener(v -> onConnectClicked());
    }

    // ==================== 互斥区块切换 ====================

    /**
     * 只展开「连接」区块（日常连接）：收起配对区块，标签高亮同步。
     * 「连接 / 首次配对」互斥——一次只在页面上显示一个区块，避免页面拥挤。
     */
    private void showConnectSection() {
        layoutConnectSection.setVisibility(View.VISIBLE);
        layoutPairSection.setVisibility(View.GONE);
        styleTab(btnConnectTab, true);
        styleTab(btnPairTab, false);
    }

    /** 只展开「首次配对」区块：收起连接区块，标签高亮同步 */
    private void showPairSection() {
        layoutConnectSection.setVisibility(View.GONE);
        layoutPairSection.setVisibility(View.VISIBLE);
        styleTab(btnConnectTab, false);
        styleTab(btnPairTab, true);
    }

    /**
     * 分段控件两段的选中/未选中样式：
     * 选中=主色实心圆角块（「连接」在左、半圆角向左；「首次配对」在右、半圆角向右），
     * 未选中=透明。两段始终紧贴在凹槽外壳里，无缝隙、无独立胶囊感。
     */
    private void styleTab(Button tab, boolean active) {
        if (active) {
            tab.setBackgroundResource(tab == btnConnectTab
                    ? R.drawable.bg_tab_sel_left : R.drawable.bg_tab_sel_right);
            // 主题中 colorOnPrimary 恒为白（values / values-night 均 @color/white）
            tab.setTextColor(Color.WHITE);
        } else {
            tab.setBackgroundColor(Color.TRANSPARENT);
            // colorPrimary 为平台主题属性（主题已 override），凹槽底色上主色文字清晰
            tab.setTextColor(attrColor(android.R.attr.colorPrimary));
        }
    }

    /** 解析当前主题下某 ?attr 颜色属性的实际色值 */
    private int attrColor(int attrRes) {
        android.util.TypedValue value = new android.util.TypedValue();
        activity.getTheme().resolveAttribute(attrRes, value, true);
        return value.data;
    }

    // ==================== 状态检测 ====================

    /** 页面回到前台（onResume）或配对/连接结束后调用：重新检测一次连接状态 */
    public void refresh() {
        tvStatus.setText(R.string.adb_loading);
        final int seq = ++mStatusSeq;
        new Thread(() -> {
            // 子线程：执行命令并解析（可能耗时数秒，绝不能放主线程）
            final boolean initialized = MainActivity.isDebianInitialized();
            final String connectedDevice = queryConnectedDevice();
            mainHandler.post(() -> {
                if (seq != mStatusSeq) return;   // 已有更新的检测结果，丢弃本次过期结果
                updateStatusText(initialized, connectedDevice);
            });
        }).start();
    }

    /**
     * 主线程：按检测结果更新状态文案与颜色。
     *
     * 未连接不再只显示干巴巴的「未连接」，而是按上下文给出下一步引导：
     *   - 容器未初始化 → 「容器未初始化」
     *   - 从未配对过   → 「未连接 · 请先首次配对」
     *   - 配对过       → 「未连接 · 请点击「连接」」（重连场景）
     *   - 已连接       → 绿色「已连接：<ip:port>」
     */
    private void updateStatusText(boolean initialized, String connectedDevice) {
        if (connectedDevice != null) {
            tvStatus.setText(activity.getString(R.string.adb_status_connected, connectedDevice));
            tvStatus.setTextColor(Color.parseColor("#2E7D32"));   // 已连接：深绿（白卡片上清晰）
        } else if (!initialized) {
            tvStatus.setText(R.string.adb_status_not_init);
            tvStatus.setTextColor(Color.GRAY);
        } else if (hasPaired()) {
            tvStatus.setText(R.string.adb_status_click_connect);
            tvStatus.setTextColor(Color.GRAY);
        } else {
            tvStatus.setText(R.string.adb_status_need_pair);
            tvStatus.setTextColor(Color.GRAY);
        }
    }

    /**
     * 执行 <proot-distro login debian -- adb devices> 并解析出第一个有效设备。
     *
     * @return 形如 "192.168.1.100:5555" 的设备地址；未连接/异常返回 null
     */
    private String queryConnectedDevice() {
        String output = execInContainer("devices", EXEC_TIMEOUT_MS);
        return parseAdbDevices(output);
    }

    // ==================== 命令执行（沿用原 AdbPairDialog 实现） ====================

    /**
     * 在 App 进程内静默执行容器内 adb 命令（不打开任何终端）。
     *
     * 命令形态：export PATH=<Termux bin> && proot-distro login debian -- adb <adbArgs>
     *
     * @param adbArgs  adb 子命令及参数，如 "devices"、"pair 1.2.3.4:37015 123456"
     * @param timeoutMs 最长等待毫秒数，超时强制销毁进程
     * @return 命令完整输出（stdout+stderr 合并）；容器未初始化/执行异常/超时返回 null
     */
    private String execInContainer(String adbArgs, long timeoutMs) {
        if (!MainActivity.isDebianInitialized()) {
            return null;    // 容器未初始化时直接返回，不浪费时间执行命令
        }

        try {
            // Runtime.exec 默认 PATH 不包含 Termux 目录，必须显式 export 前缀，
            // 否则系统找不到 proot-distro 命令。
            // 另 source ~/proot_env.sh 自愈 proot 运行环境（/system/bin/sh wrapper +
            // PD_PROOT_BIN），否则 proot-distro 干净环境下 proot 报 CANNOT LINK。
            String command = "export PATH=" + TERMUX_BIN + ":$PATH && "
                    + ". " + TERMUX_HOME + "/proot_env.sh 2>/dev/null || true; "
                    + "proot-distro login debian -- adb " + adbArgs;

            ProcessBuilder pb = new ProcessBuilder(TERMUX_BASH, "-c", command);
            pb.redirectErrorStream(true);   // 把 stderr 并入 stdout，避免只读一个流导致管道阻塞死锁

            // 关键：App 进程环境（zygote 继承）没有 Termux 的 LD_LIBRARY_PATH 及
            // proot-distro 必需的环境变量。缺 LD_LIBRARY_PATH 时 bash/python/proot
            // 全部 CANNOT LINK；缺 TERMUX_APP__PACKAGE_NAME/TERMUX__PREFIX 时
            // proot-distro 回落官方 com.termux 前缀导致路径错乱、登录失败。
            // 症状：配对/连接点了没反应（命令静默失败/超时）。
            // 此处与 TermuxShellEnvironment（termux-shared）注入的变量保持一致。
            Map<String, String> env = pb.environment();
            env.put("HOME", TERMUX_HOME);
            env.put("PREFIX", TERMUX_PREFIX);
            env.put("TERM", "dumb");
            env.put("LD_LIBRARY_PATH", TERMUX_PREFIX + "/lib");
            env.put("TERMUX_APP__PACKAGE_NAME", "duckyal.KaguraX");
            env.put("TERMUX__PREFIX", TERMUX_PREFIX);
            env.put("TERMUX_APP__DATA_DIR", "/data/data/duckyal.KaguraX");
            env.put("TERMUX_APP__LEGACY_DATA_DIR", "/data/data/duckyal.KaguraX");
            env.put("PROOT_TMP_DIR", TERMUX_PREFIX + "/tmp");

            Process process = pb.start();

            // 先等待进程结束（带超时强制销毁），再读输出。
            // 顺序很关键：若先 readLine 再 waitForProcess，命令卡住时 readLine 会一直阻塞，
            // 超时保护根本执行不到 → 子线程永久挂起、按钮永远禁用、无任何 Toast
            // （表现为「点了配对没反应」）。先 wait 后 read 则卡住也能超时返回。
            waitForProcess(process, timeoutMs);

            // 进程已结束（或已销毁），readLine 立即读到 EOF；销毁前已写入管道的输出仍可读出
            StringBuilder output = new StringBuilder();
            try (BufferedReader reader = new BufferedReader(
                    new InputStreamReader(process.getInputStream(), StandardCharsets.UTF_8))) {
                String line;
                while ((line = reader.readLine()) != null) {
                    output.append(line).append('\n');
                }
            }
            return output.toString();
        } catch (Exception e) {
            return null;    // 命令不存在 / IO 异常等：按失败处理
        }
    }

    /**
     * 等待进程结束（兼容 API 24：不用 waitFor(long, TimeUnit)，改轮询）。
     * 超过超时时间直接销毁进程，避免子线程永久卡死。
     */
    private void waitForProcess(Process process, long timeoutMs) throws InterruptedException {
        long deadline = System.currentTimeMillis() + timeoutMs;
        while (System.currentTimeMillis() < deadline) {
            try {
                process.exitValue();    // 进程已结束时返回退出码，否则抛 IllegalThreadStateException
                return;
            } catch (IllegalThreadStateException e) {
                Thread.sleep(200);      // 进程还在运行，休眠后继续轮询
            }
        }
        process.destroy();              // 超时：强制结束
    }

    /**
     * 解析 adb devices 输出，找第一台状态为 device 的设备。
     *
     * 规则：第二列必须精确等于 device（offline/unauthorized 不算）；
     * 标题行 "List of devices attached" 第二列是 "of"，天然被排除。
     */
    private String parseAdbDevices(String output) {
        if (output == null) return null;
        for (String line : output.split("\n")) {
            String trimmed = line.trim();
            if (trimmed.isEmpty()) {
                continue;
            }
            String[] parts = trimmed.split("\\s+");
            if (parts.length >= 2 && "device".equals(parts[1])) {
                return parts[0];    // 返回第一台有效设备
            }
        }
        return null;
    }

    /**
     * 在 adb 命令输出中查找指定序列号(ip:port)所在行并返回其状态。
     * 未出现在输出中返回 null。
     *
     * 说明：performConnect 的复合命令把 adb connect 与 adb devices 放同一段输出里，
     * 此处直接解析即可，无需另开一次 exec（避免 adb server daemon 会话漂移）。
     */
    private String deviceStateOf(String output, String address) {
        if (output == null) return null;
        for (String line : output.split("\n")) {
            String[] parts = line.trim().split("\\s+");
            if (parts.length >= 2 && address.equals(parts[0])) {
                return parts[1];
            }
        }
        return null;
    }

    /**
     * 判断命令输出是否命中任一成功标志（大小写不敏感）。
     */
    private boolean isSuccess(String output, String... markers) {
        if (output == null) return false;
        String lower = output.toLowerCase();
        for (String marker : markers) {
            if (lower.contains(marker.toLowerCase())) return true;
        }
        return false;
    }

    /** 从命令输出中提取用于提示的错误详情：取第一个非空、非 adb 常规提示的行。 */
    private String extractErrorDetail(String output) {
        if (output == null) return null;
        for (String line : output.split("\n")) {
            String trimmed = line.trim();
            if (trimmed.isEmpty()) continue;
            if (trimmed.startsWith("*")) continue;   // 跳过 "* daemon not running" 等常规提示
            return trimmed;
        }
        return null;
    }

    // ==================== 首次配对 ====================

    /**
     * 点击「配对」：App 进程内后台静默执行 adb pair，Toast 反馈结果。
     *
     * 配对成功后自动把同一设备的 IP 预填到连接地址框并发起连接（一步到位）。
     * 配对地址/配对码每次都会变化，一律不保存。
     */
    private void onPairClicked() {
        String pairAddress = etPairAddress.getText().toString().trim();
        String pairCode = etPairCode.getText().toString().trim();

        if (pairAddress.isEmpty() || pairCode.isEmpty()) {
            toast(R.string.adb_input_empty_pair);
            return;
        }
        if (!MainActivity.isDebianInitialized()) {
            toast(R.string.adb_not_initialized);
            return;
        }

        btnPair.setEnabled(false);
        toast(R.string.adb_pair_running);

        new Thread(() -> {
            // 地址是 ip:port、配对码是纯数字，无 shell 特殊字符，可安全拼接
            String output = execInContainer("pair " + pairAddress + " " + pairCode, OP_TIMEOUT_MS);
            // Android 13+ adb pair 成功输出固定含 "Successfully paired"
            final boolean success = isSuccess(output, "Successfully paired");
            mainHandler.post(() -> {
                btnPair.setEnabled(true);
                if (success) {
                    setHasPaired(true);   // 记录已完成首次配对，后续连接不再反复引导
                    prefillConnectAddressFromPair(pairAddress);
                    showConnectSection();
                    // 连接端口需按被控端「无线调试」页当前显示填写：若连接框已带端口
                    // （例如之前记住过同 IP 的端口）则自动连接；否则提示补全新端口。
                    String connectAddress = etConnectAddress.getText().toString().trim();
                    if (hasConnectPort(connectAddress)) {
                        toast(R.string.adb_pair_success);   // 「配对成功，正在自动连接…」
                        performConnect(connectAddress);
                    } else {
                        toast(R.string.adb_pair_success_fill_port);
                    }
                } else {
                    toast(R.string.adb_pair_failed);
                    refresh();            // 失败也重新检测一次状态
                }
            });
        }).start();
    }

    /**
     * 从配对地址提取 IP，预填到连接地址框（保留 "ip:" 等待用户补系统当前显示的端口）。
     * 若连接框里已有同一 IP 的完整地址（如上次记住的端口仍有效），则保留不动，便于
     * 配对成功后直接自动连接。
     */
    private void prefillConnectAddressFromPair(String pairAddress) {
        String host = pairAddress;
        int lastColon = host.lastIndexOf(':');
        if (lastColon > 0) {
            host = host.substring(0, lastColon);
        }
        String current = etConnectAddress.getText().toString().trim();
        if (current.isEmpty() || !host.equals(ipOf(current))) {
            // 不保存残缺地址：记忆只存完整 ip:port，避免下次启动显示 "ip:" 占位
            etConnectAddress.setText(host + ":");
        }
    }

    // ==================== 连接 ====================

    /**
     * 点击「连接」：App 进程内后台静默执行 adb connect，Toast 反馈结果，并记住该地址。
     */
    private void onConnectClicked() {
        String connectAddress = etConnectAddress.getText().toString().trim();

        if (connectAddress.isEmpty()) {
            toast(R.string.adb_input_empty_connect);
            return;
        }
        // 连接地址必须带端口（被控端无线调试页当前显示的随机端口），缺端口一定连不上
        if (!hasConnectPort(connectAddress)) {
            toast(R.string.adb_input_need_port);
            return;
        }
        if (!MainActivity.isDebianInitialized()) {
            toast(R.string.adb_not_initialized);
            return;
        }
        // 从未完成过首次配对：引导用户先配对（无线调试必须先 pair 一次才能 connect）
        if (!hasPaired()) {
            toast(R.string.adb_need_pair_first);
            showPairSection();    // 自动切到「首次配对」区块（互斥：连接区块收起）
            return;
        }

        // 连接成功后记忆（performConnect 成功分支保存），失败不覆盖，避免记住坏端口
        toast(R.string.adb_connect_running);
        performConnect(connectAddress);
    }

    /**
     * 后台静默执行 adb connect，结束后 Toast 结果并刷新状态。
     * 手动点「连接」与配对成功后的自动连接共用此方法。
     *
     * 2026-09 加固（针对“反复开关无线调试才连得上”）：
     *  1) 重试前先 adb disconnect 同一地址，清掉 adb server 里残留的 offline /
     *     unauthorized 旧连接，让下次 connect 重新完整握手（避免旧状态导致误判）；
     *  2) 失败时按 adb 输出分类提示：unauthorized=被控端需点「允许USB调试」/重新配对，
     *     refused=端口写错或无线调试已关，offline=稍候重连等，直接告诉用户该做什么，
     *     不再只回显英文原文；
     *  3) 认证类失败(unauthorized / failed to authenticate)说明上次配对已失效，自动清
     *     掉配对标记、切回「首次配对」区块并按当前 IP 预填，引导重新配对。
     *
     * 2026-09 追加修复（假连接成功）：adb connect 回 "connected to" 只代表 TCP+adb 握手
     * 建立，不代表设备可用——Android 11+ 无线调试下 host 公钥未授权（设备状态
     * unauthorized，被控端应弹授权）或 transport 尚未被 adb server 纳管时，connect 同样
     * 回 "connected to"。故 connect 文本成功不再直接判成功，而是与 adb devices 验证放在
     * 同一次容器会话内执行，以该地址的真实状态为准：device=真成功；unauthorized=提示去
     * 被控端点「允许」；offline/查无此设备=先 disconnect 再重试，不再误报「连接成功」。
     */
    private void performConnect(String connectAddress) {
        btnConnect.setEnabled(false);

        new Thread(() -> {
            String output = null;
            String verifiedState = null;   // adb devices 中该地址的真实状态：device/unauthorized/其他
            boolean success = false;
            for (int attempt = 1; attempt <= MAX_CONNECT_ATTEMPTS && !success; attempt++) {
                // connect 与 devices 验证放同一次容器会话内顺序执行：规避 adb server daemon
                // 在两次 exec 之间被杀/漂移（新旧 daemon 各自查不到对方建的 transport）导致
                // connect 文本成功但 devices 里永远没有该设备的假象。
                // connect 成功标志含 "connected to"；已连接过则含 "already connected"。
                output = execInContainer("connect " + connectAddress + "; sleep "
                        + CONNECT_SETTLE_SLEEP_S + "; adb devices", OP_TIMEOUT_MS);
                if (output != null && isSuccess(output, "connected to", "already connected")) {
                    // 假阳性防护：connect 文本成功≠设备可用（未授权设备也回 "connected to"），
                    // 必须以 adb devices 里该地址的真实状态为准。
                    verifiedState = deviceStateOf(output, connectAddress);
                    if ("device".equals(verifiedState)) {
                        success = true;
                        break;
                    }
                    if ("unauthorized".equals(verifiedState)) {
                        break;   // 已握手但被控端未授权：停下等用户在被控端点「允许」，不误报成功
                    }
                    // offline / 列表里还没有该地址：transport 未就绪，先断开旧状态再重试
                }
                if (!success && attempt < MAX_CONNECT_ATTEMPTS) {
                    // 断开该地址的旧连接（best-effort），清除残留 offline/unauthorized 状态
                    execInContainer("disconnect " + connectAddress, EXEC_TIMEOUT_MS);
                    try {
                        Thread.sleep(CONNECT_RETRY_DELAY_MS);
                    } catch (InterruptedException e) {
                        break;
                    }
                }
            }

            final boolean finalSuccess = success;
            final boolean finalNeedsAuth = "unauthorized".equals(verifiedState);
            // connect 文本成功但验证未通过（设备始终没入列表/未就绪）：与真失败分开提示
            final boolean finalTextSaysConnected = !success
                    && isSuccess(output, "connected to", "already connected");
            final String hint = connectHint(output);
            final boolean needRePair = needsRePair(output);
            final String detail = extractErrorDetail(output);
            mainHandler.post(() -> {
                btnConnect.setEnabled(true);
                if (finalSuccess) {
                    saveConnectAddress(connectAddress);   // 成功才覆盖记忆，保证记忆为有效地址
                    toast(R.string.adb_connect_success);
                } else if (finalNeedsAuth) {
                    // 连接已建立但被控端未授权（可能根本没弹授权窗）：按现成文案引导处理，
                    // 不误报「连接成功」，也不清配对标记（必要时按提示重新配对）
                    Toast.makeText(appContext, R.string.adb_hint_unauthorized,
                            Toast.LENGTH_LONG).show();
                } else if (finalTextSaysConnected) {
                    // 曾回 connected to 但设备未入列/未转 device：明确告知未真正就绪
                    Toast.makeText(appContext, R.string.adb_connect_not_ready,
                            Toast.LENGTH_LONG).show();
                } else if (hint != null) {
                    // 分类提示（比英文原文可操作）：
                    // 认证类失败自动引导重新配对，其余停留在连接区块让用户按提示改
                    Toast.makeText(appContext, hint, Toast.LENGTH_LONG).show();
                    if (needRePair) {
                        setHasPaired(false);              // 配对已失效：下次需重新配对
                        prefillPairAddressFromConnect();  // 按连接框 IP 预填配对地址
                        showPairSection();                // 自动切到「首次配对」
                        etPairCode.setText("");
                    }
                } else if (detail != null) {
                    // 失败且有 adb 实质输出：显示具体原因，方便排查（如 Connection refused）
                    Toast.makeText(appContext,
                            appContext.getString(R.string.adb_connect_failed_detail, detail),
                            Toast.LENGTH_LONG).show();
                } else {
                    toast(R.string.adb_connect_failed);
                }
                refresh();    // 结束后重新检测连接状态
            });
        }).start();
    }

    /**
     * 连接地址是否含端口：形如 ip:port / [ipv6]:port，最后一个冒号后必须是纯数字。
     * 缺端口（如 "192.168.1.100:"）返回 false。
     */
    private boolean hasConnectPort(String address) {
        if (address == null || address.isEmpty()) return false;
        int lastColon = address.lastIndexOf(':');
        if (lastColon <= 0 || lastColon == address.length() - 1) return false;
        return address.substring(lastColon + 1).matches("\\d+");
    }

    /** 从完整 ip:port 地址中提取 IP（IPv6 也按最后一个冒号切，稳妥） */
    private String ipOf(String address) {
        if (address == null) return "";
        int lastColon = address.lastIndexOf(':');
        return lastColon > 0 ? address.substring(0, lastColon) : address;
    }

    /** 按 adb connect 失败输出分类出“该做什么”的可操作提示；无法识别返回 null */
    private String connectHint(String output) {
        if (output == null) return null;
        String lower = output.toLowerCase();
        if (lower.contains("unauthorized")) {
            return appContext.getString(R.string.adb_hint_unauthorized);
        }
        if (lower.contains("failed to authenticate")
                || lower.contains("authentication failed")
                || lower.contains("failed to authenticate to")) {
            return appContext.getString(R.string.adb_hint_re_authenticate);
        }
        if (lower.contains("offline")) {
            return appContext.getString(R.string.adb_hint_offline);
        }
        if (lower.contains("cannot connect") || lower.contains("connection refused")
                || lower.contains("failed to connect") || lower.contains("timed out")
                || lower.contains("no route to host") || lower.contains("unable to connect")) {
            return appContext.getString(R.string.adb_hint_cannot_connect);
        }
        return null;
    }

    /** 认证类失败（unauthorized / 认证失败）说明上次配对已失效，需要重新配对 */
    private boolean needsRePair(String output) {
        if (output == null) return false;
        String lower = output.toLowerCase();
        return lower.contains("unauthorized")
                || lower.contains("failed to authenticate")
                || lower.contains("authentication failed");
    }

    // ==================== 小工具 ====================

    /** 从 SharedPreferences 读取上次记住的连接地址并自动填入 */
    private void loadSavedConnectAddress() {
        SharedPreferences prefs = appContext.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE);
        String saved = prefs.getString(KEY_LAST_CONNECT_ADDRESS, null);
        if (saved != null && !saved.isEmpty()) {
            etConnectAddress.setText(saved);
        }
    }

    /** 记住连接地址到 SharedPreferences */
    private void saveConnectAddress(String connectAddress) {
        appContext.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
                .edit()
                .putString(KEY_LAST_CONNECT_ADDRESS, connectAddress)
                .apply();
    }

    /**
     * 用上次连接地址的 IP 预填配对地址框（只补 IP，端口留空等用户填系统显示的新端口）。
     * 连接地址形如 "192.168.1.100:5555"，配对地址形如 "192.168.1.100:37015"，
     * 两者 IP 相同，预填后用户只需输入系统「无线调试」页面显示的配对端口与配对码。
     * 仅当配对地址框为空时预填，避免覆盖用户已输入的内容。
     */
    private void prefillPairAddressFromConnect() {
        String connectAddress = etConnectAddress.getText().toString().trim();
        if (connectAddress.isEmpty()) return;
        if (!etPairAddress.getText().toString().trim().isEmpty()) return;

        String host = connectAddress;
        int lastColon = host.lastIndexOf(':');
        if (lastColon > 0) {
            host = host.substring(0, lastColon);
        }
        etPairAddress.setText(host + ":");
    }

    /** 是否完成过首次配对 */
    private boolean hasPaired() {
        return appContext.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
                .getBoolean(KEY_HAS_PAIRED, false);
    }

    /** 记录是否完成过首次配对 */
    private void setHasPaired(boolean paired) {
        appContext.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
                .edit()
                .putBoolean(KEY_HAS_PAIRED, paired)
                .apply();
    }

    /** Toast 快捷方法 */
    private void toast(int resId) {
        Toast.makeText(appContext, resId, Toast.LENGTH_SHORT).show();
    }
}
