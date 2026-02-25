# 图片下载重命名功能 - 实现计划

## [x] 任务1: 分析当前下载和重命名逻辑
- **Priority**: P1
- **Depends On**: None
- **Description**:
  - 分析 `ach_download_image_result` 函数的下载逻辑
  - 分析 `create_config_item` 函数的文件名生成逻辑
  - 分析 `rename_processed_files` 函数的重命名逻辑
- **Success Criteria**:
  - 完全理解当前的文件命名和重命名流程
- **Test Requirements**:
  - `programmatic` TR-1.1: 运行脚本，观察生成的文件名
  - `human-judgement` TR-1.2: 确认理解文件命名逻辑

## [x] 任务2: 修改下载逻辑直接保存为ST.jpg
- **Priority**: P0
- **Depends On**: 任务1
- **Description**:
  - 修改 `ach_download_image_result` 函数，当检测到文件名包含HB时，直接保存为ST.jpg
  - 确保一一对应，不弄乱文件
- **Success Criteria**:
  - 下载的图片直接保存为ST.jpg格式
  - 不再需要后续的重命名步骤
- **Test Requirements**:
  - `programmatic` TR-2.1: 运行脚本处理HB.jpg文件，验证生成的文件为ST.jpg
  - `programmatic` TR-2.2: 验证多个文件同时处理时一一对应

## [x] 任务3: 更新重命名逻辑（可选）
- **Priority**: P2
- **Depends On**: 任务2
- **Description**:
  - 如果需要，更新 `rename_processed_files` 函数以处理边界情况
  - 确保兼容性
- **Success Criteria**:
  - 重命名逻辑与新的下载逻辑兼容
- **Test Requirements**:
  - `programmatic` TR-3.1: 验证重命名函数不会破坏新的命名逻辑

## [x] 任务4: 测试和验证
- **Priority**: P1
- **Depends On**: 任务2, 任务3
- **Description**:
  - 在测试目录中运行脚本
  - 验证所有功能正常工作
- **Success Criteria**:
  - 脚本成功运行
  - 生成的文件名为ST.jpg
  - 没有文件混乱或丢失
- **Test Requirements**:
  - `programmatic` TR-4.1: 在测试目录中运行完整流程
  - `human-judgement` TR-4.2: 确认文件命名正确，无混乱