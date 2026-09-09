package com.termux.app;

import android.app.Activity;
import android.app.Application;
import android.content.Context;
import android.os.Build;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.provider.Settings;

import java.net.InetSocketAddress;
import java.net.Socket;

import com.termux.BuildConfig;
import com.termux.shared.errors.Error;
import com.termux.shared.logger.Logger;
import com.termux.shared.termux.TermuxBootstrap;
import com.termux.shared.termux.TermuxConstants;
import com.termux.shared.termux.crash.TermuxCrashUtils;
import com.termux.shared.termux.file.TermuxFileUtils;
import com.termux.shared.termux.settings.preferences.TermuxAppSharedPreferences;
import com.termux.shared.termux.settings.properties.TermuxAppSharedProperties;
import com.termux.shared.termux.shell.command.environment.TermuxShellEnvironment;
import com.termux.shared.termux.shell.am.TermuxAmSocketServer;
import com.termux.shared.termux.shell.TermuxShellManager;
import com.termux.shared.termux.theme.TermuxThemeUtils;

public class TermuxApplication extends Application {

    private static final String LOG_TAG = "TermuxApplication";

    /** 前台 Activity 计数：为 0 表示应用已退到后台 */
    private int mResumedCount = 0;
    /** 退后台后延迟拉起悬浮球（毫秒）：覆盖应用内切换页面的短暂后台窗口，避免误开 */
    private static final long FLOAT_START_DELAY_MS = 1200;
    private final Handler mAppHandler = new Handler(Looper.getMainLooper());

    /**
     * 延迟后执行：确认仍在后台、具备悬浮窗权限、项目服务在运行（未启动/已终止则不挂），
     * 才拉起悬浮球。悬浮窗的生命周期与项目运行绑定：
     *   - 点击「启动项目」→ MainActivity 端口就绪后主动开启（前台即可见）；
     *   - App 进程冷启动后项目仍在运行、用户直接退后台 → 这里兜底拉起。
     */
    private final Runnable mStartFloatingBall = () -> {
        if (mResumedCount > 0) return;                       // 已回到前台
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M
                && !Settings.canDrawOverlays(this)) return;  // 无悬浮窗权限（由主界面引导）
        if (FloatingWindowService.isRunning()) return;        // 已在运行
        // 端口探测放子线程，避免阻塞主线程
        new Thread(() -> {
            if (!isProjectServiceUp()) return;
            mAppHandler.post(() -> {
                if (mResumedCount > 0) return;
                if (!FloatingWindowService.isRunning()
                        && Settings.canDrawOverlays(this)) {
                    try {
                        FloatingWindowService.start(this);
                    } catch (Exception e) {
                        Logger.logErrorExtended(LOG_TAG, "auto start floating ball failed: " + e.getMessage());
                    }
                }
            });
        }, "float-auto").start();
    };

    /** 项目服务端口(127.0.0.1:8000)是否可连通 —— 悬浮球自动开启的前置条件 */
    private boolean isProjectServiceUp() {
        try (Socket socket = new Socket()) {
            socket.connect(new InetSocketAddress("127.0.0.1", 8000), 1500);
            return true;    // 能建立 TCP 连接 = 服务正在监听
        } catch (Exception e) {
            return false;   // 连接被拒 / 超时 / 无网络均视为未运行
        }
    }

    public void onCreate() {
        super.onCreate();

        Context context = getApplicationContext();

        // 应用完全退到后台时自动开启悬浮球（不再需要手动按钮）
        registerActivityLifecycleCallbacks(new ActivityLifecycleCallbacks() {
            @Override public void onActivityCreated(Activity activity, Bundle savedInstanceState) {}
            @Override public void onActivityStarted(Activity activity) {}
            @Override public void onActivityResumed(Activity activity) {
                mResumedCount++;
                mAppHandler.removeCallbacks(mStartFloatingBall);
            }
            @Override public void onActivityPaused(Activity activity) {
                mResumedCount--;
                if (mResumedCount <= 0) {
                    // 全部页面暂停 = 退后台（含切到系统设置/其他 App）；延迟后再确认
                    mAppHandler.postDelayed(mStartFloatingBall, FLOAT_START_DELAY_MS);
                }
            }
            @Override public void onActivityStopped(Activity activity) {}
            @Override public void onActivitySaveInstanceState(Activity activity, Bundle outState) {}
            @Override public void onActivityDestroyed(Activity activity) {}
        });

        // Set crash handler for the app
        TermuxCrashUtils.setDefaultCrashHandler(this);

        // Set log config for the app
        setLogConfig(context);

        Logger.logDebug("Starting Application");

        // Set TermuxBootstrap.TERMUX_APP_PACKAGE_MANAGER and TermuxBootstrap.TERMUX_APP_PACKAGE_VARIANT
        TermuxBootstrap.setTermuxPackageManagerAndVariant(BuildConfig.TERMUX_PACKAGE_VARIANT);

        // Init app wide SharedProperties loaded from termux.properties
        TermuxAppSharedProperties properties = TermuxAppSharedProperties.init(context);

        // Init app wide shell manager
        TermuxShellManager shellManager = TermuxShellManager.init(context);

        // Set NightMode.APP_NIGHT_MODE
        TermuxThemeUtils.setAppNightMode(properties.getNightMode());

        // Check and create termux files directory. If failed to access it like in case of secondary
        // user or external sd card installation, then don't run files directory related code
        Error error = TermuxFileUtils.isTermuxFilesDirectoryAccessible(this, true, true);
        boolean isTermuxFilesDirectoryAccessible = error == null;
        if (isTermuxFilesDirectoryAccessible) {
            Logger.logInfo(LOG_TAG, "Termux files directory is accessible");

            error = TermuxFileUtils.isAppsTermuxAppDirectoryAccessible(true, true);
            if (error != null) {
                Logger.logErrorExtended(LOG_TAG, "Create apps/termux-app directory failed\n" + error);
                return;
            }

            // Setup termux-am-socket server
            TermuxAmSocketServer.setupTermuxAmSocketServer(context);
        } else {
            Logger.logErrorExtended(LOG_TAG, "Termux files directory is not accessible\n" + error);
        }

        // Init TermuxShellEnvironment constants and caches after everything has been setup including termux-am-socket server
        TermuxShellEnvironment.init(this);

        if (isTermuxFilesDirectoryAccessible) {
            TermuxShellEnvironment.writeEnvironmentToFile(this);
        }
    }

    public static void setLogConfig(Context context) {
        Logger.setDefaultLogTag(TermuxConstants.TERMUX_APP_NAME);

        // Load the log level from shared preferences and set it to the {@link Logger.CURRENT_LOG_LEVEL}
        TermuxAppSharedPreferences preferences = TermuxAppSharedPreferences.build(context);
        if (preferences == null) return;
        preferences.setLogLevel(null, preferences.getLogLevel());
    }

}
