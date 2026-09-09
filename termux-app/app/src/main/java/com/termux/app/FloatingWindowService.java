package com.termux.app;

import android.animation.ObjectAnimator;
import android.annotation.SuppressLint;
import android.app.Notification;
import android.app.PendingIntent;
import android.app.Service;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.content.res.Configuration;
import android.graphics.Canvas;
import android.graphics.Paint;
import android.graphics.PixelFormat;
import android.graphics.RectF;
import android.os.Build;
import android.os.Handler;
import android.os.IBinder;
import android.os.Looper;
import android.provider.Settings;
import android.util.Log;
import android.view.Gravity;
import android.view.KeyEvent;
import android.view.LayoutInflater;
import android.view.MotionEvent;
import android.view.View;
import android.view.ViewConfiguration;
import android.view.WindowManager;
import android.view.animation.LinearInterpolator;
import android.webkit.JavascriptInterface;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.FrameLayout;
import android.widget.ImageView;
import android.widget.Toast;

import com.termux.R;
import com.termux.shared.notification.NotificationUtils;
import java.io.InputStream;
import java.net.HttpURLConnection;
import java.net.URL;

/**
 * 悬浮球服务（本项目新增）。
 *
 * 在任意界面（游戏、桌面、其他 App）之上显示一个只能贴边停靠的悬浮球：
 *   - 单击悬浮球：展开/收起遥控页（页面为 /float，无任何窗口装饰，直接铺满小窗）
 *   - 拖动悬浮球：只能吸附在屏幕左/右边缘（半隐藏贴边，纵向可停在任意位置），
 *     单击露出的一角会先滑出，再单击才展开小窗
 *   - 展开的小窗无壳：没有标题栏/边框/圆角/阴影，就是遥控页本身
 *       · 尺寸固定且不可拖动：竖屏约 300×520（比旧版小一号，尽量不挡游戏画面），
 *         横屏自动压缩高度不溢出屏；展开位置贴悬浮球所在的一侧屏幕边缘
 *       · 展开期间悬浮球自动隐藏（不另外占用屏幕边缘），
 *       · 收起通道：
 *           1) 遥控页左上角 KaguraX 徽标（圆形 logo + 名称，无多余图标）即「收起」钮，
 *              悬浮窗环境可点，经 KaguraXBridge.collapse() JS 桥收起；
 *           2) 系统返回键 / 全面屏返回手势 —— 在窗口内容层最顶层（根视图 dispatchKeyEvent）
 *              拦截：网页可后退时先后退，无历史则收起小窗；
 *              窗口可见即成为输入焦点窗口，返回键可稳定送达
 *       （“点击/双击窗口外收起”不可行：窗外触摸不派发给悬浮窗，ACTION_OUTSIDE 在
 *        游戏/多数 ROM 上也收不到，实测无效）
 *   - 长按悬浮球：直接停止服务
 *
 * 实现要点：
 *   - 前台服务 + 常驻通知，保证在游戏内不被回收；
 *   - SYSTEM_ALERT_WINDOW 悬浮窗权限（Manifest 已声明，启动前仍需检查 Settings.canDrawOverlays）；
 *   - 拖动时 updateViewLayout 必须传 addView 时添加的顶层 View，
 *     对子 View 调用会抛 IllegalArgumentException；
 *   - 悬浮球的位置记录到 SharedPreferences，下次启动恢复。
 */
public class FloatingWindowService extends Service {

    private static final String LOG_TAG = "FloatingWindowService";

    private static final String NOTIFICATION_CHANNEL_ID = "floating_window";
    private static final int NOTIFICATION_ID = 26410;

    /** 悬浮遥控页地址（/float，小窗默认加载；网页里可链到完整控制台 /home） */
    private static final String SERVICE_URL = "http://127.0.0.1:8000/float";

    private static final String PREFS_NAME = "floating_window_prefs";
    private static final String PREF_BALL_X = "ball_x";
    private static final String PREF_BALL_Y = "ball_y";

