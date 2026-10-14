# 交给新电脑智能体的安装说明

下载入口：[GitHub 最新发布包](https://github.com/hunger-Eric/OpenMontage/releases/latest/download/OpenMontage-Codex.zip)。

用户可以直接把下面这段话发给新电脑的 Codex：

> 请帮我配置这份 OpenMontage 项目。先读项目的 AGENTS.md 和
> docs/CODEX_PORTABILITY.md，检查本机环境，安装缺少的基础依赖，执行
> scripts/codex_setup.py install，再用项目 .venv 的 Python 执行 doctor。
> 我需要用 Google Flow 时，请配置随包附带的 google-flow-mcp-v4（或者按说明
> 获取该仓库），构建桥接程序，按本机实际路径配置 Chrome，并引导我登录自己的账号。
> 已有配置保留；账号、权限或提供方选择缺失时再问我。完成后告诉我哪些能力
> 已可用、哪些还需要配置。安装阶段不生成付费媒体。

安装由智能体在接收电脑执行，不要求用户逐条输入命令。Python/Node/FFmpeg 等
系统依赖按接收电脑系统选择安装方式；账号登录由用户在浏览器完成。

压缩包解压后，打开 `OpenMontage` 文件夹作为 Codex 项目。同级的
`google-flow-mcp-v4` 是可选 Flow 桥的源码，需执行 `npm ci` 和 `npm run build`；
不包含依赖、登录状态或密钥。如果从 GitHub 下载的只有 OpenMontage，
安装说明中的桥接仓库地址可用于另行获取。

环境配置完成即可按原项目流程接收方案、生成、剪辑和视频编辑请求；
实际可用范围以接收电脑的检查和账号能力为准。
