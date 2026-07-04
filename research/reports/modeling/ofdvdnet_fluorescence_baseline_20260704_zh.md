# OFDVDnet 荧光增强 Baseline 报告

## 处理结果

- 处理视频记录数：48
- 源 manifest：`C:\Users\876762330\Desktop\projects\osteo-vision\research\literature\inventory\ofdvdnet_video_manifest_20260704.csv`
- baseline manifest：`C:\Users\876762330\Desktop\projects\osteo-vision\research\literature\inventory\ofdvdnet_fluorescence_baseline_manifest_20260704.csv`
- 输出目录：`C:\Users\876762330\Desktop\projects\osteo-vision\research\datasets\public-candidates\d046_fluorescence_osteomyelitis_videos\derived\ofdvdnet\baseline_enhancement`
- 抽帧位置：视频相对位置 `0.5`
- 阈值 / 伪彩 / 融合透明度：`0.6` / `green` / `0.45`

## 方法

对 OFDVDnet 三视图视频读取中间帧，裁剪右上角荧光视图和左下角参考视图；荧光视图经过高斯去噪、百分位归一化、CLAHE 对比度增强、伪彩映射后，与参考视图进行 alpha 融合。

## 汇总指标

- 平均阳性面积比例：`0.0605206875`
- 平均 P95 强度：`0.6327693333333333`
- 平均强度：`0.13323664583333333`
- 非零阳性面积记录数：`48`

## 医学边界

OFDVDnet mock chicken-thigh fluorescence-guided surgery proxy; not jaw osteomyelitis or real intraoperative target-domain data.

该 baseline 只用于赛点一的荧光增强、伪彩稳定性和证据展示链路验证，不能作为颌骨骨髓炎诊断模型性能。
