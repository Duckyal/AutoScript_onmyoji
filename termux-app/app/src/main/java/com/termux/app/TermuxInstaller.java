package com.termux.app;

import android.app.Activity;
import android.app.AlertDialog;
import android.app.ProgressDialog;
import android.content.Context;
import android.os.Build;
import android.os.Environment;
import android.system.Os;
import android.util.Pair;
import android.view.WindowManager;

import com.termux.R;
import com.termux.shared.file.FileUtils;
import com.termux.shared.termux.crash.TermuxCrashUtils;
import com.termux.shared.termux.file.TermuxFileUtils;
import com.termux.shared.interact.MessageDialogUtils;
import com.termux.shared.logger.Logger;
import com.termux.shared.markdown.MarkdownUtils;
import com.termux.shared.errors.Error;
import com.termux.shared.android.PackageUtils;
import com.termux.shared.termux.TermuxConstants;
import com.termux.shared.termux.TermuxUtils;
import com.termux.shared.termux.shell.command.environment.TermuxShellEnvironment;

import java.io.BufferedReader;
import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileOutputStream;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.List;
import java.util.zip.ZipEntry;
import java.util.zip.ZipInputStream;

import static com.termux.shared.termux.TermuxConstants.TERMUX_PREFIX_DIR;
import static com.termux.shared.termux.TermuxConstants.TERMUX_PREFIX_DIR_PATH;
import static com.termux.shared.termux.TermuxConstants.TERMUX_STAGING_PREFIX_DIR;
import static com.termux.shared.termux.TermuxConstants.TERMUX_STAGING_PREFIX_DIR_PATH;

/**
 * Install the Termux bootstrap packages if necessary by following the below steps:
 * <p/>
 * (1) If $PREFIX already exist, assume that it is correct and be done. Note that this relies on that we do not create a
 * broken $PREFIX directory below.
 * <p/>
 * (2) A progress dialog is shown with "Installing..." message and a spinner.
 * <p/>
 * (3) A staging directory, $STAGING_PREFIX, is cleared if left over from broken installation below.
 * <p/>
 * (4) The zip file is loaded from a shared library.
 * <p/>
 * (5) The zip, containing entries relative to the $PREFIX, is is downloaded and extracted by a zip input stream
 * continuously encountering zip file entries:
 * <p/>
 * (5.1) If the zip entry encountered is SYMLINKS.txt, go through it and remember all symlinks to setup.
 * <p/>
 * (5.2) For every other zip entry, extract it into $STAGING_PREFIX and set execute permissions if necessary.
 */
final class TermuxInstaller {

    private static final String LOG_TAG = "TermuxInstaller";

    /** 官方 Termux 前缀路径。fork 改包名后 bootstrap 内所有文本脚本(pkg/apt/proot-distro 等)的
     * shebang 与硬编码路径仍指向它, 必须替换为当前包名对应的 TERMUX_PREFIX_DIR_PATH。 */
    private static final String TERMUX_OFFICIAL_PREFIX = "/data/data/com.termux/files/usr";

    /** $PREFIX 下 TLS CA 证书文件路径(curl/openssl/git/pip 等二进制编译时写死官方路径, 需兜底)。 */
    private static final String TERMUX_TLS_CERT_FILE_PATH = TERMUX_PREFIX_DIR_PATH + "/etc/tls/cert.pem";

    /** $APT_CONFIG 指向的 fork 专用 apt 配置文件名(在 apt.conf 基础上追加 DPkg::Pre-Invoke 钩子)。 */
    private static final String TERMUX_FORK_APT_CONF_FILE_NAME = "apt.conf.fork";

    /** 修复 shebang 硬编码官方前缀的脚本, 由 apt 钩子与 dpkg wrapper 调用。 */
    private static final String TERMUX_FORK_FIX_SCRIPTS_FILE_NAME = "fix-maintainer-scripts.sh";

    /** Performs bootstrap setup if necessary. */
    static void setupBootstrapIfNeeded(final Activity activity, final Runnable whenDone) {
        String bootstrapErrorMessage;
        Error filesDirectoryAccessibleError;

        // This will also call Context.getFilesDir(), which should ensure that termux files directory
        // is created if it does not already exist
        filesDirectoryAccessibleError = TermuxFileUtils.isTermuxFilesDirectoryAccessible(activity, true, true);
        boolean isFilesDirectoryAccessible = filesDirectoryAccessibleError == null;

        // Termux can only be run as the primary user (device owner) since only that
        // account has the expected file system paths. Verify that:
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.N && !PackageUtils.isCurrentUserThePrimaryUser(activity)) {
            bootstrapErrorMessage = activity.getString(R.string.bootstrap_error_not_primary_user_message,
                MarkdownUtils.getMarkdownCodeForString(TERMUX_PREFIX_DIR_PATH, false));
            Logger.logError(LOG_TAG, "isFilesDirectoryAccessible: " + isFilesDirectoryAccessible);
            Logger.logError(LOG_TAG, bootstrapErrorMessage);
            sendBootstrapCrashReportNotification(activity, bootstrapErrorMessage);
            MessageDialogUtils.exitAppWithErrorMessage(activity,
                activity.getString(R.string.bootstrap_error_title),
                bootstrapErrorMessage);
            return;
        }

        if (!isFilesDirectoryAccessible) {
            bootstrapErrorMessage = Error.getMinimalErrorString(filesDirectoryAccessibleError);
            //noinspection SdCardPath
            if (PackageUtils.isAppInstalledOnExternalStorage(activity) &&
                !TermuxConstants.TERMUX_FILES_DIR_PATH.equals(activity.getFilesDir().getAbsolutePath().replaceAll("^/data/user/0/", "/data/data/"))) {
                bootstrapErrorMessage += "\n\n" + activity.getString(R.string.bootstrap_error_installed_on_portable_sd,
                    MarkdownUtils.getMarkdownCodeForString(TERMUX_PREFIX_DIR_PATH, false));
            }

            Logger.logError(LOG_TAG, bootstrapErrorMessage);
            sendBootstrapCrashReportNotification(activity, bootstrapErrorMessage);
            MessageDialogUtils.showMessage(activity,
                activity.getString(R.string.bootstrap_error_title),
                bootstrapErrorMessage, null);
            return;
        }

        // If prefix directory exists, even if its a symlink to a valid directory and symlink is not broken/dangling
        if (FileUtils.directoryFileExists(TERMUX_PREFIX_DIR_PATH, true)) {
            if (TermuxFileUtils.isTermuxPrefixDirectoryEmpty()) {
                Logger.logInfo(LOG_TAG, "The termux prefix directory \"" + TERMUX_PREFIX_DIR_PATH + "\" exists but is empty or only contains specific unimportant files.");
            } else if (isPrefixComplete()) {
                // fork 改包名: 修复旧版本已写入的 $PREFIX 中脚本的官方前缀
                // (shebang 仍指向 /data/data/com.termux/files/usr)。
                fixLegacyPrefixes();
                // 写入 apt.conf/wgetrc 兜底 ELF 二进制内硬编码的 CA 路径,
                // 并重写 termux.env 使新增的 CA/apt 环境变量(APT_CONFIG/CURL_CA_BUNDLE 等)生效。
                ensureForkCompatConfig();
                TermuxShellEnvironment.writeEnvironmentToFile(activity);
                whenDone.run();
                return;
            } else {
                // 目录存在但关键文件缺失(bin/bash、lib/libandroid-support.so 等)说明 bootstrap
                // 安装不完整(解压中断/被杀/空间不足等)。此时绝不能按"已装好"跳过,
                // 否则 bash 一执行就报 "CANNOT LINK EXECUTABLE \"bash\": library
                // \"libandroid-support.so\" not found"。继续走下方安装流程(先删后装)。
                Logger.logInfo(LOG_TAG, "The termux prefix directory \"" + TERMUX_PREFIX_DIR_PATH + "\" exists but is INCOMPLETE (missing critical files), re-installing bootstrap packages.");
            }
        } else if (FileUtils.fileExists(TERMUX_PREFIX_DIR_PATH, false)) {
            Logger.logInfo(LOG_TAG, "The termux prefix directory \"" + TERMUX_PREFIX_DIR_PATH + "\" does not exist but another file exists at its destination.");
        }

