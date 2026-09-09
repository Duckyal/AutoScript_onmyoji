package com.termux.app;

import android.content.Context;
import android.util.Log;

import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;

/**
 * AssetsUtils —— 把 assets/scripts 目录下的辅助脚本释放到 Termux home 目录，
 * 并赋予可执行权限，供 TermuxRunner 以 bash -c "~/xxx.sh" 方式调用。
 *
 * 释放目标：/data/data/duckyal.KaguraX/files/home/  （Termux 的 home 目录，即 ~）
 *
 * 为什么要释放而不是直接用 assets：
 *   RunCommandService 只能执行真实文件系统里的可执行文件，
 *   assets 里的脚本是打包在 APK 内的虚拟资源，bash 无法直接运行，
 *   所以必须先把脚本内容拷贝出来落盘。
 *
 * 更新策略（幂等 + 自动升级）：
 *   比较 assets 内脚本与磁盘上已存在脚本的 SHA-256，内容相同则跳过；
 *   内容不同（App 升级后脚本逻辑变了）则强制覆盖，保证手机上始终跑最新逻辑。
 *   旧版本只做「存在即跳过」会导致已安装用户永远拿不到换源等新逻辑，故改为哈希比对。
 *
 * 除脚本外，还会释放 termux-autobuilds.gpg（Termux 官方 apt 签名 key）：
 *   bootstrap 内置 termux-keyring 是旧版，缺少 Termux 2025 年启用的新签名 key
 *   （NO_PUBKEY 5A897D96E57CF20C），导致 pkg update 验签失败、仓库被禁用。
 *   key 文件随 APK 内置、本地落盘，setup_mirror.sh 直接 cp 到 trusted.gpg.d 即可，
 *   无需在线下载（此前在线拉取依赖 GitHub，国内网络不稳定会失败）。
 */
public final class AssetsUtils {

    private static final String LOG_TAG = "AssetsUtils";

    /** assets 下的脚本目录名 */
    private static final String SCRIPTS_ASSETS_DIR = "scripts";

    /** Termux home 目录（~）的绝对路径 */
    private static final String TERMUX_HOME_DIR = "/data/data/duckyal.KaguraX/files/home";

    /** 禁止实例化：纯工具类 */
    private AssetsUtils() {
    }

    /**
     * 确保所有辅助脚本与 GPG key 都已释放到 Termux home 目录（幂等：内容一致则跳过）。
     * 建议在 MainActivity.onCreate 中调用。
     *
     * @param context 上下文（用于访问 assets）
     */
    public static void ensureScripts(Context context) {
        releaseAsset(context, SCRIPTS_ASSETS_DIR, "setup_mirror.sh", true);    // Termux 换源脚本
        releaseAsset(context, SCRIPTS_ASSETS_DIR, "start.sh", true);           // 启动项目脚本
        releaseAsset(context, SCRIPTS_ASSETS_DIR, "init_container.sh", true);  // 容器初始化脚本
        releaseAsset(context, SCRIPTS_ASSETS_DIR, "proot_env.sh", true);       // proot 运行环境自愈（libtalloc / PD_PROOT_BIN）
        releaseAsset(context, SCRIPTS_ASSETS_DIR, "restore_container.sh", true); // 容器恢复包解压（免在线安装）
        releaseAsset(context, "", "termux-autobuilds.gpg", false);             // Termux 官方 apt 签名 key（修复 NO_PUBKEY）
    }

    /**
     * 释放单个资产文件：assets/[dir]/<name> → ~/<name>。
     * 若目标文件已存在且内容与 assets 一致则跳过（幂等）；
     * 若内容不一致（App 升级）则覆盖为最新版本。
     *
     * @param context    上下文
     * @param dir        assets 下子目录名（"" 表示 assets 根目录）
     * @param name       文件名，如 "setup_mirror.sh"
     * @param executable 是否需要可执行权限（脚本为 true，key 等数据文件为 false）
     */
    private static void releaseAsset(Context context, String dir, String name, boolean executable) {
        File target = new File(TERMUX_HOME_DIR, name);

        try {
            // 读取 assets 中的文件内容
            byte[] assetBytes = readAllBytesFromAsset(context, dir, name);
            String assetHash = sha256(assetBytes);

            // 磁盘上已存在且哈希一致：无需更新
            if (target.exists() && target.isFile()) {
                byte[] diskBytes = readAllBytes(new FileInputStream(target));
                if (sha256(diskBytes).equals(assetHash)) {
                    return;
                }
                Log.i(LOG_TAG, "文件内容有更新,覆盖: " + target.getAbsolutePath());
            }

            // 写入新内容
            // 注意:清除数据后首次启动时 bootstrap 可能尚未安装,Termux home 目录
            // 还不存在,必须先创建父目录,否则 FileOutputStream 会抛 FileNotFoundException。
            File parent = target.getParentFile();
            if (parent != null && !parent.exists() && !parent.mkdirs()) {
                Log.w(LOG_TAG, "创建目录失败: " + parent.getAbsolutePath());
            }
            try (FileOutputStream out = new FileOutputStream(target)) {
                out.write(assetBytes);
            }

            // 脚本需可执行权限（owner/group/others 均可执行），否则 bash 会报 Permission denied
            if (executable && !target.setExecutable(true, false)) {
                Log.w(LOG_TAG, "设置可执行权限失败: " + target.getAbsolutePath());
            }

            Log.i(LOG_TAG, "已释放文件: " + target.getAbsolutePath());
        } catch (IOException | NoSuchAlgorithmException e) {
            // assets 中文件缺失（打包时漏放）时容错：记录日志，不崩溃
            Log.w(LOG_TAG, "释放文件失败: " + name, e);
        }
    }

    /** 从 assets 读取整个文件为字节数组 */
    private static byte[] readAllBytesFromAsset(Context context, String dir, String name) throws IOException {
        String assetPath = dir.isEmpty() ? name : dir + "/" + name;
        try (InputStream in = context.getAssets().open(assetPath)) {
            return readAllBytes(in);
        }
    }

    /** 从输入流读取全部字节（8KB 缓冲） */
    private static byte[] readAllBytes(InputStream in) throws IOException {
        ByteArrayOutputStream out = new ByteArrayOutputStream();
        byte[] buffer = new byte[8192];
        int read;
        while ((read = in.read(buffer)) > 0) {
            out.write(buffer, 0, read);
        }
        return out.toByteArray();
    }

    /** 计算字节数组的 SHA-256 十六进制字符串 */
    private static String sha256(byte[] data) throws NoSuchAlgorithmException {
        MessageDigest digest = MessageDigest.getInstance("SHA-256");
        byte[] hash = digest.digest(data);
        StringBuilder sb = new StringBuilder(hash.length * 2);
        for (byte b : hash) {
            sb.append(Character.forDigit((b >> 4) & 0xF, 16));
            sb.append(Character.forDigit(b & 0xF, 16));
        }
        return sb.toString();
    }
}
