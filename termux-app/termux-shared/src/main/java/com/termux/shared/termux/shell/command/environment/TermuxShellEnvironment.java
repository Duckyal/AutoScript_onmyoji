package com.termux.shared.termux.shell.command.environment;

import android.content.Context;

import androidx.annotation.NonNull;

import com.termux.shared.errors.Error;
import com.termux.shared.file.FileUtils;
import com.termux.shared.logger.Logger;
import com.termux.shared.shell.command.ExecutionCommand;
import com.termux.shared.shell.command.environment.AndroidShellEnvironment;
import com.termux.shared.shell.command.environment.ShellEnvironmentUtils;
import com.termux.shared.shell.command.environment.ShellCommandShellEnvironment;
import com.termux.shared.termux.TermuxBootstrap;
import com.termux.shared.termux.TermuxConstants;
import com.termux.shared.termux.shell.TermuxShellUtils;

import java.io.File;
import java.nio.charset.Charset;
import java.util.HashMap;

/**
 * Environment for Termux.
 */
public class TermuxShellEnvironment extends AndroidShellEnvironment {

    private static final String LOG_TAG = "TermuxShellEnvironment";

    /** Environment variable for the termux {@link TermuxConstants#TERMUX_PREFIX_DIR_PATH}. */
    public static final String ENV_PREFIX = "PREFIX";

    public TermuxShellEnvironment() {
        super();
        shellCommandShellEnvironment = new TermuxShellCommandShellEnvironment();
    }


    /** Init {@link TermuxShellEnvironment} constants and caches. */
    public synchronized static void init(@NonNull Context currentPackageContext) {
        TermuxAppShellEnvironment.setTermuxAppEnvironment(currentPackageContext);
    }

    /** Init {@link TermuxShellEnvironment} constants and caches. */
    public synchronized static void writeEnvironmentToFile(@NonNull Context currentPackageContext) {
        HashMap<String, String> environmentMap = new TermuxShellEnvironment().getEnvironment(currentPackageContext, false);
        String environmentString = ShellEnvironmentUtils.convertEnvironmentToDotEnvFile(environmentMap);

        // Write environment string to temp file and then move to final location since otherwise
        // writing may happen while file is being sourced/read
        Error error = FileUtils.writeTextToFile("termux.env.tmp", TermuxConstants.TERMUX_ENV_TEMP_FILE_PATH,
            Charset.defaultCharset(), environmentString, false);
        if (error != null) {
            Logger.logErrorExtended(LOG_TAG, error.toString());
            return;
        }

        error = FileUtils.moveRegularFile("termux.env.tmp", TermuxConstants.TERMUX_ENV_TEMP_FILE_PATH, TermuxConstants.TERMUX_ENV_FILE_PATH, true);
        if (error != null) {
            Logger.logErrorExtended(LOG_TAG, error.toString());
        }
    }

