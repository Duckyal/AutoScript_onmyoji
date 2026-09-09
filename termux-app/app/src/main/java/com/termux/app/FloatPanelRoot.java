package com.termux.app;

import android.content.Context;
import android.util.AttributeSet;
import android.view.KeyEvent;
import android.widget.FrameLayout;

/**
 * 悬浮小窗窗口内容的根视图（floating_window.xml 的根元素）。
 *
 * 注意必须做成顶层类：布局 XML 里引用的自定义视图，LayoutInflater 会用
 * Class.forName("com.termux.app.X") 直接反射加载；若把类写成某服务类的静态嵌套类，
 * 字节码里的类名是 "$" 分隔的（如 ...FloatingWindowService$FloatPanelRoot），
 * 点号写法在运行时找不到，会抛 ClassNotFoundException 导致窗口 inflate 失败。
 *
 * 作用：在窗口内容层的最顶层拦截系统返回键/全面屏返回手势——WindowManager 把按键
 * 先派发给窗口的顶层 View（即 addView 时添加的根视图），因此在这里拦截能覆盖窗口内
 * 任意子 View（含 WebView 网页内部）持有焦点的情况，比监听某个子 View 可靠得多。
 */
public class FloatPanelRoot extends FrameLayout {

    private Runnable mBackRunnable;

    public FloatPanelRoot(Context context, AttributeSet attrs) {
        super(context, attrs);
    }

    void setBackRunnable(Runnable runnable) {
        mBackRunnable = runnable;
    }

    @Override
    public boolean dispatchKeyEvent(KeyEvent event) {
        if (event.getKeyCode() == KeyEvent.KEYCODE_BACK
                && event.getAction() == KeyEvent.ACTION_DOWN
                && mBackRunnable != null) {
            mBackRunnable.run();
            return true; // 消费掉返回键，避免再往下传
        }
        return super.dispatchKeyEvent(event);
    }
}
