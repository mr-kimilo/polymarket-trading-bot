# Order Schedule API 文档和测试

本目录包含 Order Schedule API 的完整文档和测试工具。

## 快速开始

### 1. 启动 API 服务器

```bash
# 默认端口 5000
python scripts/strategy_api.py server

# 或指定端口和主机
python scripts/strategy_api.py server --host 0.0.0.0 --port 8080
```

### 2. 查看 API 文档

完整的 API 使用说明请查看：[docs/api/order-schedule-api.md](../api/order-schedule-api.md)

文档包含：
- 所有端点的详细说明
- 请求/响应参数
- 完整的代码示例（Python、JavaScript、cURL）
- 错误处理指南

### 3. 运行 API 测试

确保 API 服务器正在运行，然后执行：

```bash
python tests/integration/test_api_endpoints.py
```

测试将验证：
- ✅ 创建订单计划
- ✅ 查询订单计划
- ✅ 检查是否应该交易
- ✅ 取消订单计划
- ✅ 错误处理

## 文件说明

```
polymarket-trading-bot/
├── docs/
│   └── api/
│       └── order-schedule-api.md          # API 完整文档
├── tests/
│   └── integration/
│       └── test_api_endpoints.py          # API 集成测试脚本
└── scripts/
    └── strategy_api.py                    # API 服务器实现
```

## API 端点概览

| 方法 | 路径 | 描述 |
|------|------|------|
| POST | `/orderSchedule/create` | 创建订单计划 |
| POST | `/orderSchedule/cancel` | 取消订单计划 |
| GET | `/orderSchedule/query` | 查询订单计划 |
| GET | `/orderSchedule/check` | 检查是否应该交易 |

## 快速示例

### 创建计划

```bash
curl -X POST http://localhost:5000/orderSchedule/create \
  -H "Content-Type: application/json" \
  -d '{
    "env": "sim",
    "strategy_type": "1",
    "schedule_date": "2026-02-05",
    "start_time": "09:00",
    "end_time": "17:00"
  }'
```

### 查询计划

```bash
curl "http://localhost:5000/orderSchedule/query?env=sim&strategy_type=1"
```

### 检查交易时间

```bash
curl "http://localhost:5000/orderSchedule/check?env=sim&strategy_type=1"
```

更多示例请参见 [API 文档](../api/order-schedule-api.md)。

## 注意事项

1. 测试前请确保数据库连接正常
2. 建议使用 `sim` 环境进行测试
3. API 使用服务器本地时区
4. 日期格式：`YYYY-MM-DD`
5. 时间格式：`HH:MM`

## 相关任务

- 任务65: Order Schedule 功能实现
- 任务65补充: time_period 拆分为 start_time/end_time
- 任务66: API 使用说明文档生成

## 更新日志

- **2026-02-04**: 完成 API 文档和测试脚本（任务66）
- **2026-02-04**: 完成 time_period 拆分功能（任务65补充）
- **2026-01-20**: 初始 Order Schedule 功能（任务65）
