# 🐞 Bug 记录（精简版）

---

## 1 核心基本信息
| 字段       | 内容                  |
| ---------- | --------------------- |
| Bug ID     | {{bug_id}}            |
| 产品线     | {{product_line}}      |
| 芯片型号   | {{chip_model}}        |
| 固件版本   | {{firmware_version}}  |
| 严重级别   | {{severity}}          |
| 提报人/时间 | {{reporter}} / {{date}} |

---

## 2 问题现象
核心现象（必填）区系
{{description}}

衍生现象（可选）
{{secondary_effect}}

---

## 3 复现核心信息
### 触发条件
前置条件：{{pre_condition}}
触发步骤：{{steps}}

### 复现关键
复现概率：{{reproduce_rate}}
复现依赖：{{reproduce_condition}}

---

## 4 运行环境（精简）
硬件/外部设备：{{hardware_env}} + {{external_device}}
软件/测试工具：{{software_env}} + {{test_tools}}

---

## 5 关键证据（核心）
日志/波形/抓包（按需填）：{{log}} / {{waveform}} / {{packet}}

---

## 6 根因与解决方案
### 根因
表层原因：{{surface_cause}}
深层原因：{{root_cause}}
Root Cause 类型（勾选）：
* [ ] 设计缺陷  * [ ] 实现错误  * [ ] 硬件行为差异  * [ ] 兼容问题  * [ ] 其他

### 修复方案
临时修复：{{patch}}
长期方案：{{long_term_solution}}

---

## 7 补充信息（可选）
排查路径：{{debug_steps}}
标签：{{tags}}