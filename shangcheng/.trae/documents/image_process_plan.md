# 图片处理脚本逻辑重构计划

## 整体流程梳理

### 场景1：全新文件夹（首次运行）

```
1. 扫描文件夹中所有HB.JPG文件
   └── 得到：HB.JPG文件列表

2. 并发调用API获取提示词
   └── 为每个HB.JPG生成对应的提示词
   └── 保存到ach_config.json（一一对应）

3. 用Playwright生成ST.JPG
   └── 读取ach_config.json中的配置
   └── 执行任务生成ST.JPG
```

### 场景2：中断后继续（断点续传）

```
1. 扫描文件夹中所有HB.JPG文件
   └── 得到：HB.JPG文件列表

2. 读取ach_config.json中的已有提示词
   └── 检查JSON项数量与HB.JPG数量是否匹配
   └── 检查每个HB.JPG是否有对应的JSON项

3. 找出缺少提示词的HB.JPG
   └── 并发调用API生成提示词
   └── 更新ach_config.json

4. 检查哪些ST.JPG没有生成
   └── 从ach_config.json中读取所有配置
   └── 检查对应的ST.JPG是否存在

5. 让Playwright执行生成ST.JPG
   └── 只处理没有ST.JPG的任务
```

### 场景3：多轮执行（查漏补缺）

```
与场景2类似，但会多轮执行：
- 第1轮：处理所有没有ST.JPG的任务
- 第2轮：检查哪些任务仍然没有ST.JPG，重复处理
- 第3轮：...
- 直到所有任务完成或达到最大轮数
```

## 核心数据结构

### HB.JPG文件列表
从savexiumi_config.json中读取items，获取海报路径（HB.JPG）

### ach_config.json结构
```json
{
  "headless": true,
  "last_input_folder": "路径",
  "banana_prompt": "",
  "configs": [
    {
      "banana_prompt": "提示词",
      "banana_ref_img1": "HB.JPG完整路径",
      "banana_save_name": "文件名(HB)",
      "banana_img_dir": "目录路径",
      ...
    }
  ]
}
```

## 实现任务

### [ ] 任务1：重构跳过已处理逻辑
- **Priority**: P0
- **Description**:
  - 重新组织代码逻辑，分为两个主要阶段：
    1. 提示词生成阶段（API调用）
    2. 图片生成阶段（Playwright执行）
  - 确保JSON项与HB.JPG文件一一对应
- **Success Criteria**:
  - 代码逻辑清晰易懂
  - 能够正确处理断点续传

### [ ] 任务2：实现提示词生成阶段
- **Priority**: P0
- **Description**:
  - 扫描所有HB.JPG文件
  - 检查JSON中是否有对应项
  - 找出缺少提示词的HB.JPG
  - 并发调用API生成提示词
  - 更新ach_config.json
- **Success Criteria**:
  - 所有HB.JPG都有对应的JSON项
  - JSON项数量等于HB.JPG数量

### [ ] 任务3：实现图片生成阶段
- **Priority**: P0
- **Description**:
  - 从ach_config.json读取所有配置
  - 检查哪些ST.JPG还没有生成
  - 只对缺少ST.JPG的任务执行Playwright
  - 支持多轮查漏补缺
- **Success Criteria**:
  - 正确识别需要生成图片的任务
  - 执行后ST.JPG数量与HB.JPG数量一致

### [ ] 任务4：参数配置化
- **Priority**: P1
- **Description**:
  - 可配置：单个任务重试次数
  - 可配置：最大运行轮数
  - 可配置：并发数量
- **Success Criteria**:
  - 参数可通过常量配置
  - 参数可在运行时调整

### [ ] 任务5：测试验证
- **Priority**: P1
- **Description**:
  - 在测试文件夹中运行脚本
  - 验证各个场景都能正常工作
- **Success Criteria**:
  - 全新文件夹能完整处理
  - 中断后能正确续传
  - 多轮执行能查漏补缺
