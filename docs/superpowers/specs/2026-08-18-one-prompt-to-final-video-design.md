# 《一句话如何变成一条完整视频》完整链路测试设计

## 目标

使用 OpenMontage 的 `animated-explainer` 生产管线，制作一条约 55 秒、
16:9、1920×1080 的中文横屏视频，主题为“一句话如何经过研究、脚本、分镜、
素材生成和合成，最终变成一条完整视频”。交付物是本地可播放、可完整解码的
`final.mp4`，并保留同一 run 的阶段工件、资产清单、联系表和最终检查结果。

这次测试的核心不是生成一个好看的孤立片段，而是证明 Codex 生图、Grok 视频、
Grok TTS、Pixabay 音乐、Remotion 模板和 OpenMontage 检查点能在同一项目中闭环。

## 范围

必须完成：

- 初始化一个新的 OpenMontage 项目工作区并打开 Backlot。
- 按 `animated-explainer` 的阶段生成并校验正式工件。
- 产出中文旁白、生成图片、真实 Grok 视频片段、背景音乐和字幕。
- 使用 Remotion `Explainer` 的现有模板完成横屏合成。
- 对最终 MP4 执行媒体探测、完整解码、关键帧/联系表和人工视觉检查。

不包含：

- 上传、公开发布、封面投放或平台账号操作。
- 竖屏衍生版、多语言版本或批量变体。
- 修改 OpenMontage 核心模板或新增通用组件。
- 未经批准的模型、供应商、声音或合成运行时切换。

## 叙事与场景设计

目标时长允许在 52–58 秒内浮动，旁白驱动最终节奏。

| 时间 | 叙事任务 | 主要模板/素材 |
| --- | --- | --- |
| 0–4 秒 | 提问：“一句话，能直接变成一条完整视频吗？” | `hero_title` |
| 4–10 秒 | 展示用户输入一条需求 | `terminal_scene` |
| 10–17 秒 | 研究→脚本→分镜→素材→合成 | `progress_bar` |
| 17–25 秒 | 单模型片段与完整生产管线的差别 | `comparison` |
| 25–34 秒 | 展示真实 Grok 动态镜头 | 视频 cut + `provider_chip` |
| 34–43 秒 | 展示 Backlot 的项目阶段与资产状态 | `screenshot_scene` |
| 43–50 秒 | 汇总生图、配音、视频和合成结果 | `kpi_grid` + `stat_reveal` |
| 50–55 秒 | 落点：“不是生成一个片段，而是交付一条成片。” | `hero_title` |

模板使用遵循叙事需要，不为了覆盖数量重复堆叠同类卡片；连续三个场景不得使用
相同视觉语法。

## 供应商与资产合同

- 图片：Codex 内置 `image_gen`，预计 2 张，生成后复制到
  `projects/one-prompt-to-final-video/assets/images/` 并登记清单。
- 视频：`grok_cli_video` / `grok-imagine-video`，预计 2 条短镜头；显式 OAuth
  文件、订阅额度计费、禁止供应商回退。
- 配音：`grok_cli_tts`，中文、`ara` 声线、MP3；先使用已生成的小样进行听审，
  未批准前不生成整段旁白。
- 音乐：`pixabay_music` 搜索一条可用曲目，记录来源信息；音乐生成供应商不可用
  不构成阻塞。
- 合成：Remotion `Explainer`，使用项目锁定的 Remotion 4.0.484。

所有付费或额度调用均在执行前说明工具、供应商、模型/变体以及样例或批量属性。
每个生成任务只有一次初始调用；失败后依据结构化错误停止，不自动重复扣额度。

## 合成运行时与创作模式

当前 FFmpeg、Remotion 和 HyperFrames 均可用。

- Remotion：本次选择。它原生覆盖 `terminal_scene`、`comparison`、图表、
  `screenshot_scene`、`provider_chip` 和 `hero_title`，最适合验证现有模板目录；
  代价是依赖 Headless Chrome，渲染耗时高于简单拼接。
- HyperFrames：已验证可用，适合 HTML/GSAP 定制和轻量文字/图片/视频 cut；
  但默认 cut 适配器不能完整覆盖本次要测的丰富 Remotion 模板，因此不选。
- FFmpeg：只承担媒体预处理、探测、完整解码和必要的最终封装，不作为主要视觉
  模板运行时。

创作模式选择 `templated`。本次目标是验证仓库已有模板，不使用 atelier 手工定制，
也不把固定模板包装成“全新视觉语言”。

## 数据流与阶段门槛

```text
主题
  → research_brief
  → proposal_packet + decision_log
  → script
  → scene_plan
  → 旁白小样审批
  → asset_manifest + 场景联系表审批
  → edit_decisions
  → Remotion render
  → render_report + final_review
  → final.mp4
```

人工批准点：

1. 提案和生产预算。
2. 完整脚本。
3. 场景计划。
4. `ara` 配音小样。
5. 图片与视频资产联系表。

批准只推进当前项目的下一阶段，不授权上传、发布、push 或供应商替换。

## 错误处理

- Grok `refresh_then_retry` 最多自动处理一次；`login_then_retry`、额度、账单、权限和
  无重试窗口的限流错误立即停止。
- 生成结果语义偏离时保留失败 take 和审查备注，是否重新生成由用户批准。
- Codex 内置生图不可被无人值守 Python 调用；由当前交互式 owner 生成并复制到
  项目资产目录。
- Remotion lint、bundle、browser 或 render 失败时保留原始命令和终端错误，不切换
  HyperFrames 冒充成功。
- 任一阶段工件 schema 无效或引用的文件不存在时，不进入下一阶段。

## 验收标准

- 同一个项目目录中存在 schema-valid 的研究、提案、脚本、场景、资产、剪辑、
  渲染和最终审查工件。
- `final.mp4` 为 1920×1080，目标时长 52–58 秒，视频和音频流可探测。
- FFmpeg 对整条视频完整解码，退出码为 0。
- 中文旁白清晰，字幕与旁白节奏一致，背景音乐不遮蔽人声。
- 关键帧/联系表确认无黑帧、空白模板、截断文字、明显拉伸或错误素材。
- 至少包含一次真实 Codex 生图、一次真实 Grok TTS、一次真实 Grok 视频和一次
  Remotion 完整渲染；任何 mock 只算回归证据，不算最终验收。
- 最终状态明确记录未发布、未上传、未 push。

## 完成与停止条件

完成条件是本地 `final.mp4` 及其同 run 验收证据全部成立。若必须扩展供应商、修改
模板代码、安装新的付费服务、重新生成已被拒绝的资产，或执行任何外部发布操作，
立即停止并请求决定。
