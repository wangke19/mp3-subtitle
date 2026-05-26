# MP3 卡拉OK 字幕生成器设计

**日期**: 2026-05-26
**版本**: v2 (revised after brainstorming)

## 概述

输入 MP3 + 封面图 + 歌词文本，输出带逐字卡拉OK 字幕的 MP4 视频（1080x1080）。
使用 WhisperX 进行转写 + 强制对齐，获得字符级时间戳，生成 ASS `\kf` 平滑覆盖字幕。

## 流水线

```
MP3 + cover.jpg + lyrics.txt
    → transcribe.py  (WhisperX: faster-whisper 转写 + wav2vec2 强制对齐)
    → align.py       (字符时间戳 → 歌词行映射)
    → subtitle.py    (ASS 卡拉OK 字幕, \kf 逐字符覆盖)
    → render.py      (ffmpeg: 封面 + 模糊背景 + 字幕 → MP4)
    → output.mp4
```

## 技术规格

### 依赖
- whisperx (包含 faster-whisper + wav2vec2 对齐)
- ffmpeg (命令行工具，需在 PATH 中)
- Python >= 3.10 + argparse (标准库)

### 模型选择
- **ASR 模型**: `large-v3` (~5GB, WhisperX 文档明确推荐 non-English 使用 large)
- **对齐模型**: `jonatasgrosman/wav2vec2-large-xlsr-53-chinese-zh-cn` (WhisperX 自动选择)
- **量化**: CPU + INT8

### Stage 1: 转写 + 对齐 (`transcribe.py`)

使用 WhisperX 完成转写和强制对齐两步：

```python
model = whisperx.load_model("large-v3", device="cpu", compute_type="int8",
                             language="zh", asr_options={"word_timestamps": True})
audio = whisperx.load_audio(mp3_path)
result = model.transcribe(audio, batch_size=8, language="zh")

# 强制对齐 (字符级)
model_a, metadata = whisperx.load_align_model(language_code="zh", device="cpu")
result = whisperx.align(result["segments"], model_a, metadata, audio,
                         device="cpu", return_char_alignments=True)
```

**输出 JSON 格式** (`transcript.json`):
```json
{
  "segments": [
    {
      "start": 10.5,
      "end": 15.2,
      "text": "今天天气真好",
      "chars": [
        {"char": "今", "start": 10.50, "end": 10.80},
        {"char": "天", "start": 10.80, "end": 11.10},
        {"char": "天", "start": 11.10, "end": 11.40},
        {"char": "气", "start": 11.40, "end": 11.75},
        {"char": "真", "start": 11.75, "end": 12.20},
        {"char": "好", "start": 12.20, "end": 12.60}
      ]
    }
  ]
}
```

**已知问题与缓解**:
- NLTK 句子分割对中文不可靠 → 使用 VAD 段落分割，不依赖 NLTK
- 部分生僻字不在对齐模型词典中 → 回退到 WhisperX 原始 word-level 时间戳
- 对齐模型 CER ~19% → 通过 lyrics 映射阶段容错

### Stage 2: 歌词映射 (`align.py`)

将 WhisperX 字符时间戳映射到用户提供的歌词行。

**算法**:
1. 将所有转写字符扁平化为一个带时间戳的序列
2. 对每行歌词，使用 `difflib.SequenceMatcher` 在转写序列中找最佳匹配子序列
3. 分配每行歌词的起止时间为匹配字符的起止时间
4. 转写中的额外内容（语气词、噪声）自动跳过
5. 歌词中未匹配的字符通过线性插值分配时间

**输入**: `transcript.json` + `lyrics.txt`
**输出**: `aligned.json`

```json
{
  "lines": [
    {
      "line_no": 1,
      "text": "今天天气真好",
      "start": 10.50,
      "end": 12.60,
      "chars": [
        {"char": "今", "start": 10.50, "end": 10.80},
        {"char": "天", "start": 10.80, "end": 11.10},
        ...
      ]
    }
  ]
}
```

**特性**:
- 容错语气词（啊、嗯、la~）
- 容错歌词省略/重复段落
- 不可匹配的歌词行标记为 warning，使用前后行插值时间

### Stage 3: ASS 字幕生成 (`subtitle.py`)

#### `\kf` 平滑覆盖

每行歌词生成一个 ASS Dialogue 事件。每个字符独立的 `\kf` 块：

```ass
Dialogue: 0,0:00:10.50,0:00:15.20,Karaoke,,0,0,0,,{\kf50}今{\kf30}天{\kf30}天{\kf35}气{\kf45}真{\kf40}好
```

`\kf` 参数为百分之一秒 (centiseconds)。

#### 样式定义

```ass
Style: Karaoke,KaiTi,48,&H00FFFFFF,&H0000D7FF,&H00000000,&H80000000,
       -1,0,0,0,100,100,0,0,1,3,0,2,10,10,30,1
```

