# AI 音乐、歌词成歌与歌声合成：零基础选型

核查日期：2026-10-09。范围：10 个候选项目/版本。实际读取了官方 README、部署说明、许可证、模型卡及部分推理入口；**没有安装模型、生成音频、试听对照测试或验证在线排队/免费额度**。性能数字若出现，均是作者文档的条件性数据，不是本项目实测。项目自称“媲美/超过 Suno”的宣传不作为排名依据。

## 先给结论

- **想把几句中文变成带演唱的歌**：优先看 ACE-Step 1.5；先用它链接的网页体验入口，再决定是否安装。本地优先普通 2B turbo，不必一开始上 XL
- **想要另一种中文整歌生成风格**：HeartMuLa 是值得试听的第二选择，许可证较清晰，但官方本地流程仍偏技术用户
- **想逐步学习旋律、和弦并改歌**：YuE2 的可编辑曲谱很有价值，但官方本地起点为 24GB NVIDIA GPU，企业商用许可不同于个人创作者
- **想输入音符和歌词，让虚拟歌手唱出来**：OpenUTAU + 适配的 DiffSinger 声库；它不是输入一句话自动生成全套编曲的工具
- **只想生成伴奏/氛围片段**：MusicGen 可作研究候选，不能当可靠的中文歌词演唱器，模型也有非商用限制
- **暂不作为新手主推**：SongGeneration 官方入口本次无法获取；SongGen 只有英文短片段；DiffRhythm 2 与 MuLaCover 的部署门槛/使用边界更适合进阶探索

“支持中文界面”“能理解中文风格描述”“能正确唱中文歌词”是三件不同的事。下面分别按官方证据说明，不由项目中文名称推断能力。

## 快速比较

| 项目 | 输入到输出 | 中文证据 | 新手定位 | 本地硬件/安装边界 | 许可关键点 |
|---|---|---|---|---|---|
| ACE-Step 1.5 | 描述/歌词 → 人声+伴奏；编辑/重绘 | 歌唱语言常量明确含zh/yue；具体发音仍需试听 | 首选尝试 | 低显存普通模型可 offload；XL 最少12GB且需优化，20GB更合适 | 代码 MIT；核查的官方1.5模型卡 MIT |
| HeartMuLa | 歌词+标签 → 歌曲 | 推荐3B模型卡明确列 zh | 第二试听对象 | CUDA 示例；可 lazy loading；官方未给统一最低显存 | 代码与推荐3B权重 Apache-2.0 |
| YuE2 | 歌词+风格 → 可编辑旋律和弦计划 → 整歌 | 模型卡 zh、普通话示例 | 想深入改歌时 | 官方快速开始：Linux、Python3.12、BF16 NVIDIA、24GB | 代码 Apache-2.0；权重 CC BY-NC + 个人创作者许可 |
| DiffSinger/OpenVPI | 音符/音素/歌词 → 歌声 | 文档明确普通话拼音和中文音素配置 | 虚拟歌手路线 | 推荐借 OpenUTAU 部署已有声库，不从训练开始 | 引擎 Apache-2.0；每个声库另查 |
| DiffRhythm 1.2 | 时间歌词LRC+风格 → 整歌 | 论文训练集明确含中文歌曲；需实际逐字验证 | 旧版备选 | base最低8GB需chunked；full不应套用该门槛 | 代码与DiT权重Apache-2.0；其余组件另查 |
| DiffRhythm 2 | 歌词文件+文本/音频风格 → 歌曲 | 本次未完成中文模型效果证据验证 | 进阶实验 | espeak-ng + Python依赖；无明确统一最低显存 | 官方代码、权重Apache-2.0 |
| MuLaCover | 参考录音或MIDI+新歌词/风格 → 翻作 | 官方README有完整中文歌词示例 | 进阶重编曲 | Linux NVIDIA，多组权重；官方验证机器B300 | 代码Apache-2.0；权重及输出均非商用 |
| SongGen | 歌词+描述 → 双轨/混合歌曲片段 | 官方明确仅英文 | 研究备选 | Python3.9、CUDA>=11.8示例，手动下载X-Codec | 代码Apache-2.0；模型卡许可未填 |
| MusicGen | 描述/旋律 → 音乐片段 | 官方说英语描述更好，不能生成逼真人声 | 伴奏实验 | medium官方建议16GB GPU；small更轻 | 代码MIT；权重CC BY-NC4.0 |
| SongGeneration/LeVo 2 | 歌词/描述/参考音频 → 歌曲 | 历史文档称支持中文 | 暂缓部署推荐 | 原官方入口不可读；不能保证完整依赖可得 | 镜像保留研究教育用途限制；现存权重卡unknown |

