# 视频参考获取与失败验证：2026-10-01

## 范围与结论

完成 7 个平台、8 类入口的样例验证：抖音、YouTube、YouTube Shorts、TikTok、Instagram、Vimeo、X、B 站。抖音复用本任务前一步的真实下载、完整解码与本地分析证据，并重新执行了媒体探测；其他入口在本轮各执行真实下载器检查和正常浏览器检查。

**目前只有抖音这个样例取得了完整可分析媒体。其他样例的失败边界已经验证；没有将网页加载、播放窗口、试看或失败回执算成视频分析成功。** 这些结果不能证明任一平台的所有视频均可用。

源代码 checkout：`E:\project\OpenMontage`，`main`，HEAD `d5eccdba2028445143516f3ad5ab7db861e49e7c`，包含本任务未提交修改。实际下载器版本 `yt-dlp 2026.03.17`。本机有 Node 和 FFmpeg；没有 Deno、`yt_dlp_ejs` 或 `curl_cffi`。没有安装依赖、切换代理、更新账号、部署服务或启动新的飞书任务。

下载器使用原 `VideoDownloader.execute` 入口；测试仅覆盖 socket timeout 为 12 秒、yt-dlp 请求重试为 0、每个子检查最多 80 秒、360p、最长 180 秒的受限选项。真实失败在元数据阶段即停止，没有通过反复下载制造“恢复成功”。最初测试记录器存在 Windows 字符编码问题；修正记录器后仅重新记录了缺失的 YouTube、Shorts 和 B 站结果，其他结果保留。

## 真实入口结果

| 平台 / 公开样例 | 下载器观察 | 浏览器观察 | 完整媒体 / 分析结果 | 下一步与未验证边界 |
|---|---|---|---|---|
| [抖音](https://www.douyin.com/video/7681624043124162469) | 同一上传器账号状态被选中；详情接口此前返回 403，解析器发出泛化 Fresh cookies 提示 | 正常播放，已保存本地完整媒体 | 133.466667 秒，1920×1080；完整解码通过；27 场景、20 关键帧。转写未验证 | 本样例的人工授权浏览器恢复已证实；飞书自动浏览器路径仍未接入、未验收 |
| [YouTube](https://www.youtube.com/watch?v=jNQXAC9IVRw) | Sign in to confirm you're not a bot；另有未找到受支持 JS runtime 的警告 | 播放器 readyState=4，19.021 秒；直接保存 30 秒超时；已观察媒体资源的导出被浏览器工具以 unsupported asset kinds 拒绝 | 没有取得完整本地文件，未执行视频分析 | 先补足官方要求的解析运行环境，再针对该入口验收；是否解决仍未验证。不能把浏览器播放当作下载完成 |
| [YouTube Shorts](https://www.youtube.com/shorts/BGQWPY4IigY) | 同样的非机器人确认；缺少 JS runtime 警告 | readyState=4，14.361 秒，blob 播放；直接保存 10 秒超时 | 没有完整文件，未执行视频分析 | 与 YouTube 一起验证分段音视频获取和合并，现有浏览器直接保存路径不足 |
| [TikTok](https://www.tiktok.com/@leenabhushan/video/6748451240264420610) | Unexpected response from webpage；缺少 impersonation target 警告 | 登录入口；点击可见 Skip 后出现出生日期注册表单，已停止 | 没有媒体，未执行分析 | 需要用户完成合适的原平台访问流程或提供本地原视频；没有代填年龄、注册或尝试绕过 |
| [Instagram](https://www.instagram.com/reel/Chunk8-jurw/) | 内容不可用、限流或需要登录的三选一提示，不能据此确认登录失效 | 关闭推广登录提示后有 4.966666 秒的 blob 媒体，readyState=4；直接保存 15 秒超时 | 没有完整文件，未执行分析 | 解析器适配与合法已有账号访问需要另行实际验证；不能承诺刷新 Cookie 能解决 |
| [Vimeo](https://vimeo.com/56015672) | TLS fingerprint 被拒绝；缺少 impersonation target 警告 | CAPTCHA Challenge / Verify to continue，已停止 | 没有媒体，未执行分析 | 人机验证需用户处理；没有降级 HTTPS、换身份或绕过。缺少依赖是已观察到的环境因素，不是已确认的唯一根因 |
| [X](https://twitter.com/starwars/status/665052190608723968) | 旧外链媒体返回 HTTP 500: Domain Not Found | 帖子可见，引用旧 amp.twimg.com 链接；video 元素为 0 | 没有媒体，未执行分析 | 原媒体是否仍可访问未解决；需有效原视频来源。这一老样例的失败不能推出 X 原生视频全部不可用 |
| [B 站](https://www.bilibili.com/video/BV13x41117TL) | HTTP 412: Precondition Failed | 播放器显示完整时长 553.82 秒，同时明确写“试看30秒”“登录 免费享高清视频” | 仅预览，未保存、未执行完整视频分析 | 已验证需要完整访问权限/本地原视频，不能把试看当成完整素材 |

真实检查的结构化证据位于 `.tmp/platform-validation-20261001/*-result.json` 和 `browser-results.json`。抖音媒体及分析位于 `.tmp/douyin-7681624043124162469-browser-20261001/`。浏览器沿用当前会话，未导入、更新或导出 Cookie；这不是同一 Cookie 下对所有请求环境的受控实验。

## 失败回归与本地修复

真实结果验证了错误分类的缺口；离线注入验证了失败后的控制流。两类证据分开记录，模拟错误不能证明平台真实发生过相应故障。

- 分类覆盖：明确登录、人机验证、403/412、429、404/删除、DRM、地域限制、域名/网络不可达、泛化 Cookie 提示、含多个候选原因的提示。
- 每个平台入口都验证：失败结果保持原错误类型、不回放失败的媒体请求、不额外请求 YouTube 字幕、不产生虚假的时长/关键帧。
- 额外验证：无效授权状态在联网前停止；字幕拒绝不吞掉原错误；缺失/空媒体不返回成功；损坏媒体被拒绝；30 秒预览与已知 553 秒源不符时被拒绝；没有转写文本时 transcript_only 不成功。
- 保留正向反证：已有有效 YouTube 字幕仍能完成 transcript_only；Fresh cookies 元数据告警并不排除本地完整媒体恢复；既有抖音完整媒体通过当前媒体探测。

本地修改在 `tools/analysis/video_downloader.py`、`tools/analysis/video_analyzer.py` 和 `skills/meta/video-reference-analyst.md`；新增 `tests/tools/test_video_reference_failure_matrix.py`，并调整已有相关回归测试。保护了原有 `tools/audio/gemini_tts.py` 等无关修改。

首次离线矩阵为 49 失败 / 74 通过；随后新增的无效授权、字幕错误、空转写、短预览检查也分别先证明失败，再修复。最终相关测试 **165 通过**，`git diff --check` 通过。没有执行跨平台真实完整分析成功的虚假验收。

## 失败后的处理

| 分类 | 处理 | 恢复是否已验证 |
|---|---|---|
| 明确 AUTH_REQUIRED | 原平台既有授权状态刷新或用户提供原文件；保持任务证据 | 本轮没有登录/刷新测试 |
| CHALLENGE_REQUIRED / ACCESS_DENIED | 停止；按平台正常访问流程解决，不重复请求或绕过 | 抖音浏览器路径仅该样例成功；Vimeo仍阻塞 |
| EXTRACTOR_BLOCKED | 保留候选原因，核对解析器版本、依赖与真实页面；不直接责怪账号 | 错误分类已修复；TikTok/Instagram媒体恢复未验证 |
| RATE_LIMITED / TRANSIENT_NETWORK | 限流停止；临时网络仅按既有有界策略恢复，条件不变不无限重试 | 临时网络的有界重试已有离线检查；本轮未制造真实平台限流 |
| NETWORK_UNAVAILABLE | 核对失败的主机、DNS与实际网络路径；不要因 HTTP 500 就宣称刷新登录可解决 | X旧外链仍未解决 |
| REFERENCE_UNAVAILABLE / MEDIA_PROTECTED / GEO_RESTRICTED | 取得用户可合法访问的有效原视频或更换参考；不可用就明确失败 | 分类与停止流程离线验证；未破解保护或限制 |
| REFERENCE_MEDIA_UNAVAILABLE / INVALID_REFERENCE_MEDIA / INCOMPLETE_REFERENCE_MEDIA | 保留失败证据；完整原文件到位后再进入本地分析 | 缺失、损坏、预览的拒绝路径已验证；抖音完整文件正向验证通过 |

## Kedou 公开链接对照

用户在操作前明确同意服务条款和隐私政策，并授权向 `https://www.kedou.life/` 提交本轮公开样例，测试解析、预览与下载；遇收费、登录或人机验证停止。本轮只提交上表的公开链接，没有提交账号 Cookie、登录信息、文件或非公开任务内容，没有安装网站提供的下载器。

| 样例 | Kedou 网页实际结果 | 完整文件验收 |
|---|---|---|
| 抖音 | 正确返回视频标题、抖音标签及清晰度入口；后台下载显示 100%，打开媒体页后可播放和保存 | 保存 15,938,154 字节 MP4；133.466667 秒，1920×1080，H.264 + AAC；FFprobe 与完整 FFmpeg 解码通过 |
| YouTube | 返回 Me at the zoo、youtube、流畅270P、有声/无声及音频选项；尝试后台和直接下载，未观察到媒体页或完成下载文件 | 未取得，不能算成功；具体下载失败原因未确定 |
| YouTube Shorts | 加载提示消失后，没有返回标题、清晰度或下载结果 | 未取得；页面没有明确原因，不能推断为账号问题 |
| TikTok | 加载结束后无解析信息或下载结果 | 未取得；原因未确定 |
| Instagram | 明确提示“Instagram解析失败，请尝试使用电脑桌面下载器配合 cookie 通过本地解析的方式下载” | 未取得；没有安装下载器或向站点提供 Cookie |
| Vimeo | 加载结束后无解析信息或下载结果 | 未取得；原因未确定 |
| X | 加载结束后无解析信息或下载结果 | 未取得；旧外链是否仍可用未解决 |
| B 站 | 加载结束后无解析信息或下载结果 | 未取得；未绕过原平台预览与访问限制 |

抖音新文件保存在 `.tmp/platform-validation-20261001/kedou/douyin/reference_video.mp4`。它与先前浏览器取得的 HEVC 文件编码与大小不同，但标题、时长、分辨率一致；本轮没有对新文件重复模型内容拆解或转写。截图与非敏感结果记录保存在同目录上一级。下载事件等待超时仅说明该浏览器事件没有完成：抖音后来实际打开媒体页并成功保存，不能把该事件超时当成网站下载必然失败。

## 下载网站式入口的判断

用户提出的方式有实际价值：**同一条抖音链接，原下载器详情接口受阻，Kedou 只接收公开链接就取得了完整媒体**。不能继续把问题概括为 Cookie 失效或认为这种获取方式做不到。网站的具体后端实现和可供自动化接入的正式 API 未验证。

同时，本轮仅抖音完成文件验收；YouTube 只解析出选项，Instagram 明确失败，其余样例没有结果。后续网络观察发现站点接口当前明确返回每日使用次数上限，页面却未清晰展示；此前无结果的样例未保留接口响应，因此无法排除同一额度限制，不能将其归因于平台不支持。不能根据站点宣称支持的平台数量承诺全部视频可用。“贴链接—预览—下载”的用户入口可以实现，但须补齐各平台实际获取能力、完整性校验与明确失败处理。Kedou 尚未作为永久依赖接入，飞书自动获取路径仍未部署、未验收。

## 网站怎样实现：公开前端与实际请求证据

在用户要求检查机制后，通过正常浏览器读取当前已加载的公开脚本，并观察一次已授权公开抖音样例提交。普通 HTTP 读取首页被 403 拒绝后未重试该请求；未修改浏览器身份、安全策略或 Cookie。

- 实际“开始”提交发出 `POST /api/video/extract/v2`，说明解析依赖服务端。公开 `CzJ60ugW.js` 将结果放入 `videoExtractInfo`，字段包括 `host`、`vid`、`displayTitle`、`videoInfoVoList`；每个画质条目在 `DuIFooo0.js` 中使用 `baseUrl`、`canDirectPlay`、`canDirectDownload`、`hlsType`、`dashType`、`mustUseDownloader` 等能力字段。
- 小播放窗口：MP4 使用普通 HTML `video`，m3u8 使用 HLS 播放组件，其他已支持格式使用对应播放器。前端已有 HLS、DASH/MPD、FLV 的处理分支；这只能证明前端支持路径，不能证明每种来源都能被完整解析。
- 直接下载：当 `canDirectDownload` 为真时，前端构造指向 `baseUrl` 的链接并点击。之前实际抖音媒体来自抖音/西瓜 CDN，而非浏览器录屏。
- 后台下载：前端调用 `/video/doDownload`，参数含 `host`、`vid`、`quality`、`mustDownload`；每约 3 秒轮询进度，完成后调用 `/video/getDownloadInfo`，使用返回的 `downloadType`、`downloadUrl`、`playUrl` 展示下载及预览。前端还会周期刷新这些地址。确有服务端异步提取链路；是否具体采用 FFmpeg、yt-dlp、账号池、代理或私有解析算法，公开证据不足。
- 本次两条解析响应 HTTP 状态均为 200，但 JSON 业务 `code=500`，提示“您今日的使用次数已达上限，请登录来获取更多下载次数吧！”。立即停止后续提交，没有注册、登录、付费或绕过额度。此前各平台无结果的失败原因须保留未确定。

由此可确定：应借鉴的是独立解析服务、结构化媒体结果、按格式播放、直接下载与后台提取分流、明确业务错误及完整性验收。不能把该站内部接口当作已授权、稳定可用的公开 API，也不能从前端代码推断其服务端解析算法。

## 按网站机制实施的本地修复

用户明确批准按照上述方案修复后，在 OpenMontage 实现独立的正常浏览器媒体解析器 `tools/analysis/reference_media_resolver.py`，接入已有 `video_downloader` 和 `video_analyzer`；Bridge 核心没有增加 Cookie、平台域名、下载器或生产流程。

- 默认 `reference_acquisition=auto`：原解析器的泛化 Fresh cookies 或 unexpected-webpage 失败进入一次隔离浏览器恢复，不重复原页面解析。`extractor` 禁用恢复；`browser` 直接选择该入口。明确 auth、403/412、挑战、限流、保护、地域等限制仍停止。
- 使用隔离的 headless 浏览器与现有 Chromium/Windows Edge；只读取并导入匹配源主机的已有 Cookie，不导入用户浏览器配置或 localStorage，不安装软件，不操作登录、验证码或付费。不将链接或凭据交给 Kedou。
- 解析单一可播放媒体；直接地址交给 yt-dlp，唯一已观察 HLS/DASH 清单交给其分段下载与合并。多个清单、无清单 blob、试看、无有效时长或受保护媒体明确失败。此实现没有声称能够解析 YouTube 的所有独立音视频流。
- 下载使用新的目录；传输不打印签名地址和会话头。校验本地视频流、时长与页面时长一致、时长上限和完整 FFmpeg 解码。只有通过后才保存安全的 acquisition receipt。
- 分析入口保留 acquisition_method / acquisition_stages；内容理解仍由原模型负责。修正已有 brief schema 遗漏 douyin 的枚举，允许真实抖音来源通过契约。

相关检查最终 **193 项通过**，包括浏览器生命周期与 Cookie 隔离的模拟验证、默认路由、明确拒绝不恢复、HLS 清单歧义、隐私输出、预览/短文件拒绝和完整解码门。原有不相关脏文件保留，没有提交、推送、部署或重启。

通过本任务正常浏览器再次取得同一抖音样例；新代码的真实文件校验通过：133.466667 秒、1920×1080、30fps、完整解码通过。文件及真实校验记录位于 `.tmp/platform-validation-20261001/local-repair/`，记录明确标注 `managed browser manual validation`，**不是生产自动浏览器调用回执**。当时自动 headless 链路未执行；随后用户明确授权，实际验收如下。

## 自动浏览器真实验收与返修

用户明确授权直接运行项目 Playwright 后，使用已安装 Edge、headless、沙箱、隔离上下文及原 uploader_default Cookie，执行当前 `VideoDownloader.execute`。

1. 第一版误把隐藏挑战 iframe 当作当前验证，返回 CHALLENGE_REQUIRED。补充可见性判定，并用真实 Edge 在本地 HTML 验证：display:none 和 visibility:hidden 不阻塞；可见挑战仍阻塞。没有移除真实验证门或修改浏览器身份、安全策略。
2. 第二次下载了 2.6 秒页头动画，工具当时返回成功，验收判为失败。原结果及 receipt 保留在 `automatic-browser-acceptance/visible-challenge-guard/`，独立 `acceptance-rejection.json` 明确否定该结果；不能将它当成正确媒体获取。
3. 排障观察到：正常页面自己请求的 aweme/detail 响应为 200，aweme_id 与输入精确一致，video.duration=133467ms；页头动画不在目标 `.video_<id>` 容器中。增加身份绑定：只接受匹配输入编号的页面响应媒体，或匹配该编号容器里的播放器；不接受装饰性或推荐视频。所有媒体地址只在内存用于传输。
4. 修正后直接 browser 路径真实通过，19.53 秒完成解析、下载与完整校验。
5. **默认 auto 入口真实通过**：先收到原 yt-dlp 的 Fresh cookies 告警，随后自动切换到隔离浏览器；17.45 秒完成。最终视频 133.466667 秒、1920×1080、30fps，完整解码通过，并取得 WAV 音轨。不是手工传入媒体地址、重用旧文件或模拟 provider 返回。
6. 自动取得的文件进入真实本地 VideoAnalyzer standard：27 场景、6 关键帧、运动分类、音频能量，steps_failed=[]。本次以本地文件路径分析，没有再访问远端，也没有执行内容模型拆解或转写；has_transcript=false。

最终相关回归 **195 项通过**；git diff --check 及 CodeGraph sync 通过。真实结果、校验 receipt 和分析证据位于 `.tmp/platform-validation-20261001/automatic-browser-acceptance/default-auto/`。这证明该抖音样例在当前本机的自动获取与本地技术分析路径成功，不能推出所有平台/视频均成功。

没有安装软件、登录、注册、收费调用、更新 Cookie、部署、重启或新建飞书任务。飞书生产入口的自动获取、内容模型拆解与可见交付仍未验收。

这份报告证明了选定入口的观察、失败处理及本地修复，**不证明飞书批量视频分析已全面可用**。
