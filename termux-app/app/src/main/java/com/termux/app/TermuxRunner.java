package com.termux.app;

import com.termux.R;
import com.termux.shared.termux.TermuxConstants.TERMUX_APP.RUN_COMMAND_SERVICE;

import android.content.Context;
import android.content.Intent;
import android.os.Build;

/**
 * TermuxRunner —— 在 Termux 环境内执行命令的工具类。
 *
 * 原理：
 *   通过 Android 的 Service 机制，向 Termux 自带的 RunCommandService
 *   发送一个 action 为 RUN_COMMAND_SERVICE.ACTION_RUN_COMMAND 的 Intent。
 *   RunCommandService 解析 Intent 携带的 extra 参数后，
 *   会在 Termux 的 bash 环境中执行我们指定的命令。
 *
 *   本项目是 termux-app 的 fork，RunCommandService 就在同一个 App 进程内，
 *   因此调用它不需要任何跨应用权限 —— 这是整套技术方案能成立的基础。
 *
 *   对外只暴露一个静态方法 run()，调用方无需关心 Intent 细节。
 */
public final class TermuxRunner {

    // ==================== RUN_COMMAND Intent 参数名（与 RunCommandService 的契约一致） ====================
    // 注意：这些常量必须引用 TermuxConstants.RUN_COMMAND_SERVICE 中的定义，
    // 它们基于 TERMUX_PACKAGE_NAME 动态生成（本 fork 为 duckyal.KaguraX），
    // 绝不能硬编码 "com.termux.xxx"，否则 RunCommandService 会报 Invalid intent action。

    /** Intent 的 action，与 Manifest 中 RunCommandService 的 <intent-filter> 匹配 */
    public static final String ACTION_RUN_COMMAND = RUN_COMMAND_SERVICE.ACTION_RUN_COMMAND;

    /** 可执行文件路径 extra（固定为 Termux 自带的 bash） */
    public static final String EXTRA_COMMAND_PATH = RUN_COMMAND_SERVICE.EXTRA_COMMAND_PATH;

    /** 传给可执行文件的参数数组 extra（bash 的 -c <命令> 模式） */
    public static final String EXTRA_ARGUMENTS = RUN_COMMAND_SERVICE.EXTRA_ARGUMENTS;

    /** 是否后台运行 extra：true=静默后台执行，false=前台终端会话 */
    public static final String EXTRA_BACKGROUND = RUN_COMMAND_SERVICE.EXTRA_BACKGROUND;

    /** 会话动作 extra：字符串 "0" = 新开会话并切换过去（前置） */
    public static final String EXTRA_SESSION_ACTION = RUN_COMMAND_SERVICE.EXTRA_SESSION_ACTION;

    /** 会话名 extra：同名会话可被 NO_SHELL_WITH_NAME 复用，避免重复点击无限新开终端 */
    public static final String EXTRA_SHELL_NAME = RUN_COMMAND_SERVICE.EXTRA_SHELL_NAME;

    /** 会话创建模式 extra："always"=总是新建（默认），"no-shell-with-name"=无同名会话才新建 */
    public static final String EXTRA_SHELL_CREATE_MODE = RUN_COMMAND_SERVICE.EXTRA_SHELL_CREATE_MODE;

    /** ShellCreateMode.NO_SHELL_WITH_NAME 的字符串值：复用同名运行中的会话 */
    public static final String SHELL_CREATE_MODE_NO_SHELL_WITH_NAME = "no-shell-with-name";

    /** 新开会话时的会话动作值：0 = 新开会话并前置 */
    public static final int SESSION_ACTION_SWITCH_TO_NEW_SESSION = 0;

    /** 命令标签 extra（显示在会话列表/通知里的标题） */
    public static final String EXTRA_COMMAND_LABEL = RUN_COMMAND_SERVICE.EXTRA_COMMAND_LABEL;

    /** Termux 自带 bash 的绝对路径（即 $PREFIX/bin/bash，PREFIX=/data/data/duckyal.KaguraX/files/usr） */
    private static final String TERMUX_BASH = "/data/data/duckyal.KaguraX/files/usr/bin/bash";

    /** 禁止实例化：纯工具类 */
    private TermuxRunner() {
    }

