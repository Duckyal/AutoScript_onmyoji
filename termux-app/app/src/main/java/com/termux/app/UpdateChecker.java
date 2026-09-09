package com.termux.app;

import java.io.ByteArrayOutputStream;
import java.io.BufferedReader;
import java.io.File;
import java.io.FileInputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.List;

import org.json.JSONArray;
import org.json.JSONObject;

import com.termux.BuildConfig;

/**
 * UpdateChecker —— 项目与 App 更新检测。
 *
 * 检测两部分（互不影响，各自失败只影响各自结果）：
 *
 * 1. 项目代码（容器内 /root/app）：
 *    - 本地版本记录 ~/repo_version.txt 保存项目仓库当前 commit SHA
 *      （由 init_container.sh / 更新命令在安装完成后写入）。
 *    - 请求 GitHub API 获取最近 20 个提交，对比本地 SHA 之后的提交 = 新提交。
 *
 * 2. App（APK 本身）：
 *    - 请求 GitHub Releases API（releases/latest），仅当最新 Release 带 .apk asset
 *      （如 tag app-v1.0；恢复包 container-v1 只有 tar.gz，不算 App 发布）时，
 *      把 tag 归一化（app-v1.0 → 1.0.0）后与本地已安装版本
 *      （BuildConfig.VERSION_NAME，1.0.0）做 semver 数字比较，远端更大即提示下载新 APK。
 *
 * 注意：
 *   - GitHub API 强制要求 User-Agent 请求头，否则返回 403。
 *   - 403 通常是未带 User-Agent 或匿名请求超限，需要单独提示用户。
 *   - 本类只做「检测 + 解析」，弹窗交互由 MainActivity 负责。
 */
public final class UpdateChecker {

    /** 项目仓库所属用户/组织 */
    public static final String REPO_OWNER = "Duckyal";

    /** 项目仓库名 */
    public static final String REPO_NAME = "KaguraX";

    /** GitHub API：获取最近 20 条提交（按时间从新到旧排列） */
    private static final String COMMITS_API_URL =
            "https://api.github.com/repos/" + REPO_OWNER + "/" + REPO_NAME + "/commits?per_page=20";

    /** GitHub API：获取最新 Release（用于 APK 版本检测） */
    private static final String LATEST_RELEASE_API_URL =
            "https://api.github.com/repos/" + REPO_OWNER + "/" + REPO_NAME + "/releases/latest";

    /** 本地版本记录文件（Termux home 下，App 用 Java File API 直接读写） */
    public static final String VERSION_FILE_PATH =
            "/data/data/duckyal.KaguraX/files/home/repo_version.txt";

    /** 连接/读取超时（毫秒） */
    private static final int TIMEOUT_MS = 15000;

    /** 禁止实例化：纯工具类 */
    private UpdateChecker() {
    }

    /**
     * 单条提交信息（供对话框展示）。
     */
    public static class CommitInfo {
        /** 完整 commit SHA */
        public String sha;

        /** 提交信息第一行（去掉多行描述的换行部分） */
        public String message;

        /** 提交日期，格式 yyyy-MM-dd */
        public String date;
    }

    /**
     * 一次检测的完整结果（成功/失败、本地 SHA、新提交列表、APK 版本）。
     */
    public static class CheckResult {
        /** 项目检测是否成功（false 时看 rateLimited 区分原因） */
        public boolean success;

        /** 是否命中 GitHub API 限流（HTTP 403） */
        public boolean rateLimited;

        /** 本地版本记录中的 SHA；null = 项目未安装（无版本文件） */
        public String localSha;

        /** 远端列表中最新的 SHA；null = API 返回空 */
        public String latestSha;

        /** 相对本地 SHA 的所有新提交（从新到旧）；空 = 已是最新 */
        public List<CommitInfo> newCommits = new ArrayList<>();

        // ===== APK 版本检测（独立于项目检测，失败不影响 success） =====

        /** 已安装的 App 版本号（BuildConfig.VERSION_NAME，如 0.118.0） */
        public String apkLocalVersion = BuildConfig.VERSION_NAME;

        /** 远端最新 Release 的版本号（tag 去前缀后，如 1.0）；null = 检测失败/无 Release */
        public String apkLatestVersion;

        /** 最新 Release 中 APK 的直接下载地址；null = 最新 Release 不含 APK(视为无 App 更新) */
        public String apkDownloadUrl;

        /** 是否有比本地更新的 APK（远端版本解析成功且 > 本地） */
        public boolean apkHasUpdate;
    }

