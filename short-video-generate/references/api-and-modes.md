# KIE Seedance 接口与模式

模型固定 `bytedance/seedance-2-mini`。所有请求走 `api.kie.ai`，文件走 `kieai.redpandaai.co`。

## 一、三个接口

```http
POST https://api.kie.ai/api/v1/jobs/createTask      创建任务
GET  https://api.kie.ai/api/v1/jobs/recordInfo      查询（?taskId=）
POST https://kieai.redpandaai.co/api/file-stream-upload   上传参考帧
```

鉴权统一 `Authorization: Bearer <KIE_API_KEY>`。

上传是 `multipart/form-data`，字段 `file`、`uploadPath`、`fileName`；返回值取 `data.downloadUrl`，没有就取 `data.fileUrl`。

**上传地址是临时的。** 长期引用一律用本地文件路径，临时 URL 只用于当次请求。

## 二、共享参数

```json
{
  "model": "bytedance/seedance-2-mini",
  "input": {
    "prompt": "最终视频提示词",
    "generate_audio": true,
    "resolution": "480p",
    "aspect_ratio": "9:16",
    "duration": 6
  }
}
```

| 字段 | 取值 | 本项目默认 | 备注 |
|---|---|---|---|
| `prompt` | 3–20000 字符 | — | 太长不是好事，见提示词规范 |
| `generate_audio` | bool | `true` | 默认连音频一起生成；要纯画面用 `--no-audio` |
| `resolution` | `480p` / `720p` | `480p` | 需要更高清时显式传 720p |
| `aspect_ratio` | 9:16 / 16:9 / 1:1 / 3:4 / 4:3 / 21:9 / adaptive | `9:16` | adaptive 仅文生 |
| `duration` | 4–15 整数 | 5 | 平台虽列 `-1`，行为未明，不传 |

### 关于 `generate_audio`

默认 `true`，画面与声音一起出。这在这个模型上是原生能力，不是外挂。

**这条音轨承载全部声音**：环境音、动作音、人物对白与旁白。本项目不再另做 TTS 配音，所以这一项不能关。

它能给什么：

- 环境音（风声、空调、街道底噪）
- 动作音（拧盖、放下杯子、脚步）
- **中文人物对白与旁白**——写进提示词的说话人与台词，它会生成对应语音
- 氛围配乐（有，但风格不可控）

它给不了什么：

- **念准生僻字、多音字**——大概率错
- **念准品牌名与型号**——尤其夹在长句里时会被含糊吞掉
- **严格的语速控制**——长台词会漏句，不会如实念完
- **与画面严格对齐的口型**——中文尤其明显

所以：**台词写进提示词是对的，但要控制长度、避开生僻字，并且每段必须听一遍核对。** 念错时不要指望去修，只能重出或改字幕贴合。

`--no-audio` 现在只用于**确实不需要任何声音的空镜**。原本"关掉音频好接后期配音"这条用法，在放弃 TTS 之后已经不存在了。

## 三、三种模式的完整载荷

**每个请求只能选一种，字段不能越界。**

### 文生视频

只有 `web_search` 可用，默认 false。

```json
{"model": "bytedance/seedance-2-mini",
 "input": {"prompt": "…", "generate_audio": true, "resolution": "480p",
           "aspect_ratio": "9:16", "duration": 5, "web_search": false}}
```

### 首帧图生视频

```json
{"model": "bytedance/seedance-2-mini",
 "input": {"prompt": "…", "first_frame_url": "https://…", "generate_audio": true,
           "resolution": "480p", "aspect_ratio": "9:16", "duration": 6}}
```

### 首尾帧图生视频

```json
{"model": "bytedance/seedance-2-mini",
 "input": {"prompt": "…", "first_frame_url": "https://…", "last_frame_url": "https://…",
           "generate_audio": true, "resolution": "480p", "aspect_ratio": "9:16", "duration": 8}}
```

## 四、这个模型不支持的

- `reference_image_urls`、`reference_video_urls`、`reference_audio_urls` 一律不传。**当前模型不开放多模态参考模式**，传了会被拒或行为未定义。
- 图生模式不能带 `web_search`。
- 图生模式不能用 `adaptive` 比例。

所以生成清单里的「参考图」模式，只能落到首帧或首尾帧（见 SKILL 第二节的映射表）。

## 五、状态与结果解析

| 状态 | 含义 | 该做什么 |
|---|---|---|
| `waiting` | 排队 | 等 |
| `queuing` | 排队中 | 等 |
| `generating` | 生成中 | 等 |
| `success` | 完成 | 立刻下载 |
| `fail` | 失败 | 读 `failCode` / `failMsg`，不自动重提 |

结果地址在两个地方，按顺序找：

1. `data.resultJson`（字符串）→ 解析后取 `resultUrls`
2. `data.resultUrls` / `data.result_urls` / `data.urls`

**结果 URL 会过期。** 成功之后马上下载，别放着。

## 六、常见错误

| 报错 | 原因 | 处理 |
|---|---|---|
| `code != 200` | 参数或额度问题 | 看返回体里的 msg |
| `failCode` 存在 | 生成阶段失败 | 记下来，改提示词或换图 |
| 提交成功但查不到 taskId | 解析问题 | 用返回的原始 taskId 查 |
| 下载 403/404 | URL 过期 | 重新 query 同一 taskId 换新地址 |
| 上传失败 | 文件不存在或格式不支持 | 检查路径，用 png / jpg |

## 七、脚本对应关系

| 操作 | 命令 |
|---|---|
| 文生 | `create --mode text` |
| 首帧 | `create --mode first --first 图` |
| 首尾帧 | `create --mode first-last --first 图 --last 图` |
| 提交后等下载 | 加 `--wait --out 路径` |
| 只看请求体 | 加 `--dry-run`（不花钱） |
| 批量 | `batch --tasks 任务表.json --out-dir 目录`（默认 5 路并发，`--concurrency N` 可调） |
| 查状态 | `query --task-id xxx` |
| 单独等下载 | `wait --task-id xxx --out 路径` |
| 只上传 | `upload --file 图` |