    /** Get shell environment for Termux. */
    @NonNull
    @Override
    public HashMap<String, String> getEnvironment(@NonNull Context currentPackageContext, boolean isFailSafe) {

        // Termux environment builds upon the Android environment
        HashMap<String, String> environment = super.getEnvironment(currentPackageContext, isFailSafe);

        HashMap<String, String> termuxAppEnvironment = TermuxAppShellEnvironment.getEnvironment(currentPackageContext);
        if (termuxAppEnvironment != null)
            environment.putAll(termuxAppEnvironment);

        HashMap<String, String> termuxApiAppEnvironment = TermuxAPIShellEnvironment.getEnvironment(currentPackageContext);
        if (termuxApiAppEnvironment != null)
            environment.putAll(termuxApiAppEnvironment);

        environment.put(ENV_HOME, TermuxConstants.TERMUX_HOME_DIR_PATH);
        environment.put(ENV_PREFIX, TermuxConstants.TERMUX_PREFIX_DIR_PATH);

        // fork 改包名: 官方 bootstrap 的 ELF 二进制(curl/apt/openssl/wget/git/pip)内部
        // 硬编码 /data/data/com.termux/files/usr 作为 CA 证书与配置目录路径, 文本替换不
        // 作用于二进制, LD_LIBRARY_PATH 只解决动态库。必须用环境变量兜底, 否则 HTTPS 源
        // TLS 证书校验全部失败(termux-change-repo 测速全 Bad / pkg update 报错)。
        String prefix = TermuxConstants.TERMUX_PREFIX_DIR_PATH;
        String certFile = prefix + "/etc/tls/cert.pem";
        // 指向 fork 专用配置: 除 Dir::Etc/CAInfo 外还含临时目录键与修复 shebang 的
        // DPkg::Pre-Invoke 钩子。不能指向 apt.conf —— apt 读完 $APT_CONFIG 后还会按
        // Dir::Etc 重读 apt.conf, 钩子写在 apt.conf 里会被读成两条导致安装失败。
        environment.put("APT_CONFIG", prefix + "/etc/apt/apt.conf.fork");
        environment.put("CURL_CA_BUNDLE", certFile); // curl
        environment.put("SSL_CERT_FILE", certFile); // openssl/gnutls 通用
        environment.put("WGETRC", prefix + "/etc/wgetrc"); // GNU wget
        environment.put("GIT_SSL_CAINFO", certFile); // git
        environment.put("PIP_CERT", certFile); // python pip
        // python-pip 包 postinst 会执行 `pip config set --global ...` 写全局配置, pip 把
        // 全局配置文件解析为编译期写死的官方前缀 /data/data/com.termux/files/usr/etc/pip.conf,
        // fork 改包名后该路径不可写, 报 "PermissionError: [Errno 13] Permission denied:
        // '/data/data/com.termux'" 且 pip config set 输出 "ERROR: Unable to save configuration"。
        // PIP_CONFIG_FILE 让 pip 的读写统一落到真实前缀, 与 APT_CONFIG/WGETRC 同理。
        environment.put("PIP_CONFIG_FILE", prefix + "/etc/pip.conf");
        // dpkg 内部硬编码 /data/data/com.termux/files/usr/var/lib/dpkg 作为状态目录,
        // 用 DPKG_ADMINDIR 指到实际前缀, 否则 apt install 时 dpkg 报
        // "cannot create the dpkg database directory .../com.termux/...: Permission denied"。
        environment.put("DPKG_ADMINDIR", prefix + "/var/lib/dpkg");
        // 三方脚本(pip/platformdirs/proot-distro 等)普遍用 ${TERMUX__PREFIX:-/data/data/com.termux/files/usr}
        // 取前缀, 未设置时会回落到官方路径: proot-distro 因此报错
        // "'.../files/usr/../home/.local/share/proot-distro/containers' is not inside the proot-distro state tree"。
        // perl 的 @INC 编译时写死官方前缀(ELF 内, 文本替换无效), 未覆盖时 perl 脚本报
        // "Can't locate Cwd.pm in @INC (... /data/data/com.termux/files/usr/lib/perl5/5.x.y ...)".
        String perl5Lib = buildPerl5Lib(prefix);
        if (perl5Lib != null)
            environment.put("PERL5LIB", perl5Lib);

        // termux-exec input env vars (auto-exported by real termux-app >= 0.119.0).
        // These let libtermux-exec.so know the app data dir, prefix and our SELinux
        // process context to decide whether to use the system linker for ELF exec
        // (the untrusted_app W^X bypass). Without them it falls back to build-time
        // defaults from properties.sh which are correct for com.termux, but setting
        // them explicitly matches the official implementation.
        //
        // Use the canonical /data/data/com.termux path instead of
        // getApplicationInfo().dataDir (which returns /data/user/0/com.termux on
        // Android 11+): the bootstrap files physically live under /data/data/..., so
        // a string prefix match against TERMUX_APP__DATA_DIR must use that exact
        // prefix. termux-exec 2.4.0 does derive the legacy path from the data dir,
        // but passing the canonical path removes any ambiguity.
        String dataDir = TermuxConstants.TERMUX_INTERNAL_PRIVATE_APP_DATA_DIR_PATH;
        environment.put("TERMUX_APP__DATA_DIR", dataDir);
        environment.put("TERMUX_APP__LEGACY_DATA_DIR", dataDir);
        // proot-distro 用它取包名(constants.py: TERMUX_APP_PACKAGE = os.environ.get(
        // "TERMUX_APP__PACKAGE_NAME", "com.termux")), 未设置时回落官方包名, 于是把 tmp
        // 等路径算成 /data/data/com.termux/files/usr/tmp/, 登录容器时报
        // "can't canonicalize /data/data/com.termux/files/usr/tmp/: No such file or directory"。
        environment.put("TERMUX_APP__PACKAGE_NAME", TermuxConstants.TERMUX_PACKAGE_NAME);
        environment.put("TERMUX__PREFIX", TermuxConstants.TERMUX_PREFIX_DIR_PATH);
        // proot 的默认临时目录写死官方路径, 未覆盖时登录容器报
        // "can't canonicalize /data/data/com.termux/files/usr/tmp/" 并在创建 glue rootfs
        // 阶段中止。proot wrapper 也会兜底, 此处供直接调用 proot 的场景使用。
        environment.put("PROOT_TMP_DIR", TermuxConstants.TERMUX_TMP_PREFIX_DIR_PATH);
        environment.put("TERMUX__SE_PROCESS_CONTEXT", getSeProcessContext());
        // termux-exec 默认关闭日志;调试用 VVVERBOSE(6) 会产生大量输出,生产环境保持 off。

        // Android 10+ blocks untrusted_app from directly exec'ing ELF files under the app
        // data directory (app_data_file) due to SELinux W^X (no execute_no_trans). The
        // termux-exec library (bundled in the bootstrap) intercepts execve() via LD_PRELOAD
        // and rewrites it to load the ELF through the system linker (/system/bin/linker64),
        // which is permitted. Without this, bash works but every command it spawns (pkg, ls,
        // proot-distro, ...) fails with "Permission denied"/"bad interpreter".
        //
        // NOTE: termux-exec >= 1.x ships its main library as libtermux-exec-ld-preload.so;
        // libtermux-exec.so is only a backwards-compat symlink which may be left dangling
        // after a pkg upgrade, in which case every spawned process fails execve() with
        // "Permission denied" (observed as `proot error: execve("/usr/bin/bash"):
        // Permission denied`). Prefer the real main library, fall back to the legacy name.
        String termuxExecLib = TermuxConstants.TERMUX_LIB_PREFIX_DIR_PATH + "/libtermux-exec-ld-preload.so";
        if (!new File(termuxExecLib).isFile()) {
            termuxExecLib = TermuxConstants.TERMUX_LIB_PREFIX_DIR_PATH + "/libtermux-exec.so";
        }
        environment.put("LD_PRELOAD", termuxExecLib);

        // If failsafe is not enabled, then we keep default PATH and TMPDIR so that system binaries can be used
        if (!isFailSafe) {
            environment.put(ENV_TMPDIR, TermuxConstants.TERMUX_TMP_PREFIX_DIR_PATH);
            if (TermuxBootstrap.isAppPackageVariantAPTAndroid5()) {
                // Termux in android 5/6 era shipped busybox binaries in applets directory
                environment.put(ENV_PATH, TermuxConstants.TERMUX_BIN_PREFIX_DIR_PATH + ":" + TermuxConstants.TERMUX_BIN_PREFIX_DIR_PATH + "/applets");
                environment.put(ENV_LD_LIBRARY_PATH, TermuxConstants.TERMUX_LIB_PREFIX_DIR_PATH);
            } else {
                // NOTE (fork 包名): 官方 Termux 在 Android 7+ 依赖二进制自身的 DT_RUNPATH
                // (硬编码为 /data/data/com.termux/files/usr/lib)，所以不设 LD_LIBRARY_PATH。
                // 但本 fork 包名为 duckyal.KaguraX，bootstrap 内所有二进制的
                // DT_RUNPATH 仍是官方路径，linker 会因找不到库而报
                // "CANNOT LINK EXECUTABLE bash: library libandroid-support.so not found"。
                // LD_LIBRARY_PATH 优先级高于 DT_RUNPATH，必须显式设置为真实的 $PREFIX/lib。
                environment.put(ENV_PATH, TermuxConstants.TERMUX_BIN_PREFIX_DIR_PATH);
                environment.put(ENV_LD_LIBRARY_PATH, TermuxConstants.TERMUX_LIB_PREFIX_DIR_PATH);
            }
        }

        return environment;
    }


    @NonNull
    @Override
    public String getDefaultWorkingDirectoryPath() {
        return TermuxConstants.TERMUX_HOME_DIR_PATH;
    }

    @NonNull
    @Override
    public String getDefaultBinPath() {
        return TermuxConstants.TERMUX_BIN_PREFIX_DIR_PATH;
    }

    @NonNull
    @Override
    public String[] setupShellCommandArguments(@NonNull String executable, String[] arguments) {
        return TermuxShellUtils.setupShellCommandArguments(executable, arguments);
    }


    /**
     * 构造 $PERL5LIB, 覆盖 perl 二进制内写死的 @INC(官方前缀)。
     *
     * perl 的 @INC 在编译时固化进 ELF, fork 改包名后全部指向不存在的官方路径,
     * 文本替换对 ELF 无效, 只能通过 PERL5LIB 追加正确的模块搜索路径, 否则任何
     * perl 脚本都会在启动阶段失败:
     * "Can't locate Cwd.pm in @INC (... /data/data/com.termux/files/usr/lib/perl5/5.42.2 ...)".
     *
     * 需要覆盖的目录形如(版本与 ABI 均可能变化, 故运行时扫描):
     *   $PREFIX/lib/perl5/site_perl/<version>/<abi>
     *   $PREFIX/lib/perl5/site_perl/<version>
     *   $PREFIX/lib/perl5/<version>/<abi>
     *   $PREFIX/lib/perl5/<version>
     *
     * @param prefix 当前包名对应的 $PREFIX。
     * @return 冒号分隔的搜索路径;perl 未安装或目录不存在时返回 null。
     */
    private static String buildPerl5Lib(String prefix) {
        File perl5Dir = new File(prefix + "/lib/perl5");
        if (!perl5Dir.isDirectory()) return null;

        StringBuilder perl5Lib = new StringBuilder();
        File sitePerlDir = new File(perl5Dir, "site_perl");
        if (sitePerlDir.isDirectory())
            appendPerl5LibVersionDirs(perl5Lib, sitePerlDir);
        appendPerl5LibVersionDirs(perl5Lib, perl5Dir);

        return perl5Lib.length() == 0 ? null : perl5Lib.toString();
    }

    /** 把 base 下形如 5.42.2 的版本目录及其 ABI 子目录追加到 PERL5LIB。 */
    private static void appendPerl5LibVersionDirs(StringBuilder perl5Lib, File base) {
        File[] versionDirs = base.listFiles();
        if (versionDirs == null) return;

        for (File versionDir : versionDirs) {
            if (!versionDir.isDirectory()) continue;
            // 只处理 perl 版本目录(以数字开头), 排除 site_perl 等非版本目录
            if (!Character.isDigit(versionDir.getName().charAt(0))) continue;

            File[] abiDirs = versionDir.listFiles();
            if (abiDirs != null) {
                for (File abiDir : abiDirs) {
                    if (abiDir.isDirectory() && abiDir.getName().contains("android"))
                        appendPerl5LibPath(perl5Lib, abiDir.getAbsolutePath());
                }
            }
            appendPerl5LibPath(perl5Lib, versionDir.getAbsolutePath());
        }
    }

    private static void appendPerl5LibPath(StringBuilder perl5Lib, String path) {
        if (perl5Lib.length() > 0)
            perl5Lib.append(":");
        perl5Lib.append(path);
    }

    /** Cached current process SELinux context, read from /proc/self/attr/current. */
    private static String sSeProcessContext;

    /**
     * Read and cache the current process's SELinux context (e.g.
     * "u:r:untrusted_app_32:s0:c512,c768"). Exported to children as
     * {@code TERMUX__SE_PROCESS_CONTEXT} so termux-exec can decide whether
     * to use the system linker for ELF exec under app_data_file.
     */
    private static synchronized String getSeProcessContext() {
        if (sSeProcessContext == null) {
            StringBuilder sb = new StringBuilder();
            try (java.io.FileInputStream in = new java.io.FileInputStream("/proc/self/attr/current")) {
                byte[] buf = new byte[256];
                int n = in.read(buf);
                if (n > 0) sb.append(new String(buf, 0, n, "UTF-8"));
            } catch (Throwable t) {
                // ignore; empty string lets termux-exec fall back to /proc read
            }
            sSeProcessContext = sb.toString().trim();
        }
        return sSeProcessContext;
    }

}