所有可正常读取的本地开源推理路线都**不以付费音乐API为必要步骤**。这不等于没有成本：模型下载、磁盘、GPU、租机、电费或第三方网页服务可能收费。在线演示的条款与本地权重许可也不能混为一谈。

## 1. ACE-Step 1.5：最接近“先玩起来”的本地候选

**为何入选**：有 Gradio、Simple/Custom 模式、中文界面说明、多平台启动脚本。Simple 会先创建歌词/描述/元数据，再进入音频生成；不懂乐理也能从自然语言开始。普通 turbo 的部分编辑能力与 base 不同，不能把“项目支持的全部能力”当成每个模型都支持。

**中文证据**：实际代码 `VALID_LANGUAGES` 的歌唱语言列表包含 `zh` 和 `yue`；这是接口支持证据，不是普通话/粤语字音准确率实测。

**实际入口核查**：pyproject 注册 `acestep` 到 `acestep.acestep_v15_pipeline:main`；README 的本地路径为 Python3.11–3.12、`uv sync`、`uv run acestep`，首次下载模型。文档还列 MPS/ROCm/Intel/CPU，支持不代表同等速度。

**硬件解释**：≤6GB 档默认关闭LM，以量化/offload运行普通DiT。这里的低显存方案不应宣传成“任何旧电脑都能流畅写词+出整歌”；XL是另一档，≥12GB优化运行、≥20GB更合适。官方“数秒一首”的数据不能外推到CPU。

**许可/状态**：代码 LICENSE 与核查的 Ace-Step1.5 模型卡均 MIT；README已有2026-04-02 XL发布记录。在线入口是否可用、额度、商业条款未实测。

