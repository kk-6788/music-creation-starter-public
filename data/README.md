# 数据目录

- projects.json：主数据，UTF-8；顶层schema_version、checked_at、scope、projects
- projects.csv：相同19条记录的表格版，UTF-8 BOM方便中文表格软件读取；sources用 ` | ` 连接
- sources.csv：去重后的来源URL及相关项目ID；用于后续逐项复核

## 项目字段

| 字段 | 含义 |
|---|---|
| id / name | 稳定机器ID / 展示名称 |
| research_group / category | ai或ui / 功能类别 |
| input_output | 主要输入到输出 |
| beginner_fit | 编辑判断的新手定位，不是质量评分 |
| chinese_evidence | 中文界面/语言/歌词的实际文档证据与限制 |
| deployment | 安装、平台、硬件条件摘要 |
| code_license | 代码许可及适用范围 |
| model_or_asset_license | 权重、声库、采样等独立边界 |
| output_terms | 输出使用声明、限制或尚未确认之处 |
| commercial_caution | 快速风险标签，不是法律意见 |
| repository | 官方源仓库或原官方入口 |
| checked_at | 核查日期，ISO 8601日期 |
| evidence_level | official-document-review或official-access-blocked-secondary-history |
| runtime_tested | 是否运行测试；本次全部false |
| commit_pinned | 是否锁定上游commit；本次全部false |
| detail_document | 从仓库根目录起的研究文件路径 |
| sources | 来源URL数组；CSV中为分隔文本 |

更新时先改JSON，再同步CSV与Markdown摘要；字段缺失不能用未经核实的猜测补齐。模型许可不明可用自然语言明确记录，不要填成MIT。
