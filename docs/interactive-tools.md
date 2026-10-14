# 零基础音乐创作：交互工具与可复用组件研究

核查日期：2026-10-09（UTC）。本次直接读取官方 GitHub README、LICENSE、目录/关键入口及官方产品页面；未安装、运行、注册、付费或实测音频。易用性分级是根据交互方式的编辑判断，不是实测评分。维护日期采用 GitHub API 的 pushed_at，表示仓库推送，不保证正式版发布时间或质量。

## 结论

- **第一次玩音乐：BeepBox**。浏览器点格子即可组成旋律、鼓和循环；官方明确歌曲留在设备，分享链接才分享作品。
- **想把旋律带去其他软件：signal**。已有简繁中文词条、钢琴卷帘、多轨、MIDI 和 WAV 导出；不是专业混音 DAW。
- **想自己唱：Audacity**。先把伴奏导入，再录自己的声音；它解决录音剪辑，不替你作曲或练唱。
- **想编完整伴奏：LMMS**；专练节奏则用 **Hydrogen**。两者需要安装，学习成本高于 BeepBox。
- **若以后开发自己的零基础音乐网页：Tone.js + wavesurfer.js**。前者负责发声和节拍，后者负责录音波形/回放。它们是开发库，不能直接当现成 DAW。
- GridSound 适合观察浏览器 DAW 设计，但 README 明确称其为“half open-source”；Chrome Music Lab 很适合玩，但公开代码已归档，且不包含全部线上实验。

## 1. BeepBox：最推荐的第一站

- 类型/适用：现成浏览器作曲工具，同时含可复用合成器。适合做 15–60 秒旋律、游戏感配乐、鼓点和循环；不负责录人声、写歌词。
- 零基础门槛：低。点击添加音符，拖动长度，复制/排列 pattern。先做一小段，不必先学五线谱。
- 平台/中文：JavaScript 浏览器；官方提供离线下载。页面及文档为英文，本次未核实官方中文界面。
- 隐私：官网说明歌曲编码在 URL 的 # 后，服务器不接收歌曲；复制分享 URL 会分享整首曲子。MP3 导出会按需从 jsDelivr 下载 lamejs 依赖，不能把所有导出描述为完全断网。
- 许可/商用：主代码 MIT，保留版权与许可文本即可按许可使用/改造/分发。官网明确原创歌曲归作者；第三方旋律或素材仍须另核权利。
- 开发入口：TypeScript；README 构建是 npm install → npm run build；editor/ 为编辑器、synth/ 为发声引擎、player/ 为嵌入播放器、website/index.html 为构建后入口。package.json 实际调用 Bash 编译脚本，自建环境须有 Bash。
- 维护：未归档；最近仓库推送 2026-08-07。
- 来源：[在线工具与隐私/离线说明](https://www.beepbox.co/) · [README](https://github.com/johnnesky/beepbox/blob/main/README.md) · [许可](https://github.com/johnnesky/beepbox/blob/main/LICENSE.md) · [构建脚本](https://github.com/johnnesky/beepbox/blob/main/package.json) · [仓库状态](https://api.github.com/repos/johnnesky/beepbox)

## 2. signal：轻量中文 MIDI 作曲草稿本

- 类型/适用：现成浏览器 MIDI 编辑器。多轨钢琴卷帘、SoundFont、MIDI 键盘输入输出、WAV 导出，适合旋律和伴奏草稿。
- 零基础门槛：低至中。需要理解时间横轴、音高纵轴和不同乐器轨；建议从 4 小节开始。
- 边界：README 明确定位为 DAW 的补充工具，刻意保持基础音质、无效果器。录 MIDI 演奏不等于麦克风录唱。
- 平台/中文：官网支持桌面 Chrome/Firefox/Safari，PWA；Web MIDI 需浏览器支持。源码 localization.ts 已有 zh-Hans/zh-Hant；中文完整度未实测。
- 隐私：Web Audio 在浏览器播放，架构含 IndexedDB、本地文件能力，也有 Firebase 云端。官方服务使用 Google Analytics 与 Sentry；云注册采集关联账户用户名和邮箱。不能称线上版“完全不联网/不收集数据”。
- 许可/商用：主代码 MIT；用户另载 SoundFont 的许可须单独确认。
- 开发入口：React/TypeScript monorepo；app/ 是 UI，packages/core 为音乐数据/引擎，packages/player 为调度播放，electron/ 为桌面壳，functions/ 为 Firebase。按 README：corepack enable、pnpm install、先 pnpm build，再 pnpm dev；localhost:3000。另有 docker compose up 路径。启用云功能还要配置 Firebase。
- 维护：未归档；最近推送 2026-10-04。
- 来源：[直接开始](https://signalmidi.app/edit) · [功能](https://signalmidi.app/) · [README](https://github.com/ryohey/signal/blob/main/README.md) · [架构](https://github.com/ryohey/signal/blob/main/ARCHITECTURE.md) · [中文词条](https://github.com/ryohey/signal/blob/main/app/src/localize/localization.ts) · [许可](https://github.com/ryohey/signal/blob/main/LICENSE) · [隐私](https://signalmidi.app/privacy) · [状态](https://api.github.com/repos/ryohey/signal)

## 3. Audacity：录唱与剪辑优先

- 类型/适用：桌面多轨录音/音频编辑器。适合录自己的歌声、剪掉空白、叠加伴奏、整理试唱小样。
- 零基础门槛：录一条声音低，混音中。官方入门流程是选择麦克风、按红色录音键、回听；先试录以避免爆音。
- 平台/中文：Windows、macOS、Linux；需要安装。仓库含简繁中文翻译（au3/locale 及 share/locale）；不同版本完整度未测。
- 隐私：基础录音可作为本地工作流。官方声明网络功能可关闭；更新检查默认启用，另有可选分析/错误报告和 Audio.com 集成，使用云功能会改变数据流。Audacity 4 的错误报告开启后自动发送，3.x 的提示机制不同，不能混写。
- 许可/商用：成品整体 GPLv3；大量源文件 GPLv2-or-later，第三方目录/插件另有例外；文档 CC BY 3.0。不能把整个仓库按 MIT 复制进新项目。录制作品、伴奏和插件素材权利需分别核实。
- 开发入口：README 明示 master 正在大改 Audacity 4，初学开发者不友好；Audacity 3 的补丁应基于 audacity3。4 的构建需 Git/CMake/Ninja/C++/Qt 6.10 等，BUILDING.md 仍在完善。给零基础用户应提供官方已发布安装包，不要求自己编译。
- 维护：未归档；最近推送 2026-10-09。仓库重构活跃不代表主分支适合日常生产。
- 来源：[官网](https://www.audacityteam.org/) · [录音教程](https://support.audacityteam.org/basics/recording-your-voice-and-microphone) · [README](https://github.com/audacity/audacity/blob/master/README.md) · [构建](https://github.com/audacity/audacity/blob/master/BUILDING.md) · [许可](https://github.com/audacity/audacity/blob/master/LICENSE.txt) · [4+隐私](https://www.audacityteam.org/legal/privacy-notice/) · [3.x隐私](https://www.audacityteam.org/legal/archive/privacy-notice-audacity-3/) · [状态](https://api.github.com/repos/audacity/audacity)

## 4. LMMS：完整伴奏编排的第二阶段

- 类型/适用：桌面音乐制作软件，含 Piano Roll、Pattern Editor、Song Editor、Mixer、自动化和内置合成器；适合把旋律、鼓、贝斯组织成完整伴奏。
- 零基础门槛：中。功能多，建议先只用鼓、贝斯、旋律三轨。别从插件安装与调音色开始。
- 平台/中文：跨 Windows/macOS/Linux；需要安装。源码 data/locale 有 zh_CN.ts 与 zh_TW.ts。
- 录唱边界：本次当前 README 未列麦克风录音能力；不要据此承诺可直接录人声。建议把“编曲用 LMMS、录唱用 Audacity”作为明确工作流，而不是依赖历史论坛判断当前开发版。
- 隐私：可按桌面本地文件工作流使用，无须为编曲上传录音；本次未做网络流量审计。
- 许可/商用：仓库顶层 GPLv2；逐文件/插件仍需核对。GPL 并非禁止商用，但分发修改软件需履行对应许可；自作音乐与第三方采样/SoundFont 授权另算。
- 开发入口：C++/Qt/CMake；src/、include/、plugins/、data/。INSTALL.txt 要求补齐 Git submodules 与开发依赖后配置 CMake；不适合做“零基础一键部署”项目。
- 维护：未归档；最近推送 2026-09-27。
- 来源：[官网](https://lmms.io/) · [下载](https://lmms.io/download) · [README](https://github.com/LMMS/lmms/blob/master/README.md) · [安装构建](https://github.com/LMMS/lmms/blob/master/INSTALL.txt) · [语言目录](https://github.com/LMMS/lmms/tree/master/data/locale) · [许可](https://github.com/LMMS/lmms/blob/master/LICENSE.txt) · [状态](https://api.github.com/repos/LMMS/lmms)
- 核查限制：官方 documentation 页面本次返回 403；功能判断改据当前仓库 README，不声称已实测最新版。

## 5. Hydrogen：专注鼓点与节奏

- 类型/适用：现成桌面鼓机/鼓步进编曲器，支持 pattern、鼓组、MIDI、音符属性和节奏循环；适合先学“底鼓、军鼓、踩镲如何摆”。
- 零基础门槛：低至中，比完整 DAW 更专注；不会替用户完成歌词、主旋律或录唱。
- 平台/中文：Linux/macOS/Windows；需安装。README 提供 1.2.7 安装文件；data/i18n 有 hydrogen_zh_CN.ts，中文覆盖未测。
- 隐私：可使用本地鼓组、本地工程；下载外部鼓组需联网。未做网络审计。
- 许可/商用：README 明确 GPLv2+；鼓组/采样需各自核许可，不能只看软件许可便认定素材全部可商用。
- 开发入口：C++/Qt/CMake，src/ 与 data/；Linux 构建需要 Qt、libsndfile、音频/MIDI 驱动开发库等，普通用户用发布包。
- 维护：未归档；最近推送 2026-10-08。
- 来源：[README与下载](https://github.com/hydrogen-music/hydrogen/blob/main/README.md) · [构建](https://github.com/hydrogen-music/hydrogen/blob/main/INSTALL.md) · [语言目录](https://github.com/hydrogen-music/hydrogen/tree/main/data/i18n) · [许可](https://github.com/hydrogen-music/hydrogen/blob/main/COPYING) · [状态](https://api.github.com/repos/hydrogen-music/hydrogen)

## 6. GridSound：可体验，但谨慎作为开源底座

- 类型/适用：浏览器 DAW，Web Audio、编曲窗口、钢琴卷帘、鼓、合成器、混音及效果器组件。
- 零基础门槛：中。比 BeepBox 接近传统 DAW；作者声明 work-in-progress。
- 平台/中文：免安装网页；中文支持未核实。实际入口代码对 Firefox 有专门提示，跨浏览器兼容须实测。
- 隐私：官方可注册账户保存云端作品；不能把云保存当本地处理。未核实其完整隐私政策。
- 许可/商用：daw 仓库顶层 AGPL-3.0；README 同时自称“half open-source”。只可说已公开这一仓库，不可说完整网站/后端全开源。若复用修改并网络提供服务，应核对 AGPL 的对应源码义务；素材与子模块逐一核对。
- 开发入口：src/run.js 初始化 GSDAW；build-conf.json 组合资源；.gitmodules 引用 daw-core、gs-ui-components、gs-api-client、音频组件、assets、samples 等多个仓库。README 没有完整本地构建步骤，不承诺 clone 后即运行；先仅作为使用体验/架构参考。
- 维护：未归档；最近推送 2026-10-05。
- 来源：[在线体验](https://daw.gridsound.com/) · [README](https://github.com/gridsound/daw/blob/main/README.md) · [许可](https://github.com/gridsound/daw/blob/main/LICENSE) · [子模块](https://github.com/gridsound/daw/blob/main/.gitmodules) · [构建配置](https://github.com/gridsound/daw/blob/main/build-conf.json) · [入口](https://github.com/gridsound/daw/blob/main/src/run.js) · [状态](https://api.github.com/repos/gridsound/daw)

## 7. Tone.js：开发自己的点格子音乐工具

- 类型/适用：Web Audio 开发库，不是开箱即用作曲软件。提供节拍/事件调度、合成器、采样器、效果器等，适合构建节奏网格、和弦按钮与自动伴奏交互。
- 零基础门槛：使用最终界面可低；开发门槛中，需要 JavaScript/TypeScript 和音频调度概念。
- 平台/中文：桌面/移动浏览器；文档英文，界面由开发者自己做中文。使用者无须安装，开发环境需 npm 或打包/CDN。
- 隐私：合成和处理基于浏览器原生 Web Audio；采样音频可能从指定 URL 下载，是否上传/分析取决于开发者应用，库本身不等于整站隐私保证。
- 许可/商用：MIT；外部采样另核许可。用于新项目较易做清晰依赖边界。
- 关键实现：先在用户点击事件中 await Tone.start()，否则浏览器可能静音；用 Transport 的时间参数精确调度，不能只依赖 setInterval。MIDI 文件需要另用 Tonejs/Midi 转换；不要把音频库误当自带完整 MIDI 编辑器。
- 开发入口：npm install tone 是稳定版，tone@next 对应开发测试版；Tone/ 和 examples/ 是主要入口。
- 维护：未归档；最近推送 2026-10-04。
- 来源：[README](https://github.com/Tonejs/Tone.js/blob/dev/README.md) · [示例](https://tonejs.github.io/examples/) · [API](https://tonejs.github.io/docs/) · [许可](https://github.com/Tonejs/Tone.js/blob/dev/LICENSE.md) · [状态](https://api.github.com/repos/Tonejs/Tone.js)

## 8. wavesurfer.js：录唱波形与分句回放组件

- 类型/适用：浏览器波形和播放开发库，Record 插件可录麦克风并画波形；Regions 可标记片段。适合“唱一句→回听→重新录”或歌词句段定位界面。
- 零基础门槛：现成演示低；集成需要前端开发。
- 重要边界：README 明确它不是音频剪辑/处理引擎；不能声称装上它即可剪辑、自动修音、混音。真正剪切导出需另做音频处理。
- 平台/中文：现代浏览器，npm/CDN 可嵌入；文档英文，按钮/提示由应用实现中文。录音需麦克风权限与浏览器支持。
- 隐私：README 说明音频在浏览器 Web Audio 解码；Record 产生 Blob 事件。是否上传由接入应用决定；远程音频还受 CORS 限制。长文件全量解码可能超内存，官方建议预计算 peaks。
- 许可/商用：BSD-3-Clause，保留版权/许可及免责声明，不能未经许可用作者名背书。
- 开发入口：src/wavesurfer.ts、src/plugins/record.ts、examples；README 当前主分支示例已出现 v8，生产集成应锁定并测试实际版本，勿混用 v7/v8 API。开发命令 yarn、yarn start（localhost:9090）。
- 维护：未归档；最近推送 2026-10-09。
- 来源：[README](https://github.com/katspaugh/wavesurfer.js/blob/main/README.md) · [录音代码](https://github.com/katspaugh/wavesurfer.js/blob/main/src/plugins/record.ts) · [示例](https://wavesurfer.xyz/examples/) · [许可](https://github.com/katspaugh/wavesurfer.js/blob/main/LICENSE) · [状态](https://api.github.com/repos/katspaugh/wavesurfer.js)

## 9. Chrome Music Lab：零基础启蒙好，代码仅作历史参考

- 类型/适用：在线互动音乐实验；适合体验节奏、和弦、旋律和声音可视化。官网无须注册，支持手机/平板/电脑浏览器。
- 零基础门槛：低；作为学习入口推荐，不作为完整制作/录唱工具。
- 开源边界：GitHub 仓库有 melodymaker、arpeggios、chords、pianoroll 等实验，**没有证据证明线上 Song Maker 的代码包含在这个仓库里**。不能把整站每个实验都称为可复用开源项目。
- 平台/中文/隐私：浏览器即用；中文覆盖及各实验具体数据流本次未核实。官网链接 Google 隐私/条款，不能宣称其完全离线。
- 许可/商用：已公开仓库 Apache-2.0；许可仅适用于其覆盖的代码，不能由此推出所有线上实验、声音素材或作品使用条件。
- 开发入口：各子目录自己的 README；melodymaker 说明 Node/npm/webpack，npm install 后 webpack -p。工具链老旧，新机器能否直接构建未测试。
- 维护：GitHub 已归档；API 最近推送为 2024-02-28。适合读实现，不宜选作新项目长期底座。
- 来源：[官网与FAQ](https://musiclab.chromeexperiments.com/Experiments) · [仓库](https://github.com/googlecreativelab/chrome-music-lab) · [Melody Maker构建](https://github.com/googlecreativelab/chrome-music-lab/blob/master/melodymaker/README.md) · [许可](https://github.com/googlecreativelab/chrome-music-lab/blob/master/LICENSE) · [状态](https://api.github.com/repos/googlecreativelab/chrome-music-lab)

## 新仓库如何纳入这些项目

建议先做中文导航与学习路线，不复制上游完整源码：
1. “马上玩”：BeepBox、signal、Chrome Music Lab
2. “录自己的歌”：Audacity
3. “认真编伴奏”：LMMS、Hydrogen
4. “开发组件”：Tone.js、wavesurfer.js
5. “审慎参考”：GridSound、已归档代码及未实测部署说明

每个条目记录 checked_at、官方试玩/下载、源仓库、类别、入门难度、中文证据、安装条件、隐私、代码许可、素材许可风险、维护事实。任何后续二次开发都应锁定版本/commit、附许可清单；“可以商用软件”与“可以商用所有音乐素材”分别核对。