    /** 悬浮球直径（dp），之前 54dp 偏大，缩小到 40dp */
    private static final int BALL_SIZE_DP = 40;
    /** 贴边隐藏时露出的宽度（dp）：约球径（40dp）的 2/3，好点且仍算半隐藏 */
    private static final int DOCK_VISIBLE_DP = 27;
    /** 距左右边缘多近时触发吸附（dp） */
    private static final int DOCK_EDGE_DP = 24;
    /** 悬浮小窗竖屏目标尺寸(dp)：比旧版(340×620)小一号，避免盖住游戏画面太多；
     *  宽受限、高控制在页面可滚动范围内 */
    private static final int WINDOW_W_DP = 300;
    private static final int WINDOW_H_DP = 520;

    /** 任务运行状态查询地址与超时（后端 /api/task_status，空 device=任一设备） */
    private static final String TASK_STATUS_URL = "http://127.0.0.1:8000/api/task_status";
    private static final int STATUS_TIMEOUT_MS = 1200;

    /** 悬浮球「任务运行中」状态轮询周期（毫秒） */
    private static final long MONITOR_INTERVAL_MS = 2500;

    /** 状态光环：球体外缘留白(dp)与光环线宽(dp) */
    private static final int RING_GAP_DP = 5;
    private static final int RING_STROKE_DP = 3;

    /** 状态光环颜色：任务执行中=旋转绿弧；空闲=静止灰弧 */
    private static final int COLOR_RUNNING = 0xFF00E676;
    private static final int COLOR_RUNNING_DIM = 0x5900E676;
    private static final int COLOR_IDLE = 0xFF9E9E9E;
    private static final int COLOR_IDLE_DIM = 0x339E9E9E;

    /** 服务是否运行中（同进程静态标记，应用退后台自动开启时据此避免重复启动） */
    private static boolean sRunning = false;

    public static boolean isRunning() {
        return sRunning;
    }

