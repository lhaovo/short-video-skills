# 资产清单 · {{标题}}

> 目录：`outputs/{{YYYY-MM-DD-标题}}` ｜ 目标模型：{{Seedance}} ｜ 画幅：{{9:16}} ｜ 资产数：{{N}}

---

## 一、总表

| 编号 | 类型 | 用途 | 来源 | 被哪些段引用 | 状态 |
|---|---|---|---|---|---|
| PR-01 | 产品主体 | 一致性母版 | 真实拍摄 | {{S01、S02}} | {{已有}} |
| PR-02 | 产品细节 | {{讲参数}} | {{AI（真实图打底）}} | {{S03}} | {{待出图}} |
| SC-01 | 场景 | 环境 | AI 生成 | {{S01、S03}} | {{待出图}} |
| CH-01 | 人物手部 | {{使用动作}} | AI 生成 | {{S02}} | {{待出图}} |

---

## 二、生产顺序

1. `PR-01` 产品主体 —— 一切镜头的身份锚点，最先做、最严做
2. `SC-01` 场景 —— 空间基准
3. `CH-01` 人物手部
4. `PR-02` 细节（依赖母版）

---

## 三、图像提示词

### PR-01 · 产品主体（母版）

```text
纯白无缝背景，{{产品全称}} 正面 45 度视角，完整可见，比例不变形。
{{材质}}：双层不锈钢，哑光白漆，接缝在底部一圈；
{{印刷}}：侧面纵向银色 logo，字形完整；
{{结构}}：杯盖浅灰硅胶圈可见。
均匀柔和的顶部漫射光 + 左右补光，金属低反光，避免镜面高光与硬阴影。
商业产品摄影，干净克制，无道具，无手，无文字叠加。
4K，边缘锐利，印刷清晰可读，几何对称。
no text overlay, no watermark, no logo distortion, no misspelled label,
no reflection artifacts, no harsh shadow, no oily specular highlight,
no extra parts, no floating object, no hand, no props
```

### SC-01 · 场景

```text
{{画幅}}，{{空间整体结构与体量}}。前景：{{}}；中景：{{}}；远景：{{}}。
机位：{{平视，略高}}。光影：{{主光颜色+方向}}，{{阴影色调}}。
空气：{{清晨薄尘，窗边有细微光斑}}。
写实，商业质感，无人物。
no people, no text, no watermark, no clutter
```

### CH-01 · 人物手部

```text
{{画幅}}，女性手部特写，{{年龄感}}，{{袖口描述}}，指甲干净无修饰。
手停在{{抓握进行到一半}}的状态，拇指压在{{}}边缘。
{{环境简要}}。{{光位与色温}}。写实，皮肤自然。
no freckles, no facial spots, even natural daylight, no studio strobe,
no split lighting, skin clean smooth and even-toned,
no oily specular highlights, no blotchy redness,
keep the image sharp and in focus
```

> 每张图都要写全主体外观，不写「同上」。模型没有记忆。

---

## 四、资产图自查

- [ ] 同一产品在不同图里形状、比例、接缝位置一致
- [ ] logo 字形完整、无错字、未被「优化」
- [ ] 白底图里没有环境、投影、道具
- [ ] 一张图没有塞四个视角
- [ ] 人物图肤色、发型、服装在各视图统一
- [ ] 图上没有文字、水印、UI 边框
- [ ] 产品镜头来源已标明；有参数/功效宣称的镜头用了实拍或官方素材；纯 AI 的产品图已锁几何与印刷