    /**
     * 在 Termux 环境中执行一条命令（唯一对外入口）。
     *
     * @param context    上下文（Activity / Service 均可）
     * @param command    要执行的完整 shell 命令字符串，如 "proot-distro login debian"
     * @param newSession true  = 新开一个终端会话并前置（用户可见、可交互），
     *                   例如初始化容器、启动项目这类希望用户看到输出过程的场景；
     *                   false = 在后台静默执行（不打扰用户），
     *                   例如终止项目（pkill）这类一键完成、无需观看的场景。
     */
    public static void run(Context context, String command, boolean newSession) {
        run(context, command, newSession, null, null);
    }

    /**
     * 在 Termux 环境中执行一条命令（唯一对外入口）。
     *
     * @param context        上下文（Activity / Service 均可）
     * @param command        要执行的完整 shell 命令字符串，如 "proot-distro login debian"
     * @param newSession     true  = 新开一个终端会话并前置（用户可见、可交互），
     *                       例如初始化容器、启动项目这类希望用户看到输出过程的场景；
     *                       false = 在后台静默执行（不打扰用户），
     *                       例如终止项目（pkill）这类一键完成、无需观看的场景。
     * @param shellName      会话名（可为 null）。配合 shellCreateMode 使用：
     *                       同名且仍在运行的会话可被复用，避免会话无限堆积。
     * @param shellCreateMode 会话创建模式（可为 null）：
     *                       SHELL_CREATE_MODE_NO_SHELL_WITH_NAME = 存在同名运行中会话时
     *                       不新建，仅把已有会话前置（复用终端）；null = 总是新建。
     */
    public static void run(Context context, String command, boolean newSession,
                           String shellName, String shellCreateMode) {
        // 1. 构造指向 RunCommandService 的 Intent。
        //    显式指定组件（packageName + 类名），确保系统一定路由到本 App 内的服务，
        //    不依赖隐式 intent 的解析（虽然 Manifest 里也注册了 intent-filter）。
        Intent intent = new Intent(ACTION_RUN_COMMAND);
        intent.setClassName(context.getPackageName(), RunCommandService.class.getName());

        // 2. 指定可执行文件为 Termux 的 bash，参数为 ["-c", command]，
        //    等效于在 Termux 终端输入：bash -c "command"
        intent.putExtra(EXTRA_COMMAND_PATH, TERMUX_BASH);
        intent.putExtra(EXTRA_ARGUMENTS, new String[]{"-c", command});

        // 2.5 会话名与创建模式：NO_SHELL_WITH_NAME 时若已有同名运行中会话则复用而非新建。
        //     注意 RunCommandService 用 getStringExtra 读取这两个 extra，必须传字符串。
        if (shellName != null) {
            intent.putExtra(EXTRA_SHELL_NAME, shellName);
        }
        if (shellCreateMode != null) {
            intent.putExtra(EXTRA_SHELL_CREATE_MODE, shellCreateMode);
        }

        // 3. BACKGROUND 与 newSession 恰好相反：
        //    newSession=true  → 前台终端会话（BACKGROUND=false）
        //    newSession=false → 后台静默执行（BACKGROUND=true）
        intent.putExtra(EXTRA_BACKGROUND, !newSession);

        // 4. 需要前置时，附加会话动作 extra = "0"（新开会话并切换过去）。
        //    注意 RunCommandService 用 getStringExtra 读取，所以要传字符串 "0"。
        if (newSession) {
            intent.putExtra(EXTRA_SESSION_ACTION, String.valueOf(SESSION_ACTION_SWITCH_TO_NEW_SESSION));
        }

        // 5. 设置会话标题，方便用户在会话列表 / 状态栏通知里识别这是哪个任务。
        intent.putExtra(EXTRA_COMMAND_LABEL, context.getString(R.string.application_name_manager));

        // 6. 启动服务：
        //    RunCommandService 是前台服务（内部会调用 startForeground 创建常驻通知），
        //    Android 8.0+ 要求用 startForegroundService() 来启动前台服务；
        //    8.0 以下老版本没有这个方法，用普通 startService() 即可。
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            context.startForegroundService(intent);
        } else {
            context.startService(intent);
        }
    }
}