    /** 统一启动入口（适配 Android 8+ 前台服务）。
     *  调用方：MainActivity(启动项目端口就绪后主动开启) /
     *  TermuxApplication(应用退后台且项目仍在运行兜底开启)。 */
    public static void start(Context context) {
        Intent intent = new Intent(context, FloatingWindowService.class);
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            context.startForegroundService(intent);
        } else {
            context.startService(intent);
        }
    }

    private WindowManager mWindowManager;
    private WindowManager.LayoutParams mBallParams;
    private View mBallView;
    private WindowManager.LayoutParams mWindowParams;
    private View mWindowView;
    private WebView mWebView;
    private boolean mWindowVisible = false;
    private boolean mWebViewPaused = false;

    /** 悬浮球是否处于贴边隐藏状态 */
    private boolean mBallDocked = false;

    /** 展开的小窗当前贴靠屏幕哪一侧边缘（true=右边缘，false=左边缘） */
    private boolean mWindowDockedRight = false;

    /** 拖动状态 */
    private float mTouchDownRawX, mTouchDownRawY;
    private int mTouchStartX, mTouchStartY;
    private boolean mDragging;
    private boolean mWasDockedAtDown;
    private int mTouchSlop;

    /** 运行状态光环（叠加在悬浮球图标外圈） */
    private View mRingView;
    private ObjectAnimator mRingAnimator;

    /** 是否正在执行任务（轮询线程查后端后回主线程刷新，驱动光环转绿旋转） */
    private volatile boolean mTaskRunning = false;
    /** 轮询线程开关（onDestroy 置 false 退出） */
    private volatile boolean mMonitorEnabled = false;
    private Thread mMonitorThread;

    @Override
    public void onCreate() {
        super.onCreate();
        // 悬浮窗权限被关闭时直接退出（例如用户从系统设置里撤销权限）
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M && !Settings.canDrawOverlays(this)) {
            Log.w(LOG_TAG, "No overlay permission, stopping");
            stopSelf();
            return;
        }

        mWindowManager = (WindowManager) getSystemService(WINDOW_SERVICE);
        mTouchSlop = ViewConfiguration.get(this).getScaledTouchSlop();

        int screenW = mWindowManager.getDefaultDisplay().getWidth();
        int screenH = mWindowManager.getDefaultDisplay().getHeight();

        setupNotification();
        createBall(screenW, screenH);
        createWindow(screenW, screenH);
        startMonitoring();   // 轮询后端任务状态并驱动光环（执行任务中才转绿）
        sRunning = true;
    }

    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        return START_STICKY; // 被杀后系统会尝试重建，重建即恢复悬浮球
    }

    @Override
    public void onDestroy() {
        sRunning = false;
        stopRingAnimation();
        mMonitorEnabled = false;
        if (mMonitorThread != null) {
            mMonitorThread.interrupt();   // 打断轮询休眠，线程随即退出
            mMonitorThread = null;
        }
        removeView(mBallView, mBallParams);
        removeView(mWindowView, mWindowParams);
        if (mWebView != null) {
            mWebView.removeAllViews();
            mWebView.destroy();
            mWebView = null;
        }
        super.onDestroy();
    }

    @Override
    public IBinder onBind(Intent intent) {
        return null;
    }

    // ==================== 前台服务通知 ====================

    /** 常驻通知：点击回到项目管理器主界面 */
    private void setupNotification() {
        NotificationUtils.setupNotificationChannel(this, NOTIFICATION_CHANNEL_ID,
                getString(R.string.floating_notification_channel_name),
                android.app.NotificationManager.IMPORTANCE_LOW);

        Intent contentIntent = new Intent(this, MainActivity.class);
        int flags = PendingIntent.FLAG_UPDATE_CURRENT;
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) flags |= PendingIntent.FLAG_IMMUTABLE;
        PendingIntent pi = PendingIntent.getActivity(this, 0, contentIntent, flags);

        Notification notification = NotificationUtils.geNotificationBuilder(this,
                NOTIFICATION_CHANNEL_ID,
                Notification.PRIORITY_LOW,
                getString(R.string.floating_notification_title),
                getString(R.string.floating_notification_text),
                getString(R.string.floating_notification_text),
                pi, null,
                NotificationUtils.NOTIFICATION_MODE_SILENT).build();
        startForeground(NOTIFICATION_ID, notification);
    }

    // ==================== 悬浮球 ====================

    /**
     * 创建悬浮球：顶层容器 = 状态光环(RingView) + 居中图标。
     * 容器直径比图标大 2×RING_GAP_DP，光环刚好露在图标外圈；
     * 光环是纯色圆环 + 一段高亮弧，高亮弧随 rotation 动画沿边缘旋转
     * （圆环对称，旋转视觉上只有高亮弧在动）。拖动/点击/长按监听挂在顶层容器上。
     */
    private void createBall(int screenW, int screenH) {
        int ballSize = dp(BALL_SIZE_DP);
        int ringGap = dp(RING_GAP_DP);
        int box = ballSize + ringGap * 2;

        FrameLayout root = new FrameLayout(this);
        root.setLayoutParams(new FrameLayout.LayoutParams(box, box));

        // 状态光环（先 add，图标后 add 盖在上面）
        RingView ring = new RingView(this, dp(RING_STROKE_DP));
        ring.setClickable(false);
        ring.setFocusable(false);
        ring.configure(COLOR_IDLE, COLOR_IDLE_DIM);   // 初始未知状态：静止灰弧
        root.addView(ring, new FrameLayout.LayoutParams(box, box));
        mRingView = ring;
        mRingAnimator = ObjectAnimator.ofFloat(ring, View.ROTATION, 0f, 360f);
        mRingAnimator.setDuration(1800);
        mRingAnimator.setRepeatCount(ObjectAnimator.INFINITE);
        mRingAnimator.setInterpolator(new LinearInterpolator());

        ImageView ball = new ImageView(this);
        ball.setImageResource(R.drawable.ic_float_ball);
        ball.setContentDescription(getString(R.string.action_floating_ball));
        ball.setClickable(false);
        ball.setFocusable(false);
        root.addView(ball, new FrameLayout.LayoutParams(ballSize, ballSize, Gravity.CENTER));

        mBallParams = new WindowManager.LayoutParams(
                box, box,
                overlayType(),
                WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE
                        | WindowManager.LayoutParams.FLAG_LAYOUT_IN_SCREEN,
                PixelFormat.TRANSLUCENT);
        mBallParams.gravity = Gravity.TOP | Gravity.START;

        SharedPreferences prefs = getSharedPreferences(PREFS_NAME, MODE_PRIVATE);
        mBallParams.x = prefs.getInt(PREF_BALL_X, screenW - box - dp(12));
        mBallParams.y = prefs.getInt(PREF_BALL_Y, screenH / 3);
        // 上次贴边保存的位置在屏幕外，据此恢复贴边状态
        if (mBallParams.x < 0 || mBallParams.x > screenW - box) {
            mBallDocked = true;
        }

        // 单击展开/收起（贴边时先滑出），拖动移动（碰边实时吸附），长按停止服务
        root.setOnTouchListener(makeDragListener(root, mBallParams, v -> onBallClick()));
        root.setOnLongClickListener(v -> {
            Toast.makeText(this, R.string.floating_toast_stopped, Toast.LENGTH_SHORT).show();
            stopSelf();
            return true;
        });

        mWindowManager.addView(root, mBallParams);
        mBallView = root;
        // 启动即吸附到边缘：悬浮球只出现在屏幕左/右边缘，不留中间
        snapBallToEdge();
    }

    // ==================== 运行状态光环 ====================

    /** 启动/停止光环旋转动画 */
    private void startRingAnimation() {
        if (mRingView == null || mRingAnimator == null) return;
        if (!mRingAnimator.isStarted()) {
            mRingView.setRotation(0f);
            mRingAnimator.start();
        }
    }

    private void stopRingAnimation() {
        if (mRingAnimator != null && mRingAnimator.isStarted()) {
            mRingAnimator.cancel();
        }
        if (mRingView != null) {
            mRingView.setRotation(0f);
        }
    }

    /**
     * 状态光环自定义 View：画一整圈半透明圆环 + 两段高亮弧。
     * 高亮弧在 onDraw 里固定角度，视觉旋转由外部对 View 做 rotation 动画实现。
     */
    private static final class RingView extends View {
        private final Paint mPaint = new Paint(Paint.ANTI_ALIAS_FLAG);
        private final float mStrokeWidth;
        private int mBrightColor = COLOR_IDLE;
        private int mDimColor = COLOR_IDLE_DIM;

        RingView(Context context, float strokeWidth) {
            super(context);
            mStrokeWidth = strokeWidth;
            mPaint.setStyle(Paint.Style.STROKE);
            mPaint.setStrokeCap(Paint.Cap.ROUND);
        }

        /** 切换状态配色：任务执行中=绿，空闲=灰 */
        void configure(int bright, int dim) {
            if (mBrightColor == bright && mDimColor == dim) return;
            mBrightColor = bright;
            mDimColor = dim;
            invalidate();
        }

        @Override
        protected void onDraw(Canvas canvas) {
            super.onDraw(canvas);
            float cx = getWidth() / 2f;
            float cy = getHeight() / 2f;
            float radius = Math.min(cx, cy) - mStrokeWidth / 2f - 1f;
            if (radius <= 0) return;
            RectF bounds = new RectF(cx - radius, cy - radius, cx + radius, cy + radius);
            mPaint.setStrokeWidth(mStrokeWidth);
            // 整圈底色环（很淡）
            mPaint.setColor(mDimColor);
            canvas.drawCircle(cx, cy, radius, mPaint);
            // 主高亮弧 + 小尾弧（-90° 起画，视觉上从顶部开始）
            mPaint.setColor(mBrightColor);
            canvas.drawArc(bounds, -90f, 90f, false, mPaint);
            canvas.drawArc(bounds, 135f, 26f, false, mPaint);
        }
    }

    // ==================== 任务运行状态轮询（后端 /api/task_status） ====================

    /** 请求后端：当前是否有任务正在执行（不带 device=任一设备在跑即视为执行中）。
     *  悬浮球只在项目运行时才存在，这里只关心「有没有任务在跑」来点亮光环。 */
    private static boolean isTaskRunning() {
        HttpURLConnection conn = null;
        try {
            URL url = new URL(TASK_STATUS_URL);
            conn = (HttpURLConnection) url.openConnection();
            conn.setRequestMethod("GET");
            conn.setConnectTimeout(STATUS_TIMEOUT_MS);
            conn.setReadTimeout(STATUS_TIMEOUT_MS);
            if (conn.getResponseCode() != HttpURLConnection.HTTP_OK) return false;
            InputStream in = conn.getInputStream();
            StringBuilder sb = new StringBuilder();
            byte[] buf = new byte[512];
            int n;
            while ((n = in.read(buf)) > 0) sb.append(new String(buf, 0, n, "UTF-8"));
            // 返回形如 {"running": true, "task_name": "..."}
            return sb.toString().replaceAll("\\s+", "").contains("\"running\":true");
        } catch (Exception e) {
            return false;   // 后端未响应 → 一律按空闲处理
        } finally {
            if (conn != null) conn.disconnect();
        }
    }

    /** 后台轮询线程：周期查询任务状态；状态翻转时回主线程刷新光环 */
    private void startMonitoring() {
        mMonitorEnabled = true;
        mMonitorThread = new Thread(() -> {
            boolean lastRunning = false;
            while (mMonitorEnabled) {
                final boolean running = isTaskRunning();
                if (running != lastRunning) {
                    new Handler(Looper.getMainLooper())
                            .post(() -> refreshBallUI(running));
                }
                lastRunning = running;
                try {
                    Thread.sleep(MONITOR_INTERVAL_MS);
                } catch (InterruptedException e) {
                    break;
                }
            }
        }, "float-task-monitor");
        mMonitorThread.setDaemon(true);
        mMonitorThread.start();
    }

    /** 主线程：按查询结果点亮光环：任务执行中=绿色旋转弧；空闲=静止灰弧 */
    private void refreshBallUI(boolean running) {
        if (mBallView == null || mRingView == null) return;
        mTaskRunning = running;
        if (running) {
            ((RingView) mRingView).configure(COLOR_RUNNING, COLOR_RUNNING_DIM);
            startRingAnimation();
        } else {
            ((RingView) mRingView).configure(COLOR_IDLE, COLOR_IDLE_DIM);
            stopRingAnimation();
        }
    }

    private void onBallClick() {
        if (mBallDocked) {
            // 贴边隐藏中：先滑出，本次点击不展开小窗
            unDockBall();
        } else {
            toggleWindow();
        }
    }

    /**
     * 吸附悬浮球到屏幕边缘：比较球中心与屏幕中线，吸到左或右边缘，
     * 半隐藏（露出约 2/3），纵向位置保持。悬浮球只允许出现在屏幕边缘。
     */
    private void snapBallToEdge() {
        if (mBallView == null || mBallParams == null) return;
        int screenW = mWindowManager.getDefaultDisplay().getWidth();
        int screenH = mWindowManager.getDefaultDisplay().getHeight();
        int ballSize = mBallParams.width;
        int centerX = mBallParams.x + ballSize / 2;
        if (centerX < screenW / 2) {
            mBallParams.x = dp(DOCK_VISIBLE_DP) - ballSize; // 左边缘半隐藏
        } else {
            mBallParams.x = screenW - dp(DOCK_VISIBLE_DP);  // 右边缘半隐藏
        }
        mBallParams.y = Math.max(0, Math.min(mBallParams.y, screenH - ballSize));
        mBallDocked = true;
        mWindowManager.updateViewLayout(mBallView, mBallParams);
    }

    /** 解除贴边隐藏：悬浮球完全回到屏幕内（仍贴近原边缘），供点击/拖动前调用 */
    private void unDockBall() {
        if (!mBallDocked) return;
        int screenW = mWindowManager.getDefaultDisplay().getWidth();
        int ballSize = mBallParams.width;
        if (mBallParams.x < 0) {
            mBallParams.x = dp(8);
        } else {
            mBallParams.x = screenW - ballSize - dp(8);
        }
        mBallDocked = false;
        mWindowManager.updateViewLayout(mBallView, mBallParams);
    }

    // ==================== 悬浮小窗 ====================

    @SuppressLint("SetJavaScriptEnabled")
    private void createWindow(int screenW, int screenH) {
        mWindowView = LayoutInflater.from(this).inflate(R.layout.floating_window, null);
        mWindowView.setVisibility(View.GONE); // 初始只显示悬浮球

        // 无壳小窗尺寸：按当前屏幕方向计算（竖屏约 340×620，横屏自动压缩高度不溢出），
        // 方向切换后由 adaptWindowToScreen() 重新适配
        int[] winSize = computeWindowSize();
        mWindowParams = new WindowManager.LayoutParams(
                winSize[0], winSize[1],
                overlayType(),
                // 不加 NOT_FOCUSABLE：页面输入框需要能获得焦点弹出键盘。
                // 注意：不要依赖 FLAG_WATCH_OUTSIDE_TOUCH 做“点击窗口外收起”——该事件
                // 在可聚焦 overlay + 游戏/多数 ROM 场景收不到，收起已交给悬浮球完成
                WindowManager.LayoutParams.FLAG_LAYOUT_IN_SCREEN,
                PixelFormat.TRANSLUCENT);
        mWindowParams.gravity = Gravity.TOP | Gravity.START;

        mWebView = mWindowView.findViewById(R.id.floating_webview);
        WebSettings settings = mWebView.getSettings();
        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(true);
        settings.setUseWideViewPort(true);
        settings.setLoadWithOverviewMode(true);
        settings.setBuiltInZoomControls(true);
        settings.setDisplayZoomControls(false);
        // 用 UA 后缀自我标识悬浮窗小窗环境：遥控页据此区分 env-float(小窗) / env-full(桌面)
        settings.setUserAgentString(settings.getUserAgentString() + " KaguraXFloat/1.0");
        mWebView.setWebViewClient(new WebViewClient());

        // 网页内「收起」按钮（/float 右上角，仅悬浮窗显示）经此桥收起小窗：
        // 与“点击窗口外”等效但更直观可靠（不受触摸分发/ROM 差异影响）。
        // JS 回调在 WebView 线程，需切主线程操作窗口。
        Handler main = new Handler(Looper.getMainLooper());
        mWebView.addJavascriptInterface(new Object() {
            @JavascriptInterface
            public void collapse() {
                main.post(FloatingWindowService.this::collapseWindow);
            }
        }, "KaguraXBridge");

        // 系统返回键 / 全面屏返回手势兜底：在窗口内容层最顶层（根视图 dispatchKeyEvent）
        // 拦截。返回键无论焦点落在窗口内哪个子 View（含 WebView 网页内部）都会先经过根
        // 视图的分发，这里一定能收到：网页可后退时先后退，无历史则收起小窗。
        ((FloatPanelRoot) mWindowView).setBackRunnable(() -> {
            if (mWebView != null && mWebView.canGoBack()) {
                mWebView.goBack();
            } else {
                collapseWindow();
            }
        });

        mWindowManager.addView(mWindowView, mWindowParams);
    }

    /** 展开/收起小窗 */
    private void toggleWindow() {
        if (mWindowVisible) {
            collapseWindow();
        } else {
            showWindow();
        }
    }

    private void showWindow() {
        if (mWindowView == null) return;
        // 首次展开才加载页面；此后收起只隐藏，浏览状态保留
        if (mWebView.getUrl() == null) {
            mWebView.loadUrl(SERVICE_URL);
        }
        if (mWebViewPaused) {
            mWebView.onResume();
            mWebViewPaused = false;
        }

        // 每次展开都按当前屏幕适配尺寸（服务可能竖屏启动后进横屏游戏，不能沿用旧方向的尺寸）
        adaptWindowToScreen();

        int screenW = mWindowManager.getDefaultDisplay().getWidth();
        int screenH = mWindowManager.getDefaultDisplay().getHeight();
        int w = mWindowParams.width;
        int h = mWindowParams.height;
        // 悬浮球在哪一侧，小窗就贴该侧屏幕边缘展开（窗口只出现在左右边缘，不落中间）
        boolean ballLeft = (mBallParams.x + mBallParams.width / 2) < screenW / 2;
        mWindowDockedRight = !ballLeft;
        mWindowParams.x = ballLeft ? 0 : screenW - w;
        mWindowParams.y = Math.max(0, Math.min(mBallParams.y, screenH - h));
        // 展开期间隐藏悬浮球（不再占屏幕另一侧）；收起入口在遥控页左上角徽标 + 系统返回键
        mBallView.setVisibility(View.GONE);

        mWindowManager.updateViewLayout(mWindowView, mWindowParams);
        mWindowView.setVisibility(View.VISIBLE);
        mWindowVisible = true;
    }

    private void collapseWindow() {
        if (mWindowView == null) return;
        mWindowView.setVisibility(View.GONE);
        if (mWebView != null) {
            mWebView.onPause();
            mWebViewPaused = true;
        }
        // 收起：把隐藏的悬浮球恢复到小窗贴靠的同一条边缘半隐藏停靠
        int screenW = mWindowManager.getDefaultDisplay().getWidth();
        int screenH = mWindowManager.getDefaultDisplay().getHeight();
        int ballSize = mBallParams.width;
        if (mWindowDockedRight) {
            mBallParams.x = screenW - dp(DOCK_VISIBLE_DP); // 右边缘半隐藏
        } else {
            mBallParams.x = dp(DOCK_VISIBLE_DP) - ballSize; // 左边缘半隐藏
        }
        mBallParams.y = Math.max(0, Math.min(mWindowParams.y, screenH - ballSize));
        mBallDocked = true;
        mWindowManager.updateViewLayout(mBallView, mBallParams);
        mBallView.setVisibility(View.VISIBLE);
        mWindowVisible = false;
        saveBallPosition(mBallParams.x, mBallParams.y);
    }

    // ==================== 屏幕适配 ====================

    /** 按当前屏幕方向/尺寸计算小窗宽高：竖屏默认 300×520（较旧版更小），横屏压缩到可用高度内（不低于 240dp） */
    private int[] computeWindowSize() {
        int screenW = mWindowManager.getDefaultDisplay().getWidth();
        int screenH = mWindowManager.getDefaultDisplay().getHeight();
        int w = Math.min(dp(WINDOW_W_DP), screenW - dp(40));
        int h;
        if (getResources().getConfiguration().orientation == Configuration.ORIENTATION_LANDSCAPE) {
            // 横屏物理高度小：窗口接近满高、上下留边距，操作区不至于太局促
            h = Math.max(dp(240), screenH - dp(48));
        } else {
            // 竖屏：用目标小尺寸，并给小屏留出裕量（顶部避让、底部留白）
            h = Math.min(dp(WINDOW_H_DP), screenH - dp(96));
        }
        return new int[]{w, h};
    }

    /**
     * 屏幕方向/尺寸变化后，把小窗与悬浮球调整到新屏幕内：
     * 小窗按新方向重新计算宽高并保持贴靠原边缘；悬浮球保证不落到屏幕外。
     */
    private void adaptWindowToScreen() {
        if (mWindowView == null || mWindowParams == null) return;
        int screenW = mWindowManager.getDefaultDisplay().getWidth();
        int screenH = mWindowManager.getDefaultDisplay().getHeight();

        int[] size = computeWindowSize();
        if (mWindowParams.width != size[0] || mWindowParams.height != size[1]) {
            mWindowParams.width = size[0];
            mWindowParams.height = size[1];
            if (mWindowVisible) {
                // 展开中：旋转后仍贴靠原来的边缘（按新屏幕重新对齐）
                mWindowParams.x = mWindowDockedRight ? screenW - size[0] : 0;
            } else {
                mWindowParams.x = Math.max(0, Math.min(mWindowParams.x, screenW - size[0]));
            }
            mWindowParams.y = Math.max(0, Math.min(mWindowParams.y, screenH - size[1]));
            mWindowManager.updateViewLayout(mWindowView, mWindowParams);
        }
        if (mBallParams == null) return;
        // 悬浮球（展开期间隐藏中）：只保证没有落到屏幕外（半隐藏贴边的 x 不改变）
        mBallParams.y = Math.max(0, Math.min(mBallParams.y, screenH - mBallParams.width));
        mWindowManager.updateViewLayout(mBallView, mBallParams);
    }

    @Override
    public void onConfigurationChanged(Configuration newConfig) {
        super.onConfigurationChanged(newConfig);
        // 服务常驻后台，屏幕方向切换（例如进入横屏游戏）后窗口尺寸需跟随适配
        adaptWindowToScreen();
    }

    // ==================== 拖动、点击与调整大小 ====================

    /**
     * 通用拖动监听：按住移动改变窗口位置，松手且未发生位移（<touchSlop）时视为点击。
     * 悬浮球拖动中自由跟手（方便换边），松手时无条件吸附到最近的屏幕边缘（只出现在边缘）。
     *
     * @param window  窗口的顶层 View（即 addView 时添加的那个 View，updateViewLayout 用它）
     * @param params  目标窗口的 LayoutParams（x/y 会被更新）
     * @param onClick 点击回调（可为 null）
     */
    private View.OnTouchListener makeDragListener(final View window,
                                                  final WindowManager.LayoutParams params,
                                                  final View.OnClickListener onClick) {
        return (v, event) -> {
            switch (event.getActionMasked()) {
                case MotionEvent.ACTION_DOWN:
                    mTouchDownRawX = event.getRawX();
                    mTouchDownRawY = event.getRawY();
                    mTouchStartX = params.x;
                    mTouchStartY = params.y;
                    mDragging = false;
                    mWasDockedAtDown = (window == mBallView && mBallDocked);
                    if (mWasDockedAtDown) {
                        // 触摸贴边的悬浮球：先滑出，再跟手
                        unDockBall();
                        mTouchStartX = params.x;
                        mTouchStartY = params.y;
                    }
                    return true;
                case MotionEvent.ACTION_MOVE: {
                    float dx = event.getRawX() - mTouchDownRawX;
                    float dy = event.getRawY() - mTouchDownRawY;
                    if (!mDragging && (Math.abs(dx) > mTouchSlop || Math.abs(dy) > mTouchSlop)) {
                        mDragging = true;
                    }
                    if (mDragging) {
                        params.x = mTouchStartX + (int) dx;
                        params.y = mTouchStartY + (int) dy;
                        clampPosition(params, window);
                        // 拖动中自由跟手（悬浮球可被拖到屏幕中间以便换边），吸附在松手时处理
                        mWindowManager.updateViewLayout(window, params);
                    }
                    return true;
                }
                case MotionEvent.ACTION_UP:
                case MotionEvent.ACTION_CANCEL: {
                    if (mDragging) {
                        mDragging = false;
                        if (window == mBallView) {
                            // 松手：无条件吸附到最近的左/右边缘，悬浮球只出现在屏幕边缘
                            snapBallToEdge();
                            saveBallPosition(params.x, params.y);
                        }
                    } else if (onClick != null && !mWasDockedAtDown) {
                        // 贴边状态点击只滑出，不展开
                        onClick.onClick(v);
                    }
                    return true;
                }
            }
            return false;
        };
    }

    // 小窗不可拖动：展开位置固定贴悬浮球所在的那一侧屏幕边缘。
    // 想换边时收起小窗、把悬浮球拖到另一侧再展开即可。

    /** 把视图位置限制在屏幕内（拖动悬浮球时防止拖出屏幕找不回来） */
    private void clampPosition(WindowManager.LayoutParams params, View view) {
        int screenW = mWindowManager.getDefaultDisplay().getWidth();
        int screenH = mWindowManager.getDefaultDisplay().getHeight();
        int viewW = view.getWidth();
        int viewH = view.getHeight();
        int maxX = Math.max(0, screenW - viewW);
        int maxY = Math.max(0, screenH - viewH);
        params.x = Math.max(0, Math.min(params.x, maxX));
        params.y = Math.max(0, Math.min(params.y, maxY));
    }

    private void saveBallPosition(int x, int y) {
        getSharedPreferences(PREFS_NAME, MODE_PRIVATE)
                .edit()
                .putInt(PREF_BALL_X, x)
                .putInt(PREF_BALL_Y, y)
                .apply();
    }

    private void removeView(View view, WindowManager.LayoutParams params) {
        if (view != null) {
            try {
                mWindowManager.removeView(view);
            } catch (Exception e) {
                Log.w(LOG_TAG, "removeView failed: " + e.getMessage());
            }
        }
    }

    /** Android 8.0+ 用 TYPE_APPLICATION_OVERLAY，旧版本用 TYPE_PHONE */
    private int overlayType() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            return WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY;
        }
        return WindowManager.LayoutParams.TYPE_PHONE;
    }

    private int dp(int value) {
        return (int) (value * getResources().getDisplayMetrics().density + 0.5f);
    }
}
