# JSON Contracts

All numeric episode orders are 1-based and consecutive.

## Adaptation

```json
{
  "title": "她请我拍最后一张",
  "genre": "都市情感悬疑",
  "target_audience": "偏好强反转与关系救赎的竖屏短剧用户",
  "logline": "婚礼摄影师发现三年前的盗图仇人正被同一个人继续控制。",
  "positioning": "婚礼倒计时中的证据反击与关系反转",
  "main_pleasure_line": "旧怨被重新解释，两位女性从敌对走向联合反击",
  "adaptation_strategy": "压缩校园往事，把三年前的冲突变成婚礼现场不断被揭开的证据。",
  "must_keep": [
    "摄影师拥有原始 RAW 文件",
    "盗图事件发生在三年前",
    "新娘曾因家人的工作受到威胁"
  ],
  "allowed_changes": [
    "合并两个次要同学角色",
    "把小说中的心理独白改成现场对话"
  ],
  "deviations": [
    "新增婚礼直播控制室，作为证据恢复和公开对峙的空间"
  ],
  "characters": [
    {
      "name": "林夏",
      "role": "婚礼摄影师、主角",
      "motivation": "查清旧案并决定是否公开真相",
      "visual_anchor": "29岁，清瘦，黑色短发，深灰工装摄影马甲，右手腕戴旧相机快门手链"
    },
    {
      "name": "苏遥",
      "role": "新娘、表面上的旧案加害者",
      "motivation": "摆脱控制并保护家人",
      "visual_anchor": "28岁，肩长发，白色极简婚纱，左手始终握着一枚旧存储卡"
    }
  ],
  "paywall_plan": {
    "first_paywall_at": 9,
    "free_episodes": 8,
    "cadence": 2,
    "cliffhanger_threshold": 75,
    "note": "第8集压低情绪，第9集用公开投屏完成首次强反转"
  }
}
```

`paywall_plan` may be `null` when the production is not using paid episodes.

## Episodes

```json
{
  "episodes": [
    {
      "order": 1,
      "title": "删掉三年前的照片",
      "hook_opening": "新娘把一张存储卡塞进摄影师手中，要求她立刻删除全部旧照片。",
      "hook_type": "危机请求",
      "conflict": "摄影师认出新娘正是当年的盗图者，却无法判断她为何恐惧。",
      "cliffhanger": "存储卡里出现一张今天拍摄、摄影师从未按过快门的照片。",
      "emotion_net": -2,
      "source_beats": ["婚礼重逢", "旧案记忆", "删除请求"],
      "target_duration_sec": 90,
      "is_paywall": false
    },
    {
      "order": 2,
      "title": "不属于我的照片",
      "hook_opening": "照片开始倒计时自动删除。",
      "hook_type": "倒计时",
      "conflict": "新娘拒绝解释，婚礼助理又收走了摄影师的设备。",
      "cliffhanger": "设备编号指向新郎家族公司的服务器。",
      "emotion_net": -1,
      "source_beats": ["证据线索", "设备被收"],
      "target_duration_sec": 90,
      "is_paywall": false
    }
  ]
}
```

The episode count in the input must equal the confirmed project setting.

## Script

```json
{
  "content": "场景 1｜婚礼宴会厅｜日\n\n动作：苏遥穿过宾客，把一张银色存储卡塞进林夏掌心。\n\n苏遥：全部删掉。现在。\n\n林夏：你凭什么命令我？\n\n动作：苏遥看见二楼有人举着手机拍摄，立刻后退半步。\n\n苏遥：三年前的事，今晚不能再出现。\n\n场景 2｜控制室｜日\n\n动作：林夏把存储卡插入读卡器，屏幕自动弹出照片。\n\n林夏：这张照片不是今天拍的。\n\n助理：所以你要删，不是要看。\n\n动作：照片右下角开始倒计时。",
  "duration_sec": 90,
  "scene_count": 2,
  "opening_3s": "新娘把存储卡塞给摄影师并要求立刻删除旧照片。",
  "ending_cliffhanger": "照片倒计时结束后自动上传，幕后控制者开始远程删除证据。",
  "newly_introduced_facts": [
    "婚礼二楼有人持续监视新娘",
    "存储卡连接着远程自动上传程序"
  ],
  "episode_summary": "林夏被迫重新面对三年前的旧案，并发现证据正在被远程操控。"
}
```

## Quality

```json
{
  "status": "repairable",
  "score": {
    "hook": 78,
    "density": 55,
    "paywall": 40,
    "emotion": 70,
    "duration": 85,
    "consistency": 90,
    "overall": 70
  },
  "flags": [
    {
      "severity": "high",
      "code": "middle_exposition",
      "evidence": "场景 2 连续两段人物解释三年前的账号归属。",
      "suggestion": "把解释改成林夏逼问苏遥时逐步出现的登录记录与反应镜头。"
    }
  ],
  "repair_plan": {
    "mode": "patch",
    "instruction": "保留开场与结尾，重写中段对白，让每句解释同时改变权力关系。"
  }
}
```

## Storyboard

```json
{
  "summary": "婚礼现场的对峙与远程证据删除，建立旧案主线。",
  "shots": [
    {
      "order": 1,
      "shot_size": "中近景",
      "camera_move": "手持跟拍",
      "duration_sec": 4,
      "location": "婚礼宴会厅",
      "action": "苏遥穿过人群，将银色存储卡塞进林夏掌心。",
      "dialogue": "苏遥：全部删掉。现在。",
      "character_refs": ["苏遥", "林夏"],
      "visual_prompt": "9:16竖屏，现代婚礼宴会厅，人群虚化，白色婚纱的新娘把银色存储卡压进摄影师的掌心，近景手部与两人紧张表情同框"
    }
  ]
}
```

Shot counts and durations must reflect the actual episode, not these illustrative examples.