    /**
     * 执行一次完整检测（网络操作，必须在子线程调用）。
     *
     * @return 检测结果；任何一步失败都会体现在 success=false 上，不会抛异常。
     */
    public static CheckResult check() {
        CheckResult result = new CheckResult();

        // 1. 读取本地版本记录
        result.localSha = readLocalSha();

        // 2. 请求 GitHub API 获取提交列表
        String json = requestCommitsJson(result);
        if (json == null) {
            return result;  // success 已在 requestCommitsJson 中置为 false
        }

        // 3. 解析提交列表
        List<CommitInfo> commits;
        try {
            commits = parseCommits(json);
        } catch (Exception e) {
            result.success = false;     // 解析失败（API 返回结构异常等）
            return result;
        }

        // 4. 对比本地 SHA，找出新提交
        if (!commits.isEmpty()) {
            result.latestSha = commits.get(0).sha;   // 列表第一条 = 最新提交
        }
        result.newCommits = findNewCommits(commits, result.localSha);
        result.success = true;

        // 5. APK 版本检测（独立请求，失败只置空 APK 字段，不影响项目结果）
        checkApkRelease(result);
        return result;
    }

    // ==================== 内部实现 ====================

    /** 读取本地版本记录文件中的 SHA；无文件或内容为空返回 null（视为未安装） */
    private static String readLocalSha() {
        File file = new File(VERSION_FILE_PATH);
        if (!file.isFile()) {
            return null;    // 文件不存在 = 从未记录过版本 = 未安装
        }

        // try-with-resources 逐行读取，取第一行非空内容作为 SHA
        try (BufferedReader reader = new BufferedReader(
                new InputStreamReader(new FileInputStream(file), StandardCharsets.UTF_8))) {
            String line;
            while ((line = reader.readLine()) != null) {
                line = line.trim();
                if (!line.isEmpty()) {
                    return line;    // 返回第一行非空内容
                }
            }
            return null;    // 文件为空
        } catch (IOException e) {
            return null;    // 读取失败保守处理：按未安装对待，不崩溃
        }
    }

    /**
     * 请求 GitHub API，返回响应体 JSON 字符串。
     * 失败时把结果写入 result 并返回 null：
     *   - HTTP 403 → rateLimited = true（限流）
     *   - 其它非 200 / 网络异常 → success = false（一般网络错误）
     */
    private static String requestCommitsJson(CheckResult result) {
        HttpURLConnection conn = null;
        try {
            URL url = new URL(COMMITS_API_URL);
            conn = (HttpURLConnection) url.openConnection();
            conn.setConnectTimeout(TIMEOUT_MS);
            conn.setReadTimeout(TIMEOUT_MS);
            conn.setRequestMethod("GET");

            // GitHub API 强制要求 User-Agent，否则直接 403
            conn.setRequestProperty("User-Agent", "KaguraX-Manager");
            conn.setRequestProperty("Accept", "application/vnd.github+json");

            int code = conn.getResponseCode();
            if (code == HttpURLConnection.HTTP_FORBIDDEN) {   // 403 限流
                result.success = false;
                result.rateLimited = true;
                return null;
            }
            if (code != HttpURLConnection.HTTP_OK) {          // 其它错误码
                result.success = false;
                return null;
            }
            return readStream(conn.getInputStream());
        } catch (IOException e) {
            result.success = false;   // 无网络 / DNS 失败 / 连接被拒等
            return null;
        } finally {
            if (conn != null) {
                conn.disconnect();    // 释放底层连接资源
            }
        }
    }

    /** 解析 GitHub commits API 返回的 JSON 数组，提取 sha/描述/日期 */
    private static List<CommitInfo> parseCommits(String json) throws Exception {
        JSONArray array = new JSONArray(json);   // 顶层是 JSON 数组
        List<CommitInfo> list = new ArrayList<>();

        for (int i = 0; i < array.length(); i++) {
            JSONObject item = array.getJSONObject(i);
            JSONObject commit = item.getJSONObject("commit");

            CommitInfo info = new CommitInfo();
            info.sha = item.optString("sha");

            // 提交信息可能包含多行，只取第一行作为简洁描述
            String fullMessage = commit.optString("message", "").trim();
            int newlineIndex = fullMessage.indexOf('\n');
            info.message = newlineIndex >= 0 ? fullMessage.substring(0, newlineIndex) : fullMessage;

            // 提交日期：取 author.date（ISO 8601），截取前 10 位得到 yyyy-MM-dd
            // author 字段可能缺失（GitHub API 偶发情况），null 时兜底为空串
            JSONObject author = commit.optJSONObject("author");
            String isoDate = author != null ? author.optString("date", "") : "";
            info.date = isoDate.length() >= 10 ? isoDate.substring(0, 10) : isoDate;

            list.add(info);
        }
        return list;
    }

    /**
     * 找出「本地 SHA 之后」的所有新提交（从新到旧）。
     *
     * 实现：commits 列表从新到旧排列，从头遍历直到遇到与 localSha 相同的提交，
     * 之前遍历过的所有提交都是新的；列表中找不到 localSha 有两种情况：
     *   - localSha 为 null → 未安装，全部视为新提交
     *   - localSha 不在最近 20 条内（仓库改动太频繁）→ 保守显示全部 20 条
     */
    private static List<CommitInfo> findNewCommits(List<CommitInfo> commits, String localSha) {
        List<CommitInfo> newCommits = new ArrayList<>();
        for (CommitInfo info : commits) {
            if (localSha != null && localSha.equals(info.sha)) {
                break;  // 遇到本地版本即停止，之前的都是新提交
            }
            newCommits.add(info);
        }
        return newCommits;
    }

