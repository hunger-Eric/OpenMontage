# 在另一台电脑的 Codex 使用 OpenMontage

**给使用者的入口：** 下载源码或解压安装包后，把根目录的
[INSTALL_FOR_AGENT.md](../INSTALL_FOR_AGENT.md) 交给新电脑的智能体，让它按说明配置。

发布包入口：[GitHub 最新发布](https://github.com/hunger-Eric/OpenMontage/releases/latest)。
下载其中的 `OpenMontage-Codex.zip`；该包同时附带固定版本的 Flow 桥接源码。
每次推送 `main` 后，`Codex portable release` 工作流自动验证、打包并发布最新版本，
失败时保留此前已成功发布的版本。只有本地修改、尚未推送时不会更新发布包。
Flow 桥版本由 `portable-release.json` 固定，升级桥时更新其中的 SHA 后一起推送。

把完整源码放到任意目录，在 Codex 中打开该目录即可。项目根目录的
`AGENTS.md` 是自动入口，`.agents/skills/` 是随仓库提供的技能；不需要复制
原电脑的 Codex 全局技能、记忆、个人配置或固定盘符。工作流程仍由
`AGENT_GUIDE.md` 和选定的 pipeline/director 决定。

## 新电脑安装

安装 Python 3.10+、Node.js/npm、Git、FFmpeg（包含 ffprobe），并将命令放入 PATH。
渲染建议使用 Node.js 22 LTS。源码可以用 Git 获取，也可以复制完整源码目录。
源码地址：`https://github.com/hunger-Eric/OpenMontage.git`。

在项目根目录运行（Windows 的 PowerShell 也可直接执行，不依赖 make/Bash）：

```sh
python scripts/codex_setup.py install
```

脚本创建本目录的 `.venv`，安装核心 Python 依赖，并在 `remotion-composer`
执行 `npm ci`，沿用锁文件中的版本。缺少 `.env` 或 `config.local.yaml` 时才从
示例创建，已有文件不覆盖。安装不会配置付费账号、启动视频生成或更改 Codex 设置。
只做方案时可使用 `install --skip-remotion`。

Windows 检查命令：

```powershell
.venv/Scripts/python.exe scripts/codex_setup.py doctor
```

macOS/Linux：

```sh
.venv/bin/python scripts/codex_setup.py doctor
```

`doctor --planning-only` 只要求方案基础环境；完整制作使用默认检查。
报告区分基础环境、Remotion、可选 API SDK 和 Flow，列出缺项与修复方法，不输出密钥，
不联系模型服务。`ready` 表示本机依赖检查通过，不表示账号登录或成片质量已验证。
开新 Codex 会话后，可以直接说：

> 按 AGENTS.md 读取项目入口，运行 codex_setup.py doctor，说明可用能力和缺项；先不要生成媒体。

## 按需要配置提供方

API 密钥填在新电脑的 `.env`，只填实际使用的服务。
提供方偏好填在 `config.local.yaml`，示例见 `config.local.example.yaml`。
默认 `auto` 不会继承原电脑的账号或偏好；用 Flow 时设
`providers.video_provider: google_flow`，需要限定该提供方时同时设
`providers.restrict_to_preferences: true`。具体模型名以新电脑 Flow UI 为准。
Codex 本身的模型设置与视频提供方是两回事，迁移脚本不改 Codex 模型。

## Google Flow（可选，需另装浏览器桥）

OpenMontage 的 Python 工具会直接启动本机的 stdio MCP 桥；无需为这条路径
额外安装 Codex MCP 配置。桥接仓库不包含在 OpenMontage 中：

```sh
git clone https://github.com/hunger-Eric/google-flow-mcp-v4.git
```

在桥接仓库运行 `npm ci`、`npm run build`。同级目录名为
`google-flow-mcp-v4` 时会自动找到；其他位置在 OpenMontage `.env` 设置
`GOOGLE_FLOW_MCP_ROOT` 为该仓库的绝对路径。

在桥接仓库建立自己的 `.env`，设置：

```dotenv
HEADLESS=false
TRANSPORT=stdio
# 以下换成新电脑实际的路径，勿原样复制占位符。
CHROME_EXECUTABLE_PATH=<本机 Chrome 可执行文件绝对路径>
CHROME_USER_DATA_DIR=<本机专供 Flow 使用的浏览器数据目录>
LOCAL_STORAGE_ROOT=<本机媒体下载目录>
```

不要直接沿用桥的旧示例中 macOS 固定路径。在桥接仓库运行 `npm run login`，
在新电脑登录自己的 Google 账号，再运行 `doctor --require-flow`。
检查通过只证明桥已构建，登录/订阅与实际生成仍须实际入口验证。
Flow 共用一个浏览器配置，同一电脑的请求顺序执行；不要并发启动多个桥占用它。

## 迁移范围

源码、流程、模板和技能跟随仓库；`.venv`、`node_modules` 在新电脑重新安装。
不要把 `.env`、`config.local.yaml`、浏览器配置、Cookies、系统凭据库和原电脑
Codex 配置作为分发包。飞书权限、应用凭据和模板链接属于账号配置，需要接收方
自己授权，不能凭一个模板链接认定可用。

新任务在新电脑新建项目即可。若要继续旧作品，另行复制所需 `projects/<id>/`
及素材，并由 Agent 先核对其中的绝对路径、原生成任务回执和已有产物；
不要直接重跑已提交的视频。旧工程跨电脑续跑不属于自动路径重写功能。
