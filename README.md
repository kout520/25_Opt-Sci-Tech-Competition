# 25_Opt-Sci-Tech-Competition · 光电设计大赛小车追击视觉
> **2025 年全国大学生光电设计大赛（实物组）** 小车追击视觉项目 —— 基于 **嘉楠 K230**（RISC-V AI 视觉芯片 + KPU + nncase）的 AI 目标检测、追踪与激光打靶，助力小车追击类赛题高效开发！
[![K230](https://img.shields.io/badge/Chip-K230%20RISC--V-blue.svg)](https://developer.canaan-creative.com/k230/)
[![CanMV](https://img.shields.io/badge/Runtime-CanMV%20(MicroPython)-green.svg)]()
[![nncase](https://img.shields.io/badge/AI-nncase%20%2F%20KPU-orange.svg)]()
[![MIT](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT)

---
## 📖 项目简介
本项目是 **2025 年全国大学生光电设计大赛实物组** 的**小车追击视觉**方案，基于 **嘉楠 K230** 芯片开发。K230 集成 **KPU（神经网络处理器）** 与双核 RISC-V CPU，配合 **nncase** 工具链在片内直接运行 YOLO 目标检测模型，实现目标的实时检测、追踪与激光打靶。

系统通过 **UART 串口**与小车/云台协同：识别目标后计算偏移并下发 `@(x,y)` 帧，目标居中稳定后自动发射激光击毁，全程绿灯指示 + 蜂鸣器提示。代码基于 K230 **CanMV**（MicroPython）运行时，开箱即用，直接部署到 K230/K230D 开发板即可运行。✨

---
## ✨ 核心特性
- 🧠 **片内 AI 推理**：KPU + nncase 运行 YOLO（AnchorBaseDet）模型，320×320 输入实时检测，无需外部算力
- 🎯 **目标检测与追踪**：置信度 / NMS 后处理选最优目标，平滑跟踪（多帧均值滤波）
- 🔦 **激光打靶**：目标居中稳定后自动发射激光，绿灯指示、蜂鸣器提示，命中计数双发击毁
- 📡 **串口-小车协同**：向小车发送目标偏移 `@(x,y)`，接收小车启动指令（`@Go`），串口调试指令 `x+/x-/y+/y-` 在线标定靶位
- 📐 **面积突变判目标**：目标框面积变化阈值检测目标状态变化
- 🖥️ **多屏输出**：LCD（ST7701 800×480）/ HDMI（LT9611 1920×1080）实时显示 + OSD 叠加

---
## 🧩 已集成模块清单
| 文件 / 目录 | 功能说明 |
| :--- | :--- |
| `光电识别目标/main.py` | AI 目标检测 + 追踪 + 激光打靶主程序（状态机、偏移发送、命中判定） |
| `光电识别目标/mp_deployment_source/` | YOLO 模型 `best_AnchorBaseDet_*.kmodel` + `deploy_config.json` + 图像/视频检测脚本 |

---
## 🚀 快速上手
### 1. 环境要求
- **开发板**：嘉楠 K230 / K230D（或 K230 CanMV 套件）
- **运行时**：CanMV（K230 MicroPython 固件）
- **AI 工具链**：nncase（`.kmodel` 已编译好，见 `mp_deployment_source/`）
- **开发环境**：CanMV IDE 或任意串口终端（115200 bps）

### 2. 部署步骤
1.  克隆本仓库到本地：
    ```bash
    git clone https://github.com/kout520/25_Opt-Sci-Tech-Competition.git
    ```
2.  将 `光电识别目标/mp_deployment_source/` 整个目录拷贝到开发板 **SD 卡 `/sdcard/mp_deployment_source/`**
3.  用 CanMV IDE 打开 `光电识别目标/main.py`（或作为 `main.py` 放入 SD 卡开机自启），连接 K230 开发板运行
4.  根据硬件接线确认 GPIO（激光 / 绿灯 / 蜂鸣器 / UART1 / UART2）映射，启动后即可看到目标检测画面

### 3. 追击打靶协作流程
```
小车端  ──@Go────►  K230 端
                    (SCANNING) YOLO 检测目标 → 计算偏移
K230 端 ──@(x,y)──►  小车端（控制车身/云台对准目标）
                    (SCANNING) 目标居中稳定 → 发射激光 → 绿灯 + 蜂鸣
                    命中计数达 2 → 击毁 → 切换下一目标
```
- 串口协议：K230 向小车发送 `@(偏移x,偏移y)\r\n`；小车向 K230 发送 `@Go\r\n` 启动
- 调试指令：`x+ / x- / y+ / y-` 微调靶位框（对应不同远近 / 位置标定）

---
## 📂 项目结构
```
25_Opt-Sci-Tech-Competition/
├── 光电识别目标/                   # 小车追击视觉工程
│   ├── main.py                    # AI 目标检测 + 激光打靶主程序
│   └── mp_deployment_source/      # 部署包：kmodel + 配置 + 图像/视频检测
│       ├── best_AnchorBaseDet_*.kmodel
│       ├── deploy_config.json
│       └── det_image.py / det_video.py
├── .gitignore                     # Git 忽略文件
├── LICENSE                        # MIT 开源协议
└── README.md                      # 项目说明文档
```

---
## 📄 开源协议
本项目采用 **MIT License** 开源协议，详细协议请查看 [LICENSE](./LICENSE) 文件。

---
## 🎉 致谢
感谢嘉楠科技提供的 K230 芯片与 CanMV / nncase 开源生态，祝各位在光电设计大赛中取得优异成绩！
---
