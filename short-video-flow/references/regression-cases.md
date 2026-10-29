# 回归用例与适用范围

改动 story/drama/prompt/flow 脚本或门禁文字后，运行下列可执行测试。真实案例位于项目本地被忽略的 outputs/，不存在时真实案例测试会跳过；合成测试仍须全绿。

统一运行：python short-video-flow/scripts/run_regression.py

| 用例 | 输入 | 期望 | 判定范围 |
|---|---|---|---|
| R1 | `short-video-flow/tests/test_sequence.py` 合成流程状态 | S1A 必须起始；跳阶段、缺门禁、静默回退和未填模板均 exit 2 | 顺序锁 |
| R2 | `story-deslop/tests/test_deslop_scripts.py` 合成正文 | 干净文本、em dash blocking、白名单、截断与标点 check-only 均符合预期 | 去 AI 味脚本 |
| R3 | `ai-novel-short-story/scripts/selftest.py` 合成项目 | 三方向、因果规划、连续拆段、整篇审查、修复上限与最终成文均可执行 | 故事状态机 |
| R4 | `short-story-to-drama-storyboard/scripts/selftest.py` 合成短篇 | 单集/多集改编、脚本质量门、源快照、逐镜分镜与 finalize 均可执行 | 改编分镜状态机 |
| R5 | v4 字幕及实际时长 65.57s | 本技能 check_rhythm.py 报 11 句、72 字、19.13s 最大空档、10–20s 窗口 0 字；默认 exit 0，严格阈值 4s 时 exit 2 | 字幕时间轴代理指标 |
| R6 | 合成清单：九字段空表/占位符/散文体、缺交接列 | check_gen_list exit 2；完整九字段表及交接列 exit 0 | F7/F8 防绕过 |

R5 字幕使用 字幕-v4.srt；字幕.srt 为其他版本，不能混为同一案例。字数按 Unicode 字母及数字计，不计标点，不能把字幕密度误称为音频语音密度。

下列视觉案例仍需人工或经人工校准的项目专用工具核对：v3 的 S12 指认对象不在场、v4 首帧其余段零误报、v1 空间/道具漂移、S15 吉祥物标志性镜片缺失。案例 check_causality.py 和 check_props.py 含固定镜号、资产词与颜色阈值，未经项目参数化，不作为通用 skill 的自动通过证明。记录具体文件、镜号和截图，确认无误再把规则参数化。
