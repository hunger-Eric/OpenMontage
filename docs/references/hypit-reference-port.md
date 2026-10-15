# Hypit 参考视频理解源码迁移

本次迁入的是原项目的实现和原版方法说明。OpenMontage 本地执行迁入源码，
不查找或调用 Hypit 命令，不依赖另一个项目目录、Hypit 安装、账号或 Runtime。

## 原始来源与接入位置

| 原项目材料 | 本项目位置与用途 |
|---|---|
| 原技能 `SKILL.md` | [原文](../../third_party/hypit/SKILL.md#understand-and-adapt)：导演理解、整体与细节互相修正、对象与关系随时间变化；只采用当前参考理解职责 |
| `@hypit/hypit` 0.2.6 `packages/video-cli/src/media.ts` | `tools/analysis/_reference_media/media.ts`：媒体探测、指定时间取帧、图集、分页图集、时间标记片段、变化候选 |
| 同版本 `transcript.ts` | 同目录原文件：真实词时间、帧旁词语上下文、按短语定位、重复短语选择；缺失时间不猜补 |
| 同版本 `process.ts` | 同目录原文件：本地 FFmpeg 子进程、标准流和超时处理 |
| 原技能 `references/creation/reference-video.md` | [原文](../../third_party/hypit/references/creation/reference-video.md)：整片理解与局部细读、按问题调整取证尺度、保留连接起来的解释、转为新作品方向 |
| 原技能 `references/playbooks/craft/video-direction.md` | [原文](../../third_party/hypit/references/playbooks/craft/video-direction.md)：动作动机、各参考输入的职责、运动证据、摄影机与切镜 |

原技能的引用书保留原文和相对链接；只由当前参考分析入口按需读取，不将其
完整生产技能注册为本项目的新入口。源码、文档逐文件 SHA-256、版本与机械
接入改动见 [PROVENANCE.json](../../third_party/hypit/PROVENANCE.json)。
原许可随源码及引用书保留。

## 接入已有流程

`video_analyzer` 标准／深度分析先沿用现有下载和转写，再调用迁入的本地实现
准备初始图集及变化候选。`reference_media` 暴露同一源码支持的六种本地操作，
供分析者按原方法继续缩小范围、加密取样、放大细节或结合真实词时间。
没有另写摄影机分类器、镜头解释器或语义完成评分。

默认取样、变化分数、帧时间读取和图集布局来自原实现。
例如变化候选沿用 12 Hz、32×32 RGB 相邻差异及 0.1 阈值；候选不等于切镜。
密度和观察范围由当前问题决定，不能把这些数字当作理解视频的固定模板。

按原文使用 `ANALYSIS.md`、`TIMELINE.md` 和 `PROGRESS.md`，分别承载整体解释、
带时间的具体实现及待查问题。`video_analysis_brief.reference_understanding`
保存它们的索引与执行证据；工具不会填入已完成的理解。

后续 proposal/script/scene/assets 从这个连接起来的解释中工作：保留被用户
选中的表达关系。源秒数定位证据；新内容的动作、台词、转折决定新作品的
对应时刻。已有 `proposal_packet.metadata.reference_adaptation` 负责制作决定，
引用这些分析文件及修订，而不是再写一套可变理解。沿用现有生成与合成入口。

## 本地执行

安装迁入源码所需的小型依赖（不安装 Hypit）：

```powershell
npm ci --prefix tools/analysis/_reference_media
```

依赖为原项目使用的 `sharp` 和 `tsx`，另需既有 Node 与 FFmpeg。缺失时明确
失败，不改调外部命令或自拟算法。

```python
registry.get("reference_media").execute({
    "operation": "tiles",
    "input_path": source_path,
    "output_path": fresh_grid_directory,
    "receipt_path": fresh_receipt_path,
    "options": {"start": 6.8, "end": 8.4, "every": 0.1, "cell": 480, "columns": 4},
})
```

例子的数值来自原方法文档的局部细读示例，不是统一的生产参数。
按短语定位使用原 `around/transcript/occurrence/padding` 选项；词时间必须与
同一媒体时钟对应。取得媒体、准备图集、理解内容和生成效果分别验收。

## 为接入所做的改动

移除了原文件中的下载／准备下载分支和 `@hypit/yt-dlp` 引入，下载仍由
OpenMontage 的既有获取协议负责；将类型依赖 `CliIo` 换为本地等价接口；
增加本地执行入口与 Python 工具封装。`process.ts`、`transcript.ts` 保持原字节。
取帧、图集、词句检索和变化计算的函数保留原实现。没有迁入其生成服务、
渲染器或默认模型。也没有增加镜头字段、硬编码运镜规则或额外人工审批。