    /** 把输入流完整读成字符串（UTF-8） */
    private static String readStream(InputStream in) throws IOException {
        ByteArrayOutputStream out = new ByteArrayOutputStream();
        byte[] buffer = new byte[8192];
        int read;
        while ((read = in.read(buffer)) > 0) {
            out.write(buffer, 0, read);
        }
        return new String(out.toByteArray(), StandardCharsets.UTF_8);
    }

    // ==================== APK 版本检测 ====================

    /**
     * 请求 releases/latest 并解析 APK 版本与下载地址，写入 result。
     * 任何失败都只留下 apkLatestVersion=null（视为未知），绝不影响项目检测结果。
     */
    private static void checkApkRelease(CheckResult result) {
        HttpURLConnection conn = null;
        try {
            URL url = new URL(LATEST_RELEASE_API_URL);
            conn = (HttpURLConnection) url.openConnection();
            conn.setConnectTimeout(TIMEOUT_MS);
            conn.setReadTimeout(TIMEOUT_MS);
            conn.setRequestMethod("GET");
            conn.setRequestProperty("User-Agent", "KaguraX-Manager");
            conn.setRequestProperty("Accept", "application/vnd.github+json");

            int code = conn.getResponseCode();
            if (code != HttpURLConnection.HTTP_OK) {
                return;   // 404=无 Release / 403=限流 / 其它：一律按「未知」处理
            }

            JSONObject release;
            try (InputStream in = conn.getInputStream()) {
                release = new JSONObject(readStream(in));
            }

            String tag = release.optString("tag_name", "").trim();

            // 从 assets 里找第一个 .apk 的直接下载地址。
            // 注意: 本项目 Release 混用两类资产 —— 恢复包(container-v1, 仅 tar.gz)
            // 与 App APK(app-v1.0)。只有带 .apk asset 的 Release 才代表「新版 App」,
            // 否则(如恢复包更新)直接视为无 APK 更新, 绝不误报「有新版本」。
            String downloadUrl = null;
            JSONArray assets = release.optJSONArray("assets");
            if (assets != null) {
                for (int i = 0; i < assets.length(); i++) {
                    String name = assets.getJSONObject(i).optString("name", "");
                    if (name.endsWith(".apk")) {
                        downloadUrl = assets.getJSONObject(i).optString("browser_download_url", null);
                        break;
                    }
                }
            }
            if (downloadUrl == null || downloadUrl.isEmpty()) {
                return;   // 无 APK asset：非 App 发布(如恢复包)，不参与版本比较
            }

            String version = normalizeVersion(tag);
            if (version == null) {
                return;   // tag 解析不出数字版本（如 nightly），不比较
            }
            result.apkLatestVersion = version;
            result.apkDownloadUrl = downloadUrl;

            result.apkHasUpdate = compareVersions(result.apkLocalVersion, version) < 0;
        } catch (Exception e) {
            // 解析/网络异常：保持 apkLatestVersion=null，视为未知，不打扰
        } finally {
            if (conn != null) {
                conn.disconnect();
            }
        }
    }

    /**
     * 把 Release tag 归一化为纯数字版本号（用于比较）。
     * 支持 "1.0"、"v1.0"、"app-v1.0"、"app-v1.0.0" 等；解析不出数字返回 null。
     * 实现：从左往右找到第一个数字，取其后的 数字.数字[.数字] 片段；
     * 不带小版本号的补足（1.0 → 1.0.0），便于与本地 semver 统一比较。
     */
    private static String normalizeVersion(String tag) {
        int digitIndex = -1;
        for (int i = 0; i < tag.length(); i++) {
            if (Character.isDigit(tag.charAt(i))) {
                digitIndex = i;
                break;
            }
        }
        if (digitIndex < 0) return null;

        StringBuilder sb = new StringBuilder();
        int dots = 0;
        for (int i = digitIndex; i < tag.length(); i++) {
            char c = tag.charAt(i);
            if (Character.isDigit(c)) {
                sb.append(c);
            } else if (c == '.' && dots < 2 && sb.length() > 0) {
                sb.append(c);
                dots++;
            } else {
                break;   // 遇到其它字符（如 -beta、+meta）停止
            }
        }
        String version = sb.toString();
        // 补足三段 semver：1.0 → 1.0.0
        while (version.split("\\.").length < 3) {
            version += ".0";
        }
        return version;
    }

    /**
     * semver 三段式数字比较（忽略 prerelease/build 后缀，主.次.修订）。
     * @return 负数 = a<b，0 = 相等，正数 = a>b
     */
    private static int compareVersions(String a, String b) {
        String[] pa = a.split("\\.");
        String[] pb = b.split("\\.");
        int len = Math.max(pa.length, pb.length);
        for (int i = 0; i < len; i++) {
            int na = i < pa.length ? Integer.parseInt(pa[i]) : 0;
            int nb = i < pb.length ? Integer.parseInt(pb[i]) : 0;
            if (na != nb) return na - nb;
        }
        return 0;
    }
}
