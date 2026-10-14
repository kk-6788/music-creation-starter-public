# Music Creator · 零基础音乐创作

新增本地中文创作工作台：接入 ACE-Step，支持主题写词后编辑、按歌词生成歌曲、纯音乐 BGM、试听与 WAV 下载。电脑运行模型，安卓手机通过同一 Wi-Fi 的浏览器使用。

开始使用请看 [创作工具使用说明](docs/app-quickstart.md)。本地安装及真实生成的实际验证结果以交付目录验证报告为准。原有项目导航和资料继续保留在下方。

## 原项目导航与研究说明

从“我不会乐理”到第一段 30 秒小样：作词、作曲、编曲、录唱与 AI 歌声的中文选型指南。

以下部分是一份研究整理、学习路线和产品方案导航，包含 19 个项目/版本的数据目录与验证脚本。新增的本地工作台不包含多轨音乐编辑器或声库训练工具。

导航资料核查日期：**2026-10-09（UTC）**。按使用目标选择，不按星数排名。下方各项目比较来自官方文档、模型卡和许可证阅读，不代表横向音质试听实测。

## 先选一条路线

| 你现在想做什么 | 从哪里开始 | 下一步 |
|---|---|---|
| 完全不安装，先做旋律/鼓点 | [BeepBox](https://www.beepbox.co/) | [30秒路线](docs/first-30-seconds.md)的手工作曲分支 |
| 中文界面写几条旋律轨 | [signal](https://signalmidi.app/edit) | 保存MIDI/WAV，后续进入桌面编曲 |
| 写四句歌词，让AI唱出来 | [ACE-Step 1.5](https://github.com/ace-step/ACE-Step-1.5) | 先看官方体验入口与条款，再比较HeartMuLa |
| 想自己唱 | [Audacity](https://www.audacityteam.org/) | 导入有权使用的伴奏，戴耳机录一条人声 |
| 认真编伴奏 | [LMMS](https://lmms.io/download) | 先做鼓、贝斯、旋律三轨 |
| 输入音符，让虚拟歌手唱 | [OpenUTAU](https://github.com/stakira/OpenUtau) + DiffSinger兼容声库 | 先核对具体声库语言和许可，不从训练开始 |
| 以后做自己的中文音乐工具 | Tone.js + wavesurfer.js | 看[分阶段MVP方案](docs/mvp-plan.md)，当前未实现 |

没有独立推荐“自动作词仓库”：第一首歌可先用原创四行歌词和[提示模板](examples/first-song.md)，减少安装负担；整歌生成器的自动写词能力随模型配置不同。

## 19个候选项目总览

“先试听”是基于交互和文档的选型建议，不是音质实测冠军。OpenUTAU作为DiffSinger的配套工作台介绍，不重复计为第20项。

| 项目 | 用途 | 新手定位 | 重要边界 |
|---|---|---|---|
| [ACE-Step 1.5](https://github.com/ace-step/ACE-Step-1.5) | 整歌生成 | 先试听 | 需核对全链路 |
| [HeartMuLa](https://github.com/HeartMuLa/heartlib) | 整歌生成 | 第二试听对象 | 需核对全链路 |
| [YuE2](https://github.com/multimodal-art-projection/YuE) | 可编辑整歌生成 | 进阶改歌 | 个人与企业不同 |
| [DiffSinger / OpenVPI](https://github.com/openvpi/DiffSinger) | 歌声合成引擎 | 配合OpenUTAU使用 | 声库逐项核对 |
| [DiffRhythm 1.2](https://github.com/ASLP-lab/DiffRhythm) | 整歌生成 | 研究备选 | 需核对全链路 |
| [DiffRhythm 2](https://github.com/xiaomi-research/diffrhythm2) | 整歌生成 | 研究备选 | 需核对全链路 |
| [MuLaCover](https://github.com/HeartMuLa/MuLaCover) | 重编曲/翻作 | 进阶非商用实验 | 输出非商用 |
| [SongGen](https://github.com/LiuZH-19/SongGen) | 短歌曲研究 | 英文研究备选 | 许可未明 |
| [MusicGen / AudioCraft](https://github.com/facebookresearch/audiocraft) | 伴奏生成 | 非商用伴奏研究 | 权重非商用 |
| [SongGeneration / LeVo 2](https://github.com/tencent-ailab/SongGeneration) | 整歌生成 | 暂缓推荐 | 来源受阻 |
| [BeepBox](https://github.com/johnnesky/beepbox) | 浏览器作曲 | 新手第一站 | 自有素材优先 |
| [signal](https://github.com/ryohey/signal) | 浏览器MIDI编辑 | 新手旋律草稿 | 素材逐项核对 |
| [Audacity](https://github.com/audacity/audacity) | 录唱与音频编辑 | 想自己唱优先 | 素材逐项核对 |
| [LMMS](https://github.com/LMMS/lmms) | 桌面编曲 | 第二阶段 | 素材逐项核对 |
| [Hydrogen](https://github.com/hydrogen-music/hydrogen) | 桌面鼓机 | 专练节奏 | 素材逐项核对 |
| [GridSound](https://github.com/gridsound/daw) | 浏览器DAW | 体验/架构参考 | 不宜直接当完整底座 |
| [Tone.js](https://github.com/Tonejs/Tone.js) | 音频开发库 | 开发组件 | 素材逐项核对 |
| [wavesurfer.js](https://github.com/katspaugh/wavesurfer.js) | 波形/录音开发库 | 开发组件 | 素材逐项核对 |
| [Chrome Music Lab](https://github.com/googlecreativelab/chrome-music-lab) | 互动音乐启蒙 | 启蒙/历史代码参考 | 开源范围有限 |

## 建议阅读顺序

1. [从零到30秒作品](docs/first-30-seconds.md)：今天只完成一个短小样
2. [AI生成与歌声合成](docs/ai-generation.md)、[交互工具与开发组件](docs/interactive-tools.md)：详细能力、输入输出、中文和官方入口
3. [部署门槛](docs/deployment.md)：先决定是否需要GPU，不要一次装完19项
4. [代码、模型、输出许可证矩阵](docs/license-matrix.md)：商用前必读的边界
5. [分阶段MVP方案](docs/mvp-plan.md)：如果将来要开发成产品
6. [来源与核查方法](docs/methodology.md)、[数据字段](data/README.md)、[维护流程](CONTRIBUTING.md)

可维护总表：[JSON](data/projects.json) / [CSV](data/projects.csv)。每条包含核查日期、来源、中文证据、部署条件、三层许可和未实测标志。

## 最容易踩的坑

- 中文界面、中文提示词理解、中文歌词唱准是三个不同指标
- 代码许可不能代替模型、声库、采样或生成输出的许可。MuLaCover官方输出非商用；YuE2个人创作者和企业使用边界不同；MusicGen权重非商用
- SongGen与SongGeneration不是同一项目；后者官方入口本次无法读取，不提供可运行保证
- 低显存推理不等于低延迟，也不等于所有大模型版本、所有功能都能用
- wavesurfer.js不是剪辑/修音引擎；Chrome Music Lab公开仓库不等于全部线上实验源码；GridSound不等于整站全开源
- 网页体验可能收费、排队或收集上传内容。未核实当前额度，不上传私密录音或未经许可的他人声音

## 本仓库验证

需要 Python 3.9 或更新版本，仅使用标准库（无需安装依赖）：

```sh
python3 scripts/validate_catalog.py
python3 -O scripts/validate_catalog.py
python3 -m unittest discover -s tests -v
```

验证严格数据结构、19条唯一ID、真实日历日期、JSON/CSV一致性、来源URL与项目归属、仓库内文档路径、Markdown相对文件及标题链接。失败返回退出码1和FAIL诊断，成功为0；优化模式（-O）同样执行校验。它不访问网络，也不检验外站实时可用性、模型可运行性或音乐质量。见[验证记录](docs/validation-report.md)。

## 内容与权利

本仓库为原创整理与链接索引，未打包上游源码、模型权重、声库或音乐素材；原项目名称与权利归其各自权利人。尚未为本仓库原创内容选定对外再许可条款；如需再分发或将本仓库整体纳入产品，请先取得仓库维护者授权。上游许可摘要仅用于选型核对，不替代完整条款和针对具体用途的审查。