        final ProgressDialog progress = ProgressDialog.show(activity, null, activity.getString(R.string.bootstrap_installer_body), true, false);
        new Thread() {
            @Override
            public void run() {
                try {
                    Logger.logInfo(LOG_TAG, "Installing " + TermuxConstants.TERMUX_APP_NAME + " bootstrap packages.");

                    Error error;

                    // Delete prefix staging directory or any file at its destination
                    error = FileUtils.deleteFile("termux prefix staging directory", TERMUX_STAGING_PREFIX_DIR_PATH, true);
                    if (error != null) {
                        showBootstrapErrorDialog(activity, whenDone, Error.getErrorMarkdownString(error));
                        return;
                    }

                    // Delete prefix directory or any file at its destination
                    error = FileUtils.deleteFile("termux prefix directory", TERMUX_PREFIX_DIR_PATH, true);
                    if (error != null) {
                        showBootstrapErrorDialog(activity, whenDone, Error.getErrorMarkdownString(error));
                        return;
                    }

                    // Create prefix staging directory if it does not already exist and set required permissions
                    error = TermuxFileUtils.isTermuxPrefixStagingDirectoryAccessible(true, true);
                    if (error != null) {
                        showBootstrapErrorDialog(activity, whenDone, Error.getErrorMarkdownString(error));
                        return;
                    }

                    // Create prefix directory if it does not already exist and set required permissions
                    error = TermuxFileUtils.isTermuxPrefixDirectoryAccessible(true, true);
                    if (error != null) {
                        showBootstrapErrorDialog(activity, whenDone, Error.getErrorMarkdownString(error));
                        return;
                    }

                    Logger.logInfo(LOG_TAG, "Extracting bootstrap zip to prefix staging directory \"" + TERMUX_STAGING_PREFIX_DIR_PATH + "\".");

                    final byte[] buffer = new byte[8096];
                    final List<Pair<String, String>> symlinks = new ArrayList<>(50);

                    final byte[] zipBytes = loadZipBytes();
                    try (ZipInputStream zipInput = new ZipInputStream(new ByteArrayInputStream(zipBytes))) {
                        ZipEntry zipEntry;
                        while ((zipEntry = zipInput.getNextEntry()) != null) {
                            if (zipEntry.getName().equals("SYMLINKS.txt")) {
                                BufferedReader symlinksReader = new BufferedReader(new InputStreamReader(zipInput));
                                String line;
                                while ((line = symlinksReader.readLine()) != null) {
                                    String[] parts = line.split("←");
                                    if (parts.length != 2)
                                        throw new RuntimeException("Malformed symlink line: " + line);
                                    String oldPath = parts[0];
                                    String newPath = TERMUX_STAGING_PREFIX_DIR_PATH + "/" + parts[1];
                                    symlinks.add(Pair.create(oldPath, newPath));

                                    error = ensureDirectoryExists(new File(newPath).getParentFile());
                                    if (error != null) {
                                        showBootstrapErrorDialog(activity, whenDone, Error.getErrorMarkdownString(error));
                                        return;
                                    }
                                }
                            } else {
                                String zipEntryName = zipEntry.getName();
                                File targetFile = new File(TERMUX_STAGING_PREFIX_DIR_PATH, zipEntryName);
                                boolean isDirectory = zipEntry.isDirectory();

                                error = ensureDirectoryExists(isDirectory ? targetFile : targetFile.getParentFile());
                                if (error != null) {
                                    showBootstrapErrorDialog(activity, whenDone, Error.getErrorMarkdownString(error));
                                    return;
                                }

                                if (!isDirectory) {
                                    // 读整个文件到内存(bootstrap 内单文件都很小)
                                    ByteArrayOutputStream baos = new ByteArrayOutputStream();
                                    int readBytes;
                                    while ((readBytes = zipInput.read(buffer)) != -1)
                                        baos.write(buffer, 0, readBytes);
                                    byte[] fileBytes = baos.toByteArray();

                                    // fork 改包名: bootstrap 内所有文本脚本(pkg/apt/proot-distro 等)的
                                    // shebang 与硬编码路径仍指向官方 /data/data/com.termux/files/usr,
                                    // 必须替换为当前包名前缀,否则执行时报 "bad interpreter"。
                                    // 二进制(ELF)含 NUL 字节,自动跳过;其 DT_RUNPATH 由
                                    // TermuxShellEnvironment 设置的 LD_LIBRARY_PATH 覆盖。
                                    if (!containsNulByte(fileBytes)) {
                                        String content = new String(fileBytes, StandardCharsets.ISO_8859_1);
                                        if (content.contains(TERMUX_OFFICIAL_PREFIX)) {
                                            content = content.replace(TERMUX_OFFICIAL_PREFIX, TERMUX_PREFIX_DIR_PATH);
                                            fileBytes = content.getBytes(StandardCharsets.ISO_8859_1);
                                        }
                                    }

                                    try (FileOutputStream outStream = new FileOutputStream(targetFile)) {
                                        outStream.write(fileBytes);
                                    }
                                    if (zipEntryName.startsWith("bin/") || zipEntryName.startsWith("libexec") ||
                                        zipEntryName.startsWith("lib/apt/apt-helper") || zipEntryName.startsWith("lib/apt/methods")) {
                                        //noinspection OctalInteger
                                        Os.chmod(targetFile.getAbsolutePath(), 0700);
                                    }
                                }
                            }
                        }
                    }

                    // 补建 Termux 标准运行目录:部分 bootstrap 包以空目录形式打包,
                    // 若 ZIP 不含对应目录条目则解压后缺失,而 proot 等工具依赖
                    // $PREFIX/tmp 存放临时 loader 文件,缺失会报
                    // "can't chmod ... No such file" 并导致容器内 execve Permission denied。
                    for (String dirName : new String[]{"tmp", "var/log", "var/run"}) {
                        //noinspection ResultOfMethodCallIgnored
                        new File(TERMUX_STAGING_PREFIX_DIR_PATH + "/" + dirName).mkdirs();
                    }

                    if (symlinks.isEmpty())
                        throw new RuntimeException("No SYMLINKS.txt encountered");
                    for (Pair<String, String> symlink : symlinks) {
                        Os.symlink(symlink.first, symlink.second);
                    }

                    Logger.logInfo(LOG_TAG, "Moving termux prefix staging to prefix directory.");

                    if (!TERMUX_STAGING_PREFIX_DIR.renameTo(TERMUX_PREFIX_DIR)) {
                        throw new RuntimeException("Moving termux prefix staging to prefix directory failed");
                    }

                    Logger.logInfo(LOG_TAG, "Bootstrap packages installed successfully.");

                    // fork 改包名: 写入 apt.conf/wgetrc 兜底 ELF 二进制内硬编码的官方路径
                    ensureForkCompatConfig();

                    // Recreate env file since termux prefix was wiped earlier
                    TermuxShellEnvironment.writeEnvironmentToFile(activity);

                    activity.runOnUiThread(whenDone);

                } catch (final Exception e) {
                    showBootstrapErrorDialog(activity, whenDone, Logger.getStackTracesMarkdownString(null, Logger.getStackTracesStringArray(e)));

                } finally {
                    activity.runOnUiThread(() -> {
                        try {
                            progress.dismiss();
                        } catch (RuntimeException e) {
                            // Activity already dismissed - ignore.
                        }
                    });
                }
            }
        }.start();
    }

    public static void showBootstrapErrorDialog(Activity activity, Runnable whenDone, String message) {
        Logger.logErrorExtended(LOG_TAG, "Bootstrap Error:\n" + message);

        // Send a notification with the exception so that the user knows why bootstrap setup failed
        sendBootstrapCrashReportNotification(activity, message);

        activity.runOnUiThread(() -> {
            try {
                new AlertDialog.Builder(activity).setTitle(R.string.bootstrap_error_title).setMessage(R.string.bootstrap_error_body)
                    .setNegativeButton(R.string.bootstrap_error_abort, (dialog, which) -> {
                        dialog.dismiss();
                        activity.finish();
                    })
                    .setPositiveButton(R.string.bootstrap_error_try_again, (dialog, which) -> {
                        dialog.dismiss();
                        FileUtils.deleteFile("termux prefix directory", TERMUX_PREFIX_DIR_PATH, true);
                        TermuxInstaller.setupBootstrapIfNeeded(activity, whenDone);
                    }).show();
            } catch (WindowManager.BadTokenException e1) {
                // Activity already dismissed - ignore.
            }
        });
    }

    private static void sendBootstrapCrashReportNotification(Activity activity, String message) {
        final String title = TermuxConstants.TERMUX_APP_NAME + " Bootstrap Error";

        // Add info of all install Termux plugin apps as well since their target sdk or installation
        // on external/portable sd card can affect Termux app files directory access or exec.
        TermuxCrashUtils.sendCrashReportNotification(activity, LOG_TAG,
            title, null, "## " + title + "\n\n" + message + "\n\n" +
                TermuxUtils.getTermuxDebugMarkdownString(activity),
            true, false, TermuxUtils.AppInfoMode.TERMUX_AND_PLUGIN_PACKAGES, true);
    }

    static void setupStorageSymlinks(final Context context) {
        final String LOG_TAG = "termux-storage";
        final String title = TermuxConstants.TERMUX_APP_NAME + " Setup Storage Error";

        Logger.logInfo(LOG_TAG, "Setting up storage symlinks.");

        new Thread() {
            public void run() {
                try {
                    Error error;
                    File storageDir = TermuxConstants.TERMUX_STORAGE_HOME_DIR;

                    error = FileUtils.clearDirectory("~/storage", storageDir.getAbsolutePath());
                    if (error != null) {
                        Logger.logErrorAndShowToast(context, LOG_TAG, error.getMessage());
                        Logger.logErrorExtended(LOG_TAG, "Setup Storage Error\n" + error.toString());
                        TermuxCrashUtils.sendCrashReportNotification(context, LOG_TAG, title, null,
                            "## " + title + "\n\n" + Error.getErrorMarkdownString(error),
                            true, false, TermuxUtils.AppInfoMode.TERMUX_PACKAGE, true);
                        return;
                    }

                    Logger.logInfo(LOG_TAG, "Setting up storage symlinks at ~/storage/shared, ~/storage/downloads, ~/storage/dcim, ~/storage/pictures, ~/storage/music and ~/storage/movies for directories in \"" + Environment.getExternalStorageDirectory().getAbsolutePath() + "\".");

                    // Get primary storage root "/storage/emulated/0" symlink
                    File sharedDir = Environment.getExternalStorageDirectory();
                    Os.symlink(sharedDir.getAbsolutePath(), new File(storageDir, "shared").getAbsolutePath());

                    File documentsDir = Environment.getExternalStoragePublicDirectory(Environment.DIRECTORY_DOCUMENTS);
                    Os.symlink(documentsDir.getAbsolutePath(), new File(storageDir, "documents").getAbsolutePath());

                    File downloadsDir = Environment.getExternalStoragePublicDirectory(Environment.DIRECTORY_DOWNLOADS);
                    Os.symlink(downloadsDir.getAbsolutePath(), new File(storageDir, "downloads").getAbsolutePath());

                    File dcimDir = Environment.getExternalStoragePublicDirectory(Environment.DIRECTORY_DCIM);
                    Os.symlink(dcimDir.getAbsolutePath(), new File(storageDir, "dcim").getAbsolutePath());

                    File picturesDir = Environment.getExternalStoragePublicDirectory(Environment.DIRECTORY_PICTURES);
                    Os.symlink(picturesDir.getAbsolutePath(), new File(storageDir, "pictures").getAbsolutePath());

                    File musicDir = Environment.getExternalStoragePublicDirectory(Environment.DIRECTORY_MUSIC);
                    Os.symlink(musicDir.getAbsolutePath(), new File(storageDir, "music").getAbsolutePath());

                    File moviesDir = Environment.getExternalStoragePublicDirectory(Environment.DIRECTORY_MOVIES);
                    Os.symlink(moviesDir.getAbsolutePath(), new File(storageDir, "movies").getAbsolutePath());

                    File podcastsDir = Environment.getExternalStoragePublicDirectory(Environment.DIRECTORY_PODCASTS);
                    Os.symlink(podcastsDir.getAbsolutePath(), new File(storageDir, "podcasts").getAbsolutePath());

                    if (android.os.Build.VERSION.SDK_INT >= android.os.Build.VERSION_CODES.Q) {
                        File audiobooksDir = Environment.getExternalStoragePublicDirectory(Environment.DIRECTORY_AUDIOBOOKS);
                        Os.symlink(audiobooksDir.getAbsolutePath(), new File(storageDir, "audiobooks").getAbsolutePath());
                    }

                    // Dir 0 should ideally be for primary storage
                    // https://cs.android.com/android/platform/superproject/+/android-12.0.0_r32:frameworks/base/core/java/android/app/ContextImpl.java;l=818
                    // https://cs.android.com/android/platform/superproject/+/android-12.0.0_r32:frameworks/base/core/java/android/os/Environment.java;l=219
                    // https://cs.android.com/android/platform/superproject/+/android-12.0.0_r32:frameworks/base/core/java/android/os/Environment.java;l=181
                    // https://cs.android.com/android/platform/superproject/+/android-12.0.0_r32:frameworks/base/services/core/java/com/android/server/StorageManagerService.java;l=3796
                    // https://cs.android.com/android/platform/superproject/+/android-7.0.0_r36:frameworks/base/services/core/java/com/android/server/MountService.java;l=3053

                    // Create "Android/data/com.termux" symlinks
                    File[] dirs = context.getExternalFilesDirs(null);
                    if (dirs != null && dirs.length > 0) {
                        for (int i = 0; i < dirs.length; i++) {
                            File dir = dirs[i];
                            if (dir == null) continue;
                            String symlinkName = "external-" + i;
                            Logger.logInfo(LOG_TAG, "Setting up storage symlinks at ~/storage/" + symlinkName + " for \"" + dir.getAbsolutePath() + "\".");
                            Os.symlink(dir.getAbsolutePath(), new File(storageDir, symlinkName).getAbsolutePath());
                        }
                    }

                    // Create "Android/media/com.termux" symlinks
                    dirs = context.getExternalMediaDirs();
                    if (dirs != null && dirs.length > 0) {
                        for (int i = 0; i < dirs.length; i++) {
                            File dir = dirs[i];
                            if (dir == null) continue;
                            String symlinkName = "media-" + i;
                            Logger.logInfo(LOG_TAG, "Setting up storage symlinks at ~/storage/" + symlinkName + " for \"" + dir.getAbsolutePath() + "\".");
                            Os.symlink(dir.getAbsolutePath(), new File(storageDir, symlinkName).getAbsolutePath());
                        }
                    }

                    Logger.logInfo(LOG_TAG, "Storage symlinks created successfully.");
                } catch (Exception e) {
                    Logger.logErrorAndShowToast(context, LOG_TAG, e.getMessage());
                    Logger.logStackTraceWithMessage(LOG_TAG, "Setup Storage Error: Error setting up link", e);
                    TermuxCrashUtils.sendCrashReportNotification(context, LOG_TAG, title, null,
                        "## " + title + "\n\n" + Logger.getStackTracesMarkdownString(null, Logger.getStackTracesStringArray(e)),
                        true, false, TermuxUtils.AppInfoMode.TERMUX_PACKAGE, true);
                }
            }
        }.start();
    }

    private static Error ensureDirectoryExists(File directory) {
        return FileUtils.createDirectoryFile(directory.getAbsolutePath());
    }

    /**
     * 校验 $PREFIX 是否安装完整。
     * 仅判断目录存在/非空是不够的(解压中断会留下残缺环境),
     * 必须确认 bash 及其核心动态库 libandroid-support.so 都在。
     */
    private static boolean isPrefixComplete() {
        File bash = new File(TERMUX_PREFIX_DIR_PATH + "/bin/bash");
        File libSupport = new File(TERMUX_PREFIX_DIR_PATH + "/lib/libandroid-support.so");
        if (!bash.exists() || !libSupport.exists()) {
            Logger.logInfo(LOG_TAG, "Prefix incomplete: bash=" + bash.exists() + " libandroid-support.so=" + libSupport.exists());
            return false;
        }
        return true;
    }

    /** 判断字节数组是否含 NUL 字节(文本文件不含, ELF 二进制含, 用于区分脚本与二进制)。 */
    private static boolean containsNulByte(byte[] bytes) {
        for (byte b : bytes) {
            if (b == 0) return true;
        }
        return false;
    }

    /**
     * 修复已存在的 $PREFIX 中文本脚本的官方前缀。
     * fork 改包名后, 旧版本(或未走解压改写逻辑)安装的脚本其 shebang 与硬编码路径
     * 仍指向 /data/data/com.termux/files/usr, 直接执行会报 "bad interpreter"。
     * 遍历 $PREFIX 下所有目录, 对非 ELF 的文本文件做前缀替换(幂等, 已替换过的不会再改)。
     */
    private static void fixLegacyPrefixes() {
        try {
            fixLegacyPrefixInDirectory(new File(TERMUX_PREFIX_DIR_PATH));
        } catch (Exception e) {
            Logger.logError(LOG_TAG, "fixLegacyPrefixes failed: " + e.getMessage());
        }
    }

    private static void fixLegacyPrefixInDirectory(File dir) {
        File[] children = dir.listFiles();
        if (children == null) return;
        for (File child : children) {
            // fork 改包名: 符号链接的目标可能仍指向 /data/data/com.termux
            // (如 $PREFIX/etc/apt/trusted.gpg.d/*.gpg -> /data/data/com.termux/files/usr/share/
            // termux-keyring/*.gpg, 全是 broken link)。文本替换读的是链接目标内容, 对链接
            // 本身无效, 必须重建链接指向新前缀, 否则 apt 报 NO_PUBKEY(找不到公钥)。
            if (java.nio.file.Files.isSymbolicLink(child.toPath())) {
                try {
                    String target = java.nio.file.Files.readSymbolicLink(child.toPath()).toString();
                    if (target.contains(TERMUX_OFFICIAL_PREFIX)) {
                        java.nio.file.Files.delete(child.toPath());
                        java.nio.file.Files.createSymbolicLink(child.toPath(),
                            java.nio.file.Paths.get(target.replace(TERMUX_OFFICIAL_PREFIX, TERMUX_PREFIX_DIR_PATH)));
                        Logger.logInfo(LOG_TAG, "Fixed symlink prefix in " + child.getAbsolutePath());
                    }
                } catch (Exception ignored) {
                }
                continue;
            }
            if (child.isDirectory()) {
                // 跳过 lib/ 等二进制目录, 提升遍历速度
                if (child.getName().equals("lib") || child.getName().equals("share"))
                    continue;
                fixLegacyPrefixInDirectory(child);
            } else {
                try {
                    long len = child.length();
                    if (len <= 0 || len > 5 * 1024 * 1024) continue; // 跳过超大文件
                    try (java.io.FileInputStream fis = new java.io.FileInputStream(child)) {
                        byte[] bytes = new byte[(int) len];
                        int off = 0, read;
                        while (off < bytes.length && (read = fis.read(bytes, off, bytes.length - off)) != -1)
                            off += read;
                        if (containsNulByte(bytes)) continue; // ELF 二进制, 跳过
                        String content = new String(bytes, StandardCharsets.ISO_8859_1);
                        if (content.contains(TERMUX_OFFICIAL_PREFIX)) {
                            content = content.replace(TERMUX_OFFICIAL_PREFIX, TERMUX_PREFIX_DIR_PATH);
                            try (java.io.FileOutputStream fos = new java.io.FileOutputStream(child)) {
                                fos.write(content.getBytes(StandardCharsets.ISO_8859_1));
                            }
                            Logger.logInfo(LOG_TAG, "Fixed prefix in " + child.getAbsolutePath());
                        }
                    }
                } catch (Exception ignored) {
                    // 单个文件失败不影响其他
                }
            }
        }
    }

    /**
     * 写入 fork 适配配置文件, 兜底 ELF 二进制内硬编码的官方路径。
     * 官方 bootstrap 的 curl/apt/openssl/wget/git 等编译时写死 /data/data/com.termux/files/usr:
     * 文本替换不作用于 ELF, LD_LIBRARY_PATH 只能解决动态库, 而 CA 证书与 apt/wget 配置目录
     * 必须通过配置文件 + 环境变量(TermuxShellEnvironment)兜底, 否则 HTTPS 源 TLS 校验全部
     * 失败(curl: "error adding trust anchors", apt: "Unable to read .../com.termux/.../apt.conf.d")。
     * 幂等: 文件已存在且内容一致则跳过, 保留用户手动改动。
     */
    private static void ensureForkCompatConfig() {
        try {
            String prefix = TERMUX_PREFIX_DIR_PATH;

            // apt/dpkg 运行所需的目录, 首次启动时补齐。
            String[] dirs = {
                prefix + "/tmp",
                prefix + "/var/lib/apt/lists/partial",
                prefix + "/var/cache/apt/archives/partial",
                prefix + "/var/log/apt",
            };
            for (String d : dirs) {
                File dir = new File(d);
                if (!dir.isDirectory() && !dir.mkdirs())
                    Logger.logWarn(LOG_TAG, "Could not create dir: " + d);
            }

            // 1) apt: 修正全部 Dir::* 配置目录、外部命令路径与 CA 证书。
            //    apt 由 $APT_CONFIG 环境变量指到本文件, 启动时最先读入并覆盖编译默认路径。
            //    官方 bootstrap 的 libapt-pkg.so 编译时把 /data/data/com.termux/files/usr 写死进
            //    Dir::Etc/Dir::State/Dir::Bin 及 Dir::Bin::apt-key/dpkg/zstd 等默认值, 文本替换
            //    不作用于 ELF, 必须逐条用配置覆盖, 否则: 找不到 sources.list / apt-key 无法执行
            //    (Couldn't execute .../com.termux/.../bin/apt-key) / dpkg 报 Permission denied。
            String aptConf = buildAptConf(prefix, false);
            File aptConfFile = new File(prefix + "/etc/apt/apt.conf");
            if (!aptConfFile.exists() || !aptConf.equals(readFileContent(aptConfFile))) {
                writeFileContent(aptConfFile, aptConf);
                Logger.logInfo(LOG_TAG, "Wrote fork compat apt.conf: " + aptConfFile.getAbsolutePath());
            }

            // 供 $APT_CONFIG 使用的配置文件: 与 apt.conf 相同, 额外挂 DPkg::Pre-Invoke 钩子。
            // 单独成文件的原因: apt 读完 $APT_CONFIG 后还会按其中的 Dir::Etc 再读一次
            // Dir::Etc::main(即 apt.conf), 若钩子写在 apt.conf 里会被读成两条, apt 2.8
            // 的钩子子进程随即失败并报 "E: Sub-process returned an error code"。
            String aptConfFork = buildAptConf(prefix, true);
            File aptConfForkFile = new File(prefix + "/etc/apt/" + TERMUX_FORK_APT_CONF_FILE_NAME);
            if (!aptConfForkFile.exists() || !aptConfFork.equals(readFileContent(aptConfForkFile))) {
                writeFileContent(aptConfForkFile, aptConfFork);
                Logger.logInfo(LOG_TAG, "Wrote fork apt config: " + aptConfForkFile.getAbsolutePath());
            }

            ensureForkFixScriptsFile(prefix);
            ensureDpkgWrapper(prefix);
            // 先装 wrapper(它负责把 proot 备份成 proot-real), 再修 proot-real 的
            // RUNPATH —— 首次运行时 proot-real 还不存在。
            ensureProotWrapper(prefix);
            ensureProotRunpath(prefix);

            // 3) 符号链接: $PREFIX/data/data/com.termux -> 包根。官方 deb 包内路径含
            //    data/data/com.termux 前缀, dpkg --root=$PREFIX 后该路径落到
            //    $PREFIX/data/data/com.termux/..., 经此链接指向 /data/data/<本包名>, 最终
            //    装到正确的 $PREFIX/bin 等位置。若缺失, 装包时报 "Permission denied"。
            File dataDataDir = new File(prefix + "/data/data");
            File comTermuxLink = new File(dataDataDir, "com.termux");
            if (!java.nio.file.Files.isSymbolicLink(comTermuxLink.toPath())) {
                if (!dataDataDir.isDirectory() && !dataDataDir.mkdirs())
                    Logger.logWarn(LOG_TAG, "Could not create dir: " + dataDataDir.getAbsolutePath());
                java.nio.file.Files.deleteIfExists(comTermuxLink.toPath());
                java.nio.file.Files.createSymbolicLink(comTermuxLink.toPath(),
                    java.nio.file.Paths.get("../../../.."));
                Logger.logInfo(LOG_TAG, "Created symlink " + comTermuxLink.getAbsolutePath() + " -> ../../../..");
            }

            // 2) wget: 修正 CA 证书路径(由 $WGETRC 环境变量指到本文件)。
            String wgetrc = "ca_certificate = " + TERMUX_TLS_CERT_FILE_PATH + "\n";
            File wgetrcFile = new File(TERMUX_PREFIX_DIR_PATH + "/etc/wgetrc");
            if (!wgetrcFile.exists() || !wgetrc.equals(readFileContent(wgetrcFile))) {
                writeFileContent(wgetrcFile, wgetrc);
                Logger.logInfo(LOG_TAG, "Wrote fork compat wgetrc: " + wgetrcFile.getAbsolutePath());
            }

            // 4) pip: 配置文件由 PIP_CONFIG_FILE 环境变量指到本文件(python-pip postinst 的
            //    `pip config set --global` 与用户 pip 命令都会读写它)。预置清华镜像源,
            //    避免境内访问官方 PyPI 缓慢; disable-pip-version-check 与 python-pip
            //    postinst 写入的键保持一致, 触发重写时不会丢掉镜像配置。
            String pipConf =
                "[global]\n" +
                "index-url = https://pypi.tuna.tsinghua.edu.cn/simple\n" +
                "disable-pip-version-check = true\n";
            File pipConfFile = new File(TERMUX_PREFIX_DIR_PATH + "/etc/pip.conf");
            if (!pipConfFile.exists() || !pipConf.equals(readFileContent(pipConfFile))) {
                writeFileContent(pipConfFile, pipConf);
                Logger.logInfo(LOG_TAG, "Wrote fork compat pip.conf: " + pipConfFile.getAbsolutePath());
            }
        } catch (Exception e) {
            Logger.logError(LOG_TAG, "ensureForkCompatConfig failed: " + e.getMessage());
        }
    }

    /**
     * 生成 fork 适配的 apt 配置。
     *
     * 除覆盖 libapt-pkg.so 内写死的 Dir::* 默认值外, 还必须覆盖它的临时目录键:
     * apt 在写 eipp 日志和执行 DPkg::Pre-Invoke 钩子时会 fork 子进程并
     * chdir("/data/data/com.termux/files/usr/tmp/")(编译期默认值), 该路径在无 root 的
     * fork 上不存在, 子进程直接 _exit(100), 表现为任何 apt install 都失败并只报
     * "E: Sub-process returned an error code" 而没有任何 dpkg 输出。
     * 该键未导出到 apt-config, 故这里把所有可能的候选键一并写上(多余键 apt 会忽略)。
     *
     * @param prefix   当前包名对应的 $PREFIX。
     * @param withHook 是否追加修复 shebang 的 DPkg::Pre-Invoke 钩子。
     *                 注意必须用标量写法(不能写成 DPkg::Pre-Invoke { ... };),
     *                 列表写法会让 apt 的钩子子进程失败。
     */
    private static String buildAptConf(String prefix, boolean withHook) {
        String conf =
            "Dir::Etc \"" + prefix + "/etc/apt/\";\n" +
            "Dir::Etc::sourcelist \"" + prefix + "/etc/apt/sources.list\";\n" +
            "Dir::Etc::tmp \"" + prefix + "/tmp/\";\n" +
            "Dir::State \"" + prefix + "/var/lib/apt/\";\n" +
            "Dir::State::status \"" + prefix + "/var/lib/dpkg/status\";\n" +
            "Dir::Cache \"" + prefix + "/var/cache/apt/\";\n" +
            "Dir::Log \"" + prefix + "/var/log/apt/\";\n" +
            "Dir::Bin \"" + prefix + "/bin/\";\n" +
            "Dir::Bin::methods \"" + prefix + "/lib/apt/methods/\";\n" +
            "Dir::Bin::apt-key \"" + prefix + "/bin/apt-key\";\n" +
            "Dir::Bin::dpkg \"" + prefix + "/bin/dpkg\";\n" +
            "Dir::Bin::zstd \"" + prefix + "/bin/zstd\";\n" +
            "Dir::Bin::xz \"" + prefix + "/bin/xz\";\n" +
            "Dir::Bin::gzip \"" + prefix + "/bin/gzip\";\n" +
            "Dir::Bin::bzip2 \"" + prefix + "/bin/bzip2\";\n" +
            "Dir::Bin::lz4 \"" + prefix + "/bin/lz4\";\n" +
            "Dir::Bin::lzma \"" + prefix + "/bin/lzma\";\n" +
            "Dir::Bin::sh \"" + prefix + "/bin/sh\";\n" +
            "Dir::Bin::bash \"" + prefix + "/bin/bash\";\n" +
            "Dir::Bin::df \"" + prefix + "/bin/df\";\n" +
            "Dir::Bin::login \"" + prefix + "/bin/login\";\n" +
            "Dir::Bin::ionice \"" + prefix + "/bin/ionice\";\n" +
            "Dir::Bin::dmesg \"" + prefix + "/bin/dmesg\";\n" +
            // apt 用它检测是否处于 chroot, 默认 /usr/bin/ischroot(不存在)会让安装直接失败。
            "Dir::Bin::ischroot \"" + prefix + "/bin/ischroot\";\n" +
            "Dir::Temp \"" + prefix + "/tmp/\";\n" +
            "Dir::Tmp \"" + prefix + "/tmp/\";\n" +
            "Dir::TempDir \"" + prefix + "/tmp/\";\n" +
            "Dir::Etc::Temp \"" + prefix + "/tmp/\";\n" +
            "Dir::State::Temp \"" + prefix + "/tmp/\";\n" +
            "Dir::Log::Temp \"" + prefix + "/tmp/\";\n" +
            "Dir::Cache::Temp \"" + prefix + "/tmp/\";\n" +
            "Dir::Bin::Temp \"" + prefix + "/tmp/\";\n" +
            "APT::Temp \"" + prefix + "/tmp/\";\n" +
            "APT::TempDir \"" + prefix + "/tmp/\";\n" +
            "APT::Eipp::TempDir \"" + prefix + "/tmp/\";\n" +
            "EIPP::TempDir \"" + prefix + "/tmp/\";\n" +
            "EIPP::Temp \"" + prefix + "/tmp/\";\n" +
            "Acquire::https::CAInfo \"" + TERMUX_TLS_CERT_FILE_PATH + "\";\n" +
            // dpkg 子进程拿到的 PATH 默认只有官方前缀的 bin, 导致 checkpath 找不到
            // sh/rm/tar/diff/dpkg-deb/start-stop-daemon 而中止。
            "DPkg::Path \"" + prefix + "/bin:" + prefix + "/bin/applets\";\n" +
            // 官方 deb 包内路径是 ./data/data/com.termux/files/usr/..., 必须让 dpkg
            // 以 $PREFIX 为安装根, 再经 data/data/com.termux 符号链接(指向包根)还原
            // 出真实目标路径, 否则 dpkg 会尝试写 /data/data/com.termux(无权限)。
            "DPkg::Options {\n" +
            "  \"--root=" + prefix + "\";\n" +
            "  \"--force-not-root\";\n" +
            "  \"--force-script-chrootless\";\n" +
            "};\n";

        if (withHook) {
            conf += "DPkg::Pre-Invoke \"" + prefix + "/etc/apt/" +
                TERMUX_FORK_FIX_SCRIPTS_FILE_NAME + "\";\n";
        }

        return conf;
    }

    /**
     * 写入 shebang 修复脚本。它把硬编码官方前缀的 shebang 改写成本包名前缀,
     * 覆盖两类文件: dpkg 维护者脚本(info 目录)与 $PREFIX/bin 下已安装的可执行脚本
     * (pip3/proot-distro/clang 工具链/termux-chroot 等)。
     * 只用 bash 内建实现, 不依赖 PATH 里能找到 head/grep/sed。
     */
    private static void ensureForkFixScriptsFile(String prefix) {
        try {
            String official = TERMUX_OFFICIAL_PREFIX;
            // 脚本本体: 以本包名前缀的 bash 为解释器, 逻辑全部使用内建命令。
            String body =
                "#!" + prefix + "/bin/bash\n" +
                "PREFIX=\"" + prefix + "\"\n" +
                "OFFICIAL=\"" + official + "\"\n" +
                "INFO=\"$PREFIX/var/lib/dpkg/info\"\n" +
                "\n" +
                "fix_file() {\n" +
                "   local f=\"$1\" first content newfirst rest\n" +
                "   [ -f \"$f\" ] && [ -s \"$f\" ] || return 0\n" +
                "   IFS= read -r first < \"$f\" 2>/dev/null || return 0\n" +
                "   case \"$first\" in\n" +
                "      \"#!\"*\"$OFFICIAL\"*) ;;\n" +
                "      *) return 0 ;;\n" +
                "   esac\n" +
                "   content=$(<\"$f\") || return 0\n" +
                "   newfirst=\"${first/\"$OFFICIAL\"/\"$PREFIX\"}\"\n" +
                "   rest=\"${content#*\"$first\"}\"\n" +
                "   printf '%s\\n%s' \"$newfirst\" \"$rest\" > \"$f\"\n" +
                "}\n" +
                "\n" +
                "# 1) dpkg 维护者脚本。含 update-alternatives 的只改 shebang:\n" +
                "#    它会自行剥离官方前缀, 把参数一并改掉会造成前缀重复而失败。\n" +
                "#    另注: dpkg 运行维护者脚本时会剥离环境变量白名单以外的变量\n" +
                "#    (PIP_CONFIG_FILE 不在白名单内), 因此 python 包 postinst 里\n" +
                "#    `pip config set --global` 写全局配置时解析到编译期写死的官方前缀\n" +
                "#    /data/data/com.termux/... 而报 PermissionError。这里把\n" +
                "#    PIP_CONFIG_FILE 以字面路径写进 postinst 正文, 运行时必然生效。\n" +
                "for f in \"$INFO\"/*.postinst \"$INFO\"/*.preinst \"$INFO\"/*.prerm \"$INFO\"/*.postrm; do\n" +
                "   [ -f \"$f\" ] || continue\n" +
                "   IFS= read -r first < \"$f\" || continue\n" +
                "   case \"$first\" in\n" +
                "      \"#!\"*\"$OFFICIAL\"*) ;;\n" +
                "      *) continue ;;\n" +
                "   esac\n" +
                "   content=$(<\"$f\") || continue\n" +
                "   newfirst=\"${first/\"$OFFICIAL\"/\"$PREFIX\"}\"\n" +
                "   rest=\"${content#*\"$first\"}\"\n" +
                "   pip_inject=\"\"\n" +
                "   case \"$f\" in\n" +
                "      *.postinst)\n" +
                "         case \"$content\" in\n" +
                "            *PIP_CONFIG_FILE*) : ;;\n" +
                "            *) pip_inject=\"export PIP_CONFIG_FILE=\\\"$PREFIX/etc/pip.conf\\\"\" ;;\n" +
                "         esac\n" +
                "         ;;\n" +
                "   esac\n" +
                "   case \"$content\" in\n" +
                "      *update-alternatives*)\n" +
                "         [ -z \"$pip_inject\" ] && printf '%s\\n%s' \"$newfirst\" \"$rest\" > \"$f\" \\\n" +
                "            || printf '%s\\n%s\\n%s' \"$newfirst\" \"$pip_inject\" \"$rest\" > \"$f\"\n" +
                "         ;;\n" +
                "      *)\n" +
                "         [ -z \"$pip_inject\" ] && printf '%s\\n%s' \"$newfirst\" \"${rest//\"$OFFICIAL\"/\"$PREFIX\"}\" > \"$f\" \\\n" +
                "            || printf '%s\\n%s\\n%s' \"$newfirst\" \"$pip_inject\" \"${rest//\"$OFFICIAL\"/\"$PREFIX\"}\" > \"$f\"\n" +
                "         ;;\n" +
                "   esac\n" +
                "done\n" +
                "\n" +
                "# 2) $PREFIX/bin 与 bin/applets 下已安装的可执行脚本。\n" +
                "for dir in \"$PREFIX/bin\" \"$PREFIX/bin/applets\"; do\n" +
                "   [ -d \"$dir\" ] || continue\n" +
                "   for f in \"$dir\"/*; do\n" +
                "      fix_file \"$f\"\n" +
                "   done\n" +
                "done\n" +
                "\n" +
                "# 3) py3compile/py3clean: Debian 移植脚本, 内部用编译期写死的官方前缀拼解释器\n" +
                "#    路径判断 python 版本是否已安装, fork 上必然判定为未安装, 报\n" +
                "#    \"E: py3compile:NNN: Requested versions are not installed\" 并退出 1,\n" +
                "#    导致调用它们的包(postinst 配置阶段)配置失败。整文件做前缀替换修复\n" +
                "#    (版本判断逻辑可能在 lib/python3.x/debpython 模块里, 一并处理)。\n" +
                "for f in \"$PREFIX/bin/py3compile\" \"$PREFIX/bin/py3clean\" \"$PREFIX\"/lib/python3.*/debpython/*; do\n" +
                "   [ -f \"$f\" ] && [ -s \"$f\" ] || continue\n" +
                "   content=$(<\"$f\") || continue\n" +
                "   case \"$content\" in\n" +
                "      *\"$OFFICIAL\"*)\n" +
                "         printf '%s' \"${content//\"$OFFICIAL\"/\"$PREFIX\"}\" > \"$f\"\n" +
                "         ;;\n" +
                "   esac\n" +
                "done\n" +
                "\n" +
                "exit 0\n";

            File aptDir = new File(prefix + "/etc/apt");
            if (!aptDir.isDirectory() && !aptDir.mkdirs())
                Logger.logWarn(LOG_TAG, "Could not create dir: " + aptDir.getAbsolutePath());

            File scriptFile = new File(aptDir, TERMUX_FORK_FIX_SCRIPTS_FILE_NAME);
            if (!scriptFile.exists() || !body.equals(readFileContent(scriptFile))) {
                writeFileContent(scriptFile, body);
                Logger.logInfo(LOG_TAG, "Wrote fork compat fix script: " + scriptFile.getAbsolutePath());
            }
            try {
                Os.chmod(scriptFile.getAbsolutePath(), 0755);
            } catch (Exception e) {
                // 忽略: 部分文件系统不支持 chmod
            }
        } catch (Exception e) {
            Logger.logError(LOG_TAG, "ensureForkFixScriptsFile failed: " + e.getMessage());
        }
    }

    /**
     * 把 dpkg 换成调用修复脚本后再转发给真实 dpkg 的 wrapper。
     *
     * apt 安装时把 unpack 与 configure 放在同一次 dpkg 调用里, 而 DPkg::Pre-Invoke 钩子
     * 只在调用前执行一次, 无法修复刚从 deb 解压出来的维护者脚本(其 shebang 写死官方
     * 前缀, 执行时报 "No such file or directory")。改在 dpkg 入口处修复才能覆盖该时序。
     * 升级 dpkg 包会覆盖本 wrapper, 故每次启动时重新确保一次。
     */
    private static void ensureDpkgWrapper(String prefix) {
        try {
            File dpkgFile = new File(prefix + "/bin/dpkg");
            File dpkgRealFile = new File(prefix + "/bin/dpkg-real");
            String fixScript = prefix + "/etc/apt/" + TERMUX_FORK_FIX_SCRIPTS_FILE_NAME;

            // 真实 dpkg 尚未备份时先备份; 已是 wrapper 则说明之前备份过。
            if (dpkgFile.isFile()) {
                String firstLine = readFileContent(dpkgFile);
                boolean isWrapper = firstLine != null && firstLine.contains("dpkg-real");
                if (!isWrapper) {
                    if (!dpkgRealFile.exists() && !dpkgFile.renameTo(dpkgRealFile)) {
                        Logger.logWarn(LOG_TAG, "Could not rename dpkg to dpkg-real");
                        return;
                    }
                }
            }

            if (!dpkgRealFile.isFile()) {
                Logger.logWarn(LOG_TAG, "Real dpkg missing, skip installing dpkg wrapper");
                return;
            }

            // 仅在安装/卸载/配置类调用前修复, 查询类调用(如 --print-foreign-architectures)
            // 直接放行, 避免每次 apt 操作都遍历脚本目录。
            // 解释器用 /system/bin/sh: dpkg 可能在没有 LD_LIBRARY_PATH 的环境里被调用,
            // 而 $PREFIX/bin/bash 自身依赖 LD_LIBRARY_PATH, 届时连 wrapper 都起不来。
            // PIP_CONFIG_FILE: python-pip 包 postinst 执行 `pip config set --global` 写全局
            // 配置。pip 把全局配置路径解析为编译期写死的官方前缀 /data/data/com.termux/...,
            // fork 上不可写报 "PermissionError: [Errno 13] Permission denied: '/data/data/com.termux'"。
            // 与其依赖调用方(TermuxShellEnvironment)透传, 不如在此强制注入: 所有 apt/dpkg 调用
            // 都必经本 wrapper, postinst 环境 100% 生效(文件由 ensureForkCompatConfig 预置)。
            String wrapper =
                "#!/system/bin/sh\n" +
                "PREFIX=\"" + prefix + "\"\n" +
                "export LD_LIBRARY_PATH=\"$PREFIX/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}\"\n" +
                "export PIP_CONFIG_FILE=\"$PREFIX/etc/pip.conf\"\n" +
                "case \" $* \" in\n" +
                "  *\" --configure \"*|*\" -i \"*|*\" --install \"*|*\" --unpack \"*|" +
                "*\" -r \"*|*\" --remove \"*|*\" --purge \"*)\n" +
                "    \"$PREFIX/bin/bash\" \"" + fixScript + "\"\n" +
                "    ;;\n" +
                "esac\n" +
                "exec \"$PREFIX/bin/dpkg-real\" \"$@\"\n";

            if (!dpkgFile.exists() || !wrapper.equals(readFileContent(dpkgFile))) {
                writeFileContent(dpkgFile, wrapper);
                Logger.logInfo(LOG_TAG, "Wrote dpkg wrapper: " + dpkgFile.getAbsolutePath());
            }
            try {
                Os.chmod(dpkgFile.getAbsolutePath(), 0755);
                Os.chmod(dpkgRealFile.getAbsolutePath(), 0755);
            } catch (Exception e) {
                // 忽略
            }
        } catch (Exception e) {
            Logger.logError(LOG_TAG, "ensureDpkgWrapper failed: " + e.getMessage());
        }
    }

    /** proot 的 DT_RUNPATH 默认值(编译期写死的官方 lib 目录)。 */
    private static final String PROOT_OFFICIAL_RUNPATH = TERMUX_OFFICIAL_PREFIX + "/lib";

    /** 改写后的 RUNPATH: 相对 proot 自身位置, 与包名无关且比原值短, 可原地覆盖。 */
    private static final String PROOT_FIXED_RUNPATH = "$ORIGIN/../lib";

    /**
     * 修正 proot 的 RUNPATH。
     *
     * proot 升级后 RUNPATH 会回到官方路径, 所以每次启动都检查; 已是期望值则跳过。
     * 修好后 proot 不依赖 LD_LIBRARY_PATH 即可启动, 容器环境也得以保持干净。
     */
    private static void ensureProotRunpath(String prefix) {
        try {
            File prootReal = new File(prefix + "/bin/proot-real");
            if (!prootReal.isFile() || !isElfFile(prootReal)) return;

            String runpath = readElfRunpath(prootReal);
            if (runpath == null) return;
            if (PROOT_FIXED_RUNPATH.equals(runpath)) return;      // 已修好($ORIGIN 相对, 与包名无关)
            if (PROOT_OFFICIAL_RUNPATH.equals(runpath)) {
                if (patchElfRunpath(prootReal, PROOT_OFFICIAL_RUNPATH, PROOT_FIXED_RUNPATH))
                    Logger.logInfo(LOG_TAG, "Patched proot RUNPATH -> " + PROOT_FIXED_RUNPATH);
                return;
            }
            if (runpath.startsWith(prefix + "/lib")) return;       // 已是当前前缀, 无需动
            // 旧 fork/改名迁移(如 ASOnmyoji→KaguraX 数据迁移/旧版恢复包)带来的 proot-real:
            // RUNPATH 是已不存在的旧包名数据目录绝对路径。旧值比 $ORIGIN/../lib 长,
            // 可安全就地覆盖为相对路径, 否则干净环境下启动即 CANNOT LINK libtalloc。
            if (runpath.startsWith("/data/data/") && runpath.endsWith("/files/usr/lib")) {
                if (patchElfRunpath(prootReal, runpath, PROOT_FIXED_RUNPATH))
                    Logger.logInfo(LOG_TAG, "Patched stale proot RUNPATH -> " + PROOT_FIXED_RUNPATH);
            }
        } catch (Exception e) {
            Logger.logError(LOG_TAG, "ensureProotRunpath failed: " + e.getMessage());
        }
    }

    /** 读取 ELF 的 DT_RUNPATH/DT_RPATH 字符串, 不存在或解析失败返回 null。 */
    private static String readElfRunpath(File file) {
        try (java.io.RandomAccessFile raf = new java.io.RandomAccessFile(file, "r")) {
            byte[] e_ident = new byte[16];
            raf.readFully(e_ident);
            if (e_ident[0] != 0x7f || e_ident[1] != 'E' || e_ident[2] != 'L' || e_ident[3] != 'F')
                return null;
            boolean le = e_ident[5] == 1;
            if (e_ident[4] != 2) return null;

            raf.seek(0x20);
            long phoff = readLong(raf, le);
            raf.seek(0x36);
            int phentsize = readShort(raf, le) & 0xffff;
            int phnum = readShort(raf, le) & 0xffff;
            if (phoff <= 0 || phentsize <= 0 || phnum <= 0) return null;

            long dynOff = -1, dynSize = 0;
            java.util.List<long[]> loads = new java.util.ArrayList<>();
            for (int i = 0; i < phnum; i++) {
                long base = phoff + (long) i * phentsize;
                raf.seek(base);
                int p_type = readInt(raf, le);
                if (p_type == 1) {
                    raf.seek(base + 0x08);
                    long p_offset = readLong(raf, le);
                    raf.seek(base + 0x10);
                    long p_vaddr = readLong(raf, le);
                    raf.seek(base + 0x28);
                    long p_memsz = readLong(raf, le);
                    loads.add(new long[]{p_vaddr, p_memsz, p_offset});
                } else if (p_type == 2) {
                    // PT_DYNAMIC: 用 p_vaddr(@0x10) 而非 p_offset(@0x08) 换算文件偏移,
                    // vaddrToOffset() 期望的是虚拟地址。
                    raf.seek(base + 0x10);
                    dynOff = readLong(raf, le);
                    raf.seek(base + 0x20);
                    dynSize = readLong(raf, le);
                }
            }
            long dynFileOff = vaddrToOffset(loads, dynOff);
            if (dynFileOff < 0) return null;

            long strTabAddr = -1, strSize = 0, runpathVal = -1;
            for (long pos = 0; pos + 16 <= dynSize; pos += 16) {
                raf.seek(dynFileOff + pos);
                long d_tag = readLong(raf, le);
                long d_val = readLong(raf, le);
                if (d_tag == 0) break;
                if (d_tag == 5) strTabAddr = d_val;
                else if (d_tag == 10) strSize = d_val;
                else if (d_tag == 15 || d_tag == 29) runpathVal = d_val;
            }
            if (strTabAddr < 0 || runpathVal < 0 || runpathVal >= strSize) return null;

            long strTabOff = vaddrToOffset(loads, strTabAddr);
            if (strTabOff < 0) return null;

            raf.seek(strTabOff + runpathVal);
            byte[] buf = new byte[256];
            int n = raf.read(buf);
            if (n <= 0) return null;
            return readCString(buf);
        } catch (Exception e) {
            Logger.logDebug(LOG_TAG, "readElfRunpath failed: " + e.getMessage());
            return null;
        }
    }

    /**
     * 就地改写 ELF 的 DT_RUNPATH/DT_RPATH 字符串。
     *
     * 为什么必须改而不是用 LD_LIBRARY_PATH: proot-distro 登录容器时会为容器构造
     * "干净"环境(剔除宿主侧的 LD_LIBRARY_PATH, 否则容器内的 glibc 程序会去加载
     * Termux 的库, 报 "libc.so: cannot open shared object file")。这就与 proot 自身
     * 启动需要 LD_LIBRARY_PATH 相矛盾 —— 而 app 进程又无法执行 patchelf(SELinux
     * W^X + 该二进制同样依赖 LD_LIBRARY_PATH)。写死路径 /data/data/com.termux/...
     * 在 fork 上不存在, 于是 proot 在干净环境里启动即失败:
     * "CANNOT LINK EXECUTABLE .../bin/proot: library libtalloc.so.2 not found"。
     *
     * 新值用 $ORIGIN 相对定位(相对二进制所在目录), 既与包名无关, 长度又短于原值,
     * 因此可以直接覆盖 dynstr 中原来的字符串, 无需重排 ELF 各段。
     *
     * @param file    目标 ELF(会被就地修改)。
     * @param oldValue 期望的原 RUNPATH, 不匹配则不动。
     * @param newValue 新值, 长度不得大于 oldValue。
     * @return 是否发生了修改。
     */
    private static boolean patchElfRunpath(File file, String oldValue, String newValue) {
        if (newValue.length() > oldValue.length()) {
            Logger.logWarn(LOG_TAG, "New RUNPATH longer than old one, skip: " + newValue);
            return false;
        }
        try (java.io.RandomAccessFile raf = new java.io.RandomAccessFile(file, "rw")) {
            // ---- ELF header ----
            byte[] e_ident = new byte[16];
            raf.readFully(e_ident);
            if (e_ident[0] != 0x7f || e_ident[1] != 'E' || e_ident[2] != 'L' || e_ident[3] != 'F')
                return false;
            boolean littleEndian = e_ident[5] == 1;
            boolean is64 = e_ident[4] == 2;
            if (!is64) return false; // 只处理 arm64/x86_64;32 位留待需要时再支持

            // e_phoff(0x20, 8B), e_phentsize(0x36, 2B), e_phnum(0x38, 2B)
            raf.seek(0x20);
            long phoff = readLong(raf, littleEndian);
            raf.seek(0x36);
            int phentsize = readShort(raf, littleEndian) & 0xffff;
            int phnum = readShort(raf, littleEndian) & 0xffff;
            if (phoff <= 0 || phentsize <= 0 || phnum <= 0) return false;

            // ---- 收集 PT_LOAD(vaddr->offset 映射) 与 PT_DYNAMIC ----
            long dynOff = -1, dynSize = 0;
            java.util.List<long[]> loads = new java.util.ArrayList<>(); // {vaddr, memsz, offset}
            for (int i = 0; i < phnum; i++) {
                long base = phoff + (long) i * phentsize;
                raf.seek(base);
                int p_type = readInt(raf, littleEndian);
                if (p_type == 1) { // PT_LOAD: p_offset@0x08, p_vaddr@0x10, p_filesz@0x20, p_memsz@0x28
                    raf.seek(base + 0x08);
                    long p_offset = readLong(raf, littleEndian);
                    raf.seek(base + 0x10);
                    long p_vaddr = readLong(raf, littleEndian);
                    raf.seek(base + 0x28);
                    long p_memsz = readLong(raf, littleEndian);
                    loads.add(new long[]{p_vaddr, p_memsz, p_offset});
                } else if (p_type == 2) { // PT_DYNAMIC: 同上, 用 p_vaddr 换算文件偏移
                    raf.seek(base + 0x10);
                    dynOff = readLong(raf, littleEndian);
                    raf.seek(base + 0x20);
                    dynSize = readLong(raf, littleEndian);
                }
            }
            if (dynOff < 0 || dynSize <= 0) return false;

            // 虚拟地址 -> 文件偏移
            java.util.Map<Long, long[]> byAddr = new java.util.HashMap<>();
            for (long[] l : loads) byAddr.put(l[0], l);
            long dynFileOff = vaddrToOffset(loads, dynOff);
            if (dynFileOff < 0) return false;

            // ---- 遍历 .dynamic ----
            long strTabAddr = -1, strSize = 0, runpathVal = -1;
            for (long pos = 0; pos + 16 <= dynSize; pos += 16) {
                raf.seek(dynFileOff + pos);
                long d_tag = readLong(raf, littleEndian);
                long d_val = readLong(raf, littleEndian);
                if (d_tag == 0) break; // DT_NULL
                if (d_tag == 5) strTabAddr = d_val;        // DT_STRTAB
                else if (d_tag == 10) strSize = d_val;     // DT_STRSZ
                else if (d_tag == 15 || d_tag == 29) runpathVal = d_val; // DT_RPATH / DT_RUNPATH
            }
            if (strTabAddr < 0 || runpathVal < 0) return false;

            long strTabOff = vaddrToOffset(loads, strTabAddr);
            if (strTabOff < 0) return false;
            long targetOff = strTabOff + runpathVal;
            if (runpathVal < 0 || runpathVal >= strSize) return false;

            // ---- 校验当前值, 匹配则原地覆盖(补 0) ----
            raf.seek(targetOff);
            byte[] cur = new byte[oldValue.length() + 1];
            raf.readFully(cur);
            String curStr = readCString(cur);
            if (!oldValue.equals(curStr)) return false;

            byte[] nb = new byte[oldValue.length() + 1];
            byte[] vb = newValue.getBytes(StandardCharsets.ISO_8859_1);
            System.arraycopy(vb, 0, nb, 0, vb.length); // 剩余字节保持 0
            raf.seek(targetOff);
            raf.write(nb);
            return true;
        } catch (Exception e) {
            Logger.logDebug(LOG_TAG, "patchElfRunpath failed: " + e.getMessage());
            return false;
        }
    }

    /** 在 PT_LOAD 表中把虚拟地址换算成文件偏移, 失败返回 -1。 */
    private static long vaddrToOffset(java.util.List<long[]> loads, long vaddr) {
        for (long[] l : loads) {
            if (vaddr >= l[0] && vaddr < l[0] + l[1])
                return l[2] + (vaddr - l[0]);
        }
        return -1;
    }

    private static String readCString(byte[] buf) {
        int len = 0;
        while (len < buf.length && buf[len] != 0) len++;
        return new String(buf, 0, len, StandardCharsets.ISO_8859_1);
    }

    private static int readShort(java.io.RandomAccessFile raf, boolean le) throws java.io.IOException {
        int b0 = raf.read(), b1 = raf.read();
        return le ? (b0 | (b1 << 8)) : ((b0 << 8) | b1);
    }

    private static int readInt(java.io.RandomAccessFile raf, boolean le) throws java.io.IOException {
        int b0 = raf.read(), b1 = raf.read(), b2 = raf.read(), b3 = raf.read();
        return le ? (b0 | (b1 << 8) | (b2 << 16) | (b3 << 24))
                  : ((b0 << 24) | (b1 << 16) | (b2 << 8) | b3);
    }

    private static long readLong(java.io.RandomAccessFile raf, boolean le) throws java.io.IOException {
        long lo = readInt(raf, le) & 0xffffffffL;
        long hi = readInt(raf, le) & 0xffffffffL;
        return le ? (lo | (hi << 32)) : ((hi << 32) | lo);
    }

    /**
     * 供 MainActivity「一键初始化」期间轮询调用(幂等):
     * 全新安装时 bootstrap 阶段 proot 尚未安装, ensureForkCompatConfig() 里
     * ensureProotWrapper() 会因 proot 文件不存在而直接返回; pkg install proot
     * 落盘后由本方法补做 wrapper 备份与 DT_RUNPATH 修复。
     */
    static void ensureProotRuntime(String prefix) {
        ensureProotWrapper(prefix);
        ensureProotRunpath(prefix);
    }

    /**
     * 为 proot 生成 wrapper, 自行导出 LD_LIBRARY_PATH 后再转发给真实二进制。
     *
     * proot 的 DT_RUNPATH 写死官方 lib 目录, 平时靠 shell 会话里的 LD_LIBRARY_PATH
     * 兜底。但 proot 多由 proot-distro(python) 以子进程方式启动, 该调用环境不保证
     * 带上 LD_LIBRARY_PATH, linker 随即报:
     * "CANNOT LINK EXECUTABLE .../bin/proot: library libtalloc.so.2 not found"。
     * wrapper 在自身进程内导出库路径, 因此与调用方环境无关。
     * 升级 proot 包会覆盖本 wrapper, 故每次启动时重新确保一次。
     */
    private static void ensureProotWrapper(String prefix) {
        try {
            File prootFile = new File(prefix + "/bin/proot");
            File prootRealFile = new File(prefix + "/bin/proot-real");
            if (!prootFile.isFile()) return; // proot 尚未安装

            // 仅处理真实的 ELF 二进制, 已是 wrapper(脚本)时不再备份
            if (isElfFile(prootFile)) {
                if (!prootRealFile.exists() && !prootFile.renameTo(prootRealFile)) {
                    Logger.logWarn(LOG_TAG, "Could not rename proot to proot-real");
                    return;
                }
            }

            if (!prootRealFile.isFile()) {
                Logger.logWarn(LOG_TAG, "Real proot missing, skip installing proot wrapper");
                return;
            }

            // 解释器必须是 /system/bin/sh: proot 常在没有 LD_LIBRARY_PATH 的环境里
            // 被启动(proot-distro 为避免宿主库污染容器会构造干净环境), 而
            // $PREFIX/bin/bash 自身也依赖 LD_LIBRARY_PATH, 用它当解释器会同样
            // CANNOT LINK 失败。
            //
            // PROOT_LOADER(关键): proot 的扩展 ELF loader 路径写死为
            // /data/data/com.termux/files/usr/libexec/proot/loader, 该路径在 fork 上
            // 不存在, 于是执行容器内任何程序都失败:
            // "proot error: execve("/usr/bin/bash"): No such file or directory
            //  ... the loader was not found or doesn't work."
            // 只能靠环境变量覆盖, 且必须写在 wrapper 里 —— 放在 shell 环境里会被
            // proot-distro 清理掉(它构造容器环境时会剔除宿主侧的 LD_*/PROOT_* 变量)。
            //
            // PROOT_TMP_DIR: proot 默认的临时目录同样是官方路径, 未覆盖时报
            // "can't canonicalize /data/data/com.termux/files/usr/tmp/" 并在创建
            // glue rootfs 阶段中止。
            //
            // 不要在此导出 LD_LIBRARY_PATH: 它会随 proot 传进容器, 让容器内的 glibc
            // 程序去加载宿主的库, 同样表现为 "the loader was not found or doesn't
            // work"。proot 找不到库的问题改由 ensureProotRunpath() 修 RUNPATH 解决。
            String wrapper =
                "#!/system/bin/sh\n" +
                "export PROOT_LOADER=\"" + prefix + "/libexec/proot/loader\"\n" +
                "export PROOT_TMP_DIR=\"${PROOT_TMP_DIR:-" + prefix + "/tmp}\"\n" +
                "exec \"" + prefix + "/bin/proot-real\" \"$@\"\n";

            if (!prootFile.exists() || !wrapper.equals(readFileContent(prootFile))) {
                writeFileContent(prootFile, wrapper);
                Logger.logInfo(LOG_TAG, "Wrote proot wrapper: " + prootFile.getAbsolutePath());
            }
            try {
                Os.chmod(prootFile.getAbsolutePath(), 0755);
                Os.chmod(prootRealFile.getAbsolutePath(), 0755);
            } catch (Exception e) {
                // 忽略
            }
        } catch (Exception e) {
            Logger.logError(LOG_TAG, "ensureProotWrapper failed: " + e.getMessage());
        }
    }

    /** 判断文件是否为 ELF(前 4 字节为 0x7f 'E' 'L' 'F')。 */
    private static boolean isElfFile(File file) {
        try (java.io.FileInputStream fis = new java.io.FileInputStream(file)) {
            byte[] magic = new byte[4];
            return fis.read(magic) == 4 && magic[0] == 0x7f && magic[1] == 'E'
                && magic[2] == 'L' && magic[3] == 'F';
        } catch (Exception e) {
            return false;
        }
    }

    private static String readFileContent(File file) {
        try (java.io.FileInputStream fis = new java.io.FileInputStream(file)) {
            byte[] bytes = new byte[(int) file.length()];
            int off = 0, read;
            while (off < bytes.length && (read = fis.read(bytes, off, bytes.length - off)) != -1)
                off += read;
            return new String(bytes, StandardCharsets.ISO_8859_1);
        } catch (Exception e) {
            return null;
        }
    }

    private static void writeFileContent(File file, String content) throws java.io.IOException {
        java.io.FileOutputStream fos = new java.io.FileOutputStream(file);
        try {
            fos.write(content.getBytes(StandardCharsets.ISO_8859_1));
        } finally {
            fos.close();
        }
    }

    public static byte[] loadZipBytes() {
        // Only load the shared library when necessary to save memory usage.
        System.loadLibrary("termux-bootstrap");
        return getZip();
    }

    public static native byte[] getZip();

}