- **字体**: KaiTi (楷体), 48pt
- **未高亮** (`\1c`): 白色 (#FFFFFF) + 黑色描边
- **高亮** (`\2c`): 金色 (#FFD700)，`\kf` 扫过时显示
- 注: `\kf` 不支持单行内渐变色，高亮色为固定金色；如需渐变需通过多行或自定义覆盖实现
- **描边**: 3px 黑色，保证任何背景上可读
- **阴影**: 半透明，增加层次感
- **位置**: 底部居中，垂直 margin 30px 避开平台水印

#### 行显示逻辑

- 当前行在首字符前 0.5s 出现（预读）
- 新行开始时旧行淡出
- 最多同时显示 2 行（当前行 + 淡出中的前一行）

#### 样式预设

存放在 `styles/` 目录下，每个预设为一个 ASS style 片段。

### Stage 4: 渲染合成 (`render.py`)

#### 封面图处理

1. 将封面图缩放到 1080x1080 内（保持宽高比）
2. 创建封面图的模糊版本作为背景层（1080x1080）
3. 将缩放后的封面居中叠加在模糊背景上

#### ffmpeg 三步流程

```bash
# Step 1: 生成封面帧 (scale + blur bg)
ffmpeg -i cover.jpg -filter_complex \
  "[0:v]scale=1080:1080:force_original_aspect_ratio=decrease[fg]; \
   [0:v]scale=1080:1080:force_original_aspect_ratio=increase,boxblur=20[bg]; \
   [bg][fg]overlay=(W-w)/2:(H-h)/2" \
  -frames:v 1 cover_frame.png

# Step 2: 静态图 + 音频 → 视频
ffmpeg -loop 1 -i cover_frame.png -i song.mp3 \
  -c:v libx264 -tune stillimage -c:a aac -b:a 192k \
  -pix_fmt yuv420p -shortest base_video.mp4

# Step 3: 烧录 ASS 字幕
ffmpeg -i base_video.mp4 -vf "subtitles=karaoke.ass" -c:a copy output.mp4
```

#### 无封面图时

使用渐变背景代替：
```bash
ffmpeg -f lavfi -i "color=c=black:s=1080x1080:d=999,gradient=color1=0x1a1a2e:color2=0x16213e" ...
```

### 输出规格
- 分辨率: 1080x1080
- 编码: H.264 (`-tune stillimage` 优化静态背景)
- 音频: AAC 192kbps
- 字幕: ASS 内嵌 (硬字幕烧录)

## CLI 接口 (`run.py`)

```bash
# 基本用法
python run.py song.mp3 --cover cover.jpg --lyrics lyrics.txt

# 完整选项
python run.py song.mp3 --cover cover.jpg --lyrics lyrics.txt \
    --output my_video.mp4 \
    --model large-v3 \
    --language zh \
    --style default
```

### 参数说明

| 参数 | 必选 | 默认值 | 说明 |
|------|------|--------|------|
| `song.mp3` | 是 | - | 输入音频文件 |
| `--cover` | 否 | 渐变背景 | 封面图文件 |
| `--lyrics` | 否 | 纯转写模式 | 歌词文本文件（纯文本，空行分行） |
| `--output` | 否 | `output.mp4` | 输出文件名 |
| `--model` | 否 | `large-v3` | Whisper 模型 |
| `--language` | 否 | `zh` | 语言代码 |
| `--style` | 否 | `default` | ASS 样式预设 |

### 纯转写模式

省略 `--lyrics` 时，直接使用 WhisperX 转写结果生成卡拉OK 字幕（无歌词映射，直接用转写文本）。

## 项目结构

```
mp3-subtitle/
├── src/
│   ├── transcribe.py    # WhisperX 转写 + 强制对齐
│   ├── align.py          # 歌词行映射 (SequenceMatcher)
│   ├── subtitle.py       # ASS 卡拉OK 字幕生成
│   └── render.py         # ffmpeg 合成 (封面 + 字幕)
├── styles/               # ASS 样式预设
│   └── default.ass
├── requirements.txt
└── run.py                # CLI 主入口
```

## 中间产物

流水线各阶段产生可检查的中间文件（均在 temp 目录中）：

| 阶段 | 输入 | 输出 |
|------|------|------|
| transcribe | song.mp3 | transcript.json |
| align | transcript.json + lyrics.txt | aligned.json |
| subtitle | aligned.json | karaoke.ass |
| render | karaoke.ass + cover + song.mp3 | output.mp4 |

中间文件可用于调试和阶段重跑（如调整字幕样式无需重新转写）。

## 输入格式

### 歌词文件 (`lyrics.txt`)
- 纯文本，UTF-8 编码
- 空行分隔歌词段落（verse/chorus）
- 无时间戳，无标记语言

示例：
```
今天天气真好
阳光明媚温暖

我想出去走走
看看这个世界
```

### 封面图
- JPG/PNG 格式
- 任意尺寸（自动缩放）
- 推荐 600x600+

## 参考资料

- [WhisperX GitHub](https://github.com/m-bain/whisperX) — 转写 + 强制对齐核心库
- [WhisperX 中文对齐模型](https://huggingface.co/jonatasgrosman/wav2vec2-large-xlsr-53-chinese-zh-cn) — 默认中文 wav2vec2 模型
- [ASS 卡拉OK 特效规范](https://aegi.vmoe.info/docs/3.0/ASS_Tags/) — `\kf` 标签文档