**来源**：[README](https://github.com/ace-step/ACE-Step-1.5) · [Gradio说明](https://github.com/ace-step/ACE-Step-1.5/blob/main/docs/en/GRADIO_GUIDE.md) · [入口配置](https://github.com/ace-step/ACE-Step-1.5/blob/main/pyproject.toml) · [歌唱语言常量](https://github.com/ace-step/ACE-Step-1.5/blob/main/acestep/constants.py) · [代码许可](https://github.com/ace-step/ACE-Step-1.5/blob/main/LICENSE) · [官方模型卡](https://huggingface.co/ACE-Step/Ace-Step1.5)

## 2. HeartMuLa：中文歌词成歌的第二试听对象

输入自己的歌词与逗号分隔风格标签，输出含演唱的音乐；官方例程输出MP3，默认最大音频长度参数240秒。推荐权重现为 `HeartMuLa-oss-3B-happy-new-year` + `HeartCodec-oss-20260123`，不能把尚未发布的7B内部效果当作用户拿到的3B效果。

部署须下载主模型、codec与配置/tokenizer三个部分；入口为 `examples/run_music_generation.py`。单卡可开 `--lazy_load true`，多卡可分配MuLa与codec。官方未承诺通用最低显存，所以本表不给“8GB必跑”等推断数字。模型卡明确列 zh/en/ja/ko/es，不等于每种语言字音全对。

官方2026-01-20公告把仓库及相关模型权重更新为Apache-2.0，推荐3B模型卡也一致；README到2026-09-16仍有更新。提供HF/ModelScope在线体验链接，但本次未提交生成。

**来源**：[README及部署](https://github.com/HeartMuLa/heartlib) · [推理例程](https://github.com/HeartMuLa/heartlib/blob/main/examples/run_music_generation.py) · [LICENSE](https://github.com/HeartMuLa/heartlib/blob/main/LICENSE) · [推荐模型卡](https://huggingface.co/HeartMuLa/HeartMuLa-oss-3B-happy-new-year)

## 3. YuE2：能改旋律/和弦的整歌生成

当前主分支已是YuE2，旧YuE在 `YuE-v1`。YuE2由歌词和风格生成可编辑ABC旋律/和弦计划，再生成48kHz立体声。可关闭曲谱规划；改编参考录音需额外SheetSage2流程。编辑会重新合成整段录音，并非保证未编辑部分波形不变。

官方快速开始为Linux、Python3.12、支持BF16的24GB NVIDIA GPU；首次下载 `m-a-p/YuE2-3B` 及VAE。例程 `examples/generate.py` 保存音频和曲谱等中间产物。模型卡有普通话成歌示例。README在2026-10-06仍有明确新闻记录。

**许可务必分开**：代码Apache-2.0；3B/VAE权重为CC BY-NC4.0加额外个人创作者许可。以个人身份创作可发布、出售或授权生成作品，无需向模型作者付费；公司商业使用权重需另议。该许可不授予别人的歌词、录音、声音身份权利，也不允许商业转售权重。

**来源**：[当前README](https://github.com/multimodal-art-projection/YuE) · [模型卡](https://huggingface.co/m-a-p/YuE2-3B) · [完整MODEL_LICENSE](https://github.com/multimodal-art-projection/YuE/blob/main/MODEL_LICENSE) · [原YuE分支](https://github.com/multimodal-art-projection/YuE/tree/YuE-v1)

## 4. DiffSinger（OpenVPI）：让虚拟歌手按你写的音符唱

它是歌声合成引擎，不会自动包办作词、和弦与伴奏。原始推理输入DS文件，包含音素、时长、音符或控制曲线。零基础应从OpenUTAU安装已有兼容声库开始，再学习钢琴卷帘中的音高与时长，不建议首日训练声库。

OpenVPI维护版支持44.1kHz以及音高/气声等控制，官方文档明确普通话使用拼音与字典配置。最终中文能力取决于声库、字典及音素器，不能由引擎支持直接推定某个歌手支持中文。

部署文档当前要求Python≥3.10、推荐PyTorch≥2.4，ONNX用于生产部署。引擎代码Apache-2.0；声库和声码器需各自核对条款，可能限制商用、角色使用或再分发。页面明确为OpenVPI维护版本，但本次不宣称最近一次提交日期。

**来源**：[README](https://github.com/openvpi/DiffSinger) · [安装/推理/ONNX](https://github.com/openvpi/DiffSinger/blob/main/docs/GettingStarted.md) · [音素与DS格式](https://github.com/openvpi/DiffSinger/blob/main/docs/BestPractices.md) · [LICENSE](https://github.com/openvpi/DiffSinger/blob/main/LICENSE) · [OpenUTAU](https://github.com/stakira/OpenUtau)

## 5. DiffRhythm 1.2：轻一些，但歌词时间轴多一步

旧版仍有独立价值：有95秒base和285秒full模型，LRC时间歌词配文字/音频风格生成带歌声作品，也有纯音乐路径。对新手的额外负担是准备时间轴；官方链接工具可辅助，但不是自动写好词就永远对齐。

部署需要espeak-ng、Python环境和模型。官方最低8GB仅针对base且需 `--chunked`；不可外推到full。主要入口是 `scripts/infer_prompt_ref.sh`、`scripts/infer_wav_ref.sh`。2025-05-09发布1.2的记录仍保留；研究后续已转向第二代。

README明确代码与DiT权重Apache-2.0；VAE与额外组件仍应单独检查。适合想对比生成器的人，不作为首推。

**来源**：[README/硬件/入口](https://github.com/ASLP-lab/DiffRhythm) · [许可证](https://github.com/ASLP-lab/DiffRhythm/blob/main/LICENSE.md) · [1.2权重](https://huggingface.co/ASLP-lab/DiffRhythm-1_2) · [论文中文训练数据证据§4.1](https://arxiv.org/html/2503.01183v1#S4.SS1)

## 6. DiffRhythm 2：文本/参考风格的研究型备选

官方上游在 `xiaomi-research/diffrhythm2`，ASLP-lab也有镜像。实际读了 `inference.py`：必需歌词文件与style_prompt；style_prompt若是文件则读音频，否则走文字风格编码。因此不必误写成“只能参考音频”。首次自动从HF下载权重；还使用MuQ-MuLan等组件。

README的Gradio、续写、纯音乐仍列待办；不要把上一代功能直接复制到第二代。主模型与代码明确Apache-2.0，最低显存未明确。CPU分支存在于代码不等于已验证CPU实用性。本次未完成中文效果证据及听感验证，中文推荐级别低于ACE/HeartMuLa/YuE2。已核查发布记录2025-10-30。

**来源**：[README](https://github.com/xiaomi-research/diffrhythm2) · [实际推理入口](https://github.com/xiaomi-research/diffrhythm2/blob/main/inference.py) · [LICENSE](https://github.com/xiaomi-research/diffrhythm2/blob/main/LICENSE) · [权重卡](https://huggingface.co/ASLP-lab/DiffRhythm2)

## 7. MuLaCover：重编曲有趣，但不能沿用HeartMuLa商用结论

这是独立项目：用参考录音或旋律/和弦MIDI，加新歌词和风格，把音乐重新演绎。官方README提供中文歌词格式，保留分行和段落标签，不加歌词时间戳。音频会先转符号条件，不是逐帧复制。

要求Linux NVIDIA、Python3.10，并下载MuLaCover、HeartCodec、Qwen3-Embedding；参考录音路线还要YourMT3和ChordNet。默认lazy loading，官方已验证表列B300，未提供可信消费卡最低显存；不宜对新手承诺轻量。2026-09-16公开发布。

**许可特殊限制**：代码Apache-2.0，官方权重CC BY-NC4.0加MODEL_LICENSE，**用官方权重生成的输出也限制非商用**，未经书面授权不应用于付费交付。它与HeartMuLa 3B不是同一许可结论。

**来源**：[README](https://github.com/HeartMuLa/MuLaCover) · [完整生成指南](https://github.com/HeartMuLa/MuLaCover/blob/main/examples/cover_song_generation.md) · [MODEL_LICENSE](https://github.com/HeartMuLa/MuLaCover/blob/main/MODEL_LICENSE) · [代码LICENSE](https://github.com/HeartMuLa/MuLaCover/blob/main/LICENSE)

## 8. SongGen：英文30秒研究模型，不是中文整歌方案

可用描述、歌词与可选参考声音生成混合音频，或分别输出伴奏、人声。官方明确当前限制为英文、最长30秒；名字与SongGeneration相近，但不是同一项目。

官方安装示例使用Python3.9.18、CUDA≥11.8、PyTorch2.3并下载X-Codec。推理为Python类调用，未给一键新手工作台或最低显存承诺。README最近列出的发布新闻为2025-07-04训练代码。

仓库代码LICENSE是Apache-2.0；实际打开 `SongGen_mixed_pro` 模型卡仍是自动生成模板，License字段未补充。因此不要把代码许可擅自扩展成所有权重/codec可商用已确认。

**来源**：[README与推理示例](https://github.com/LiuZH-19/SongGen) · [代码LICENSE](https://github.com/LiuZH-19/SongGen/blob/master/LICENSE.txt) · [模型卡](https://huggingface.co/LiuZH-19/SongGen_mixed_pro)

## 9. MusicGen：生成伴奏片段，别期待它唱准歌词

成熟的研究基线，可从文字或旋律条件生成音乐；官方模型卡明确不能生成逼真人声，英语描述训练导致其他语言表现更弱。不适合“中文歌词→准确演唱”。

AudioCraft提供Gradio/Jupyter/Colab路线；本地medium官方建议至少16GB GPU，小模型或短片段可更低。代码MIT，模型权重CC BY-NC4.0，不能当作默认商用伴奏生产线。项目可读，但本次未用最近提交日期评判维护速度。

**来源**：[MusicGen使用说明](https://github.com/facebookresearch/audiocraft/blob/main/docs/MUSICGEN.md) · [小模型卡与限制](https://huggingface.co/facebook/musicgen-small) · [权重许可证](https://github.com/facebookresearch/audiocraft/blob/main/LICENSE_weights)

## 10. SongGeneration / LeVo 2：保留条目，明确可用性风险

本次官方GitHub `tencent-ailab/SongGeneration` 返回404，腾讯官方HF模型页返回401；只说明本次无法公开读取，**不推测项目删除原因或永久停更**。仍可读取的 `lglg666/SongGeneration-v2-large` 模型卡几乎为空且license为unknown。

社区保留的2026-03-01文档描述中文/多语歌词到歌、分离人声伴奏、Gradio与4B v2-large；列显存22/28GB，分别不带/带参考音频。这些是历史镜像文档数据，不能作为当前官方可部署保证。

读取的社区保留LICENSE明确限制学术、研究和教育用途，禁止商业或生产用途；尽管文档说“商业级效果”，也不是商业使用授权。故不建议零基础用户从来路不明整合包开始，更不能因代码可见就标“自由商用”。

**来源**：[官方原入口](https://github.com/tencent-ailab/SongGeneration) · [腾讯HF入口](https://huggingface.co/tencent/SongGeneration) · [仍可读取的v2模型卡](https://huggingface.co/lglg666/SongGeneration-v2-large) · [社区历史README，非官方现状证明](https://github.com/banner88/SongGeneration-v2/blob/main/README.md) · [社区保留LICENSE](https://github.com/banner88/SongGeneration-v2/blob/main/LICENSE)

## 零基础第一首歌：最小可行玩法

1. 自己写四行原创短句，主题只选一个，例如“下班后一个人散步”。不会写可以先请文字助手给两个四行版本，不必先研究专门歌词仓库
2. 在ACE-Step的Simple模式试一句描述，或Custom模式粘贴歌词；从30–60秒短段开始，先验证中文清楚、情绪对，再延长
3. 风格先写日常词：“温暖、轻快、木吉他、普通话女声”。每次只改一个条件，保留提示词、模型版本和seed，方便比较
4. 先比较3个结果：是否漏字/多字、句尾能否听清、主歌副歌有无区别；不要仅凭音色好听判定成功
5. 想学旋律再尝试YuE2曲谱或OpenUTAU；想补伴奏再学音轨编辑。不要第一天同时训练声库、调混音和装多个大模型

## 再发布前检查

- 代码、主权重、声库、codec、在线服务、生成音频的许可可能各不相同；“开源”与“可商用”不是一个字段
- 只用自己有权使用的歌词、音频和声音素材；克隆真实人物声音应有明确授权，不制造误认其真实演唱的内容
- 开放许可不保证输出在所有司法辖区都可获得著作权，也不保证没有侵权相似；商业发行另行审核
- README速度/质量是作者报告；演示精选音频不是普通用户一次生成成功率
- 未实测项：安装成功率、中文逐字准确率、CPU/消费卡速度、在线额度、生成作品音乐质量
