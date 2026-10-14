# 代码、模型/素材与输出：三层许可矩阵

核查日期：2026-10-09。以下是文档摘要，不是“全部商用安全”认证。先确定你是使用工具、分发软件、托管服务、使用权重还是发布音乐，再逐项审查。代码宽松许可不自动授权模型、训练数据、声音身份或输入作品。GPL/AGPL也不是禁止商用。

| 项目（详细来源） | 代码 | 模型、声库或素材 | 输出与使用边界 |
|---|---|---|---|
| [ACE-Step 1.5](../docs/ai-generation.md) | MIT | 核查的Ace-Step1.5模型卡MIT；辅助模型逐项核对 | 模型卡允许商业输出；不豁免输入/相似性/声音权利 |
| [HeartMuLa](../docs/ai-generation.md) | Apache-2.0 | 推荐3B权重Apache-2.0；组件逐项核对 | 未见独立输出非商用限制；第三方权利仍需核对 |
| [YuE2](../docs/ai-generation.md) | Apache-2.0 | CC BY-NC-4.0加个人创作者许可 | 个人创作者可按附加条件变现；公司使用权重需另议 |
| [DiffSinger / OpenVPI](../docs/ai-generation.md) | Apache-2.0 | 声库、声码器及角色条款各自决定 | 依具体声库/声音及输入素材，不自动继承引擎许可 |
| [DiffRhythm 1.2](../docs/ai-generation.md) | Apache-2.0 | DiT权重Apache-2.0；VAE等另查 | 未完整核实所有组件和输出权利 |
| [DiffRhythm 2](../docs/ai-generation.md) | Apache-2.0 | 主权重Apache-2.0；其他组件另查 | 未完整核实所有组件和输出权利 |
| [MuLaCover](../docs/ai-generation.md) | Apache-2.0 | CC BY-NC-4.0及MODEL_LICENSE | 官方权重生成的输出明确非商用；商用须书面许可 |
| [SongGen](../docs/ai-generation.md) | Apache-2.0 | 所查模型卡未填许可；codec另查 | 未确认，不作商用授权推定 |
| [MusicGen / AudioCraft](../docs/ai-generation.md) | MIT | CC BY-NC-4.0 | 不得把模型非商用许可误写成默认商用生产线；输出另核 |
| [SongGeneration / LeVo 2](../docs/ai-generation.md) | 当前官方未核实；历史镜像限制研究教育 | 当前官方未核实；社区模型卡unknown | 不能确认商用或当前可部署性 |
| [BeepBox](../docs/interactive-tools.md) | MIT | 无需AI权重；额外素材另查 | 官网声明原创歌曲归创作者；第三方旋律仍需授权 |
| [signal](../docs/interactive-tools.md) | MIT | 无需AI权重；SoundFont另查 | 取决于旋律、SoundFont与其他输入；代码许可不等于素材授权 |
| [Audacity](../docs/interactive-tools.md) | 成品GPL-3.0；部分源码GPL-2.0-or-later | 无需AI权重；插件和伴奏另查 | 自录声音与伴奏各自核权；软件GPL不等于音乐必须GPL |
| [LMMS](../docs/interactive-tools.md) | 顶层GPL-2.0；逐文件及插件另查 | 无需AI权重；采样/SoundFont另查 | 自作音乐与采样另算；本次不承诺直接录麦克风 |
| [Hydrogen](../docs/interactive-tools.md) | GPL-2.0-or-later | 无需AI权重；鼓组/采样另查 | 鼓组及采样许可决定素材使用边界 |
| [GridSound](../docs/interactive-tools.md) | 公开daw仓库AGPL-3.0；并非整站全开源 | 无需AI权重；samples/assets/子模块另查 | 作品素材另查；网络提供修改版还须核AGPL义务 |
| [Tone.js](../docs/interactive-tools.md) | MIT | 无需AI权重；外部采样另查 | 由应用及素材决定；库不自动提供作品权利 |
| [wavesurfer.js](../docs/interactive-tools.md) | BSD-3-Clause | 无需AI权重；输入音频另查 | 由应用及音频权利决定；录音不自动授权上传 |
| [Chrome Music Lab](../docs/interactive-tools.md) | 公开仓库Apache-2.0；不覆盖整站所有实验 | 声音素材与各线上实验另核 | 不能由仓库许可推定所有线上作品/素材条款 |

## 必须单独阅读的条款

- [MuLaCover MODEL_LICENSE](https://github.com/HeartMuLa/MuLaCover/blob/main/MODEL_LICENSE)：官方权重及其生成输出均有非商用限制；免费软件源代码不消除该限制
- [YuE2 MODEL_LICENSE](https://github.com/multimodal-art-projection/YuE/blob/main/MODEL_LICENSE)：个人身份创作的输出可按附加条件变现；不自动覆盖公司商业使用模型权重或商业转售权重
- [MusicGen权重许可](https://github.com/facebookresearch/audiocraft/blob/main/LICENSE_weights)：CC BY-NC 4.0，不能因AudioCraft代码MIT便认为权重可无条件商用
- [ACE-Step模型卡](https://huggingface.co/ACE-Step/Ace-Step1.5)：已核查模型卡标MIT并声明商业输出用途；这仍不构成对任意输入、输出相似性或所有外部组件的保证

## 发布前检查单

- [ ] 记录实际使用的代码commit/发行版、模型完整ID和revision
- [ ] 保存代码、主模型、codec、声库、SoundFont、采样和在线服务各自的条款链接
- [ ] 歌词、旋律、伴奏、参考录音由自己创作或已取得对应许可
- [ ] 模仿或克隆他人声音已有明确授权；不制造真人实际演唱的误解
- [ ] 核对用途：私人练习、广告、收费交付、发行、托管生成服务的授权不同
- [ ] 确认署名、NOTICE、源码提供、再分发等义务是否适用
- [ ] 对重要商业发行，另外审核相似性、声音/肖像权益与适用地区要求

本仓库不提供对AI生成内容可获著作权的保证；公开仓库和模型作者的描述也不是法律结论。
