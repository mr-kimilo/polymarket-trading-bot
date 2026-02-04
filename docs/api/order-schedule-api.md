# Order Schedule API 使用说明

订单计划调度 API 文档（任务66）

## 服务启动

```bash
# 启动 API 服务器（默认端口 5000）
python scripts/strategy_api.py server

# 指定端口和主机
python scripts/strategy_api.py server --host 0.0.0.0 --port 8080
```

服务启动后，API 将在 `http://localhost:5000` 上可用。

---

## API 接口列表

### 1. 创建订单计划

**接口**: `POST /orderSchedule/create`

**描述**: 创建一个新的订单交易时间计划

**请求头**:
```
Content-Type: application/json
```

**请求参数**:

| 参数名 | 类型 | 必填 | 说明 | 示例 |
|--------|------|------|------|------|
| env | string | 是 | 环境类型 | "prod" 或 "sim" |
| strategy_type | string | 是 | 策略类型 | "1", "2", "3" |
| schedule_date | string | 是 | 计划日期 (YYYY-MM-DD) | "2026-02-05" |
| start_time | string | 是 | 开始时间 (HH:MM) | "09:00" |
| end_time | string | 是 | 结束时间 (HH:MM) | "17:00" |

**请求示例**:

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

**响应参数**:

| 参数名 | 类型 | 说明 |
|--------|------|------|
| success | boolean | 操作是否成功 |
| message | string | 操作结果消息 |
| schedule_id | integer/null | 创建的计划ID（成功时返回） |

**成功响应示例**:
```json
{
  "success": true,
  "message": "Order schedule created successfully",
  "schedule_id": 123
}
```

**失败响应示例**:
```json
{
  "success": false,
  "message": "Invalid date format: 2026-2-5. Use YYYY-MM-DD",
  "schedule_id": null
}
```

**错误码**:
- `400` - 缺少必填参数或参数格式错误

---

### 2. 取消订单计划

**接口**: `POST /orderSchedule/cancel`

**描述**: 取消指定的订单计划（将状态设置为已取消）

**请求头**:
```
Content-Type: application/json
```

**请求参数**:

| 参数名 | 类型 | 必填 | 说明 | 示例 |
|--------|------|------|------|------|
| schedule_id | integer | 是 | 要取消的计划ID | 123 |

**请求示例**:

```bash
curl -X POST http://localhost:5000/orderSchedule/cancel \
  -H "Content-Type: application/json" \
  -d '{
    "schedule_id": 123
  }'
```

**响应参数**:

| 参数名 | 类型 | 说明 |
|--------|------|------|
| success | boolean | 操作是否成功 |
| message | string | 操作结果消息 |

**成功响应示例**:
```json
{
  "success": true,
  "message": "Order schedule 123 canceled successfully"
}
```

**失败响应示例**:
```json
{
  "success": false,
  "message": "Failed to cancel order schedule 123. It may not exist or already processed."
}
```

**错误码**:
- `400` - 缺少 schedule_id 参数

---

### 3. 查询订单计划

**接口**: `GET /orderSchedule/query`

**描述**: 查询符合条件的订单计划列表

**请求参数** (Query Parameters):

| 参数名 | 类型 | 必填 | 说明 | 示例 |
|--------|------|------|------|------|
| env | string | 否 | 环境筛选 | "prod" 或 "sim" |
| strategy_type | string | 否 | 策略类型筛选 | "1", "2", "3" |
| schedule_date | string | 否 | 日期筛选 (YYYY-MM-DD) | "2026-02-05" |
| status | integer | 否 | 状态筛选 | 0=计划中, 1=运行中, 2=已完成, 3=已取消 |

**请求示例**:

```bash
# 查询所有计划
curl http://localhost:5000/orderSchedule/query

# 查询模拟环境的策略1的计划
curl "http://localhost:5000/orderSchedule/query?env=sim&strategy_type=1"

# 查询特定日期的所有计划
curl "http://localhost:5000/orderSchedule/query?schedule_date=2026-02-05"

# 查询状态为计划中的所有计划
curl "http://localhost:5000/orderSchedule/query?status=0"
```

**响应参数**:

| 参数名 | 类型 | 说明 |
|--------|------|------|
| success | boolean | 操作是否成功 |
| message | string | 操作结果消息 |
| schedules | array | 计划列表 |
| count | integer | 计划数量 |

**schedules 数组元素结构**:

| 字段名 | 类型 | 说明 |
|--------|------|------|
| id | integer | 计划ID |
| create_dt | string | 创建时间 (ISO 8601) |
| env | string | 环境 |
| strategy_type | string | 策略类型 |
| schedule_date | string | 计划日期 |
| start_time | string | 开始时间 (HH:MM:SS) |
| end_time | string | 结束时间 (HH:MM:SS) |
| status | integer | 状态 (0=计划中, 1=运行中, 2=已完成, 3=已取消) |

**成功响应示例**:
```json
{
  "success": true,
  "message": "Found 2 schedules",
  "schedules": [
    {
      "id": 123,
      "create_dt": "2026-02-04T21:00:00",
      "env": "sim",
      "strategy_type": "1",
      "schedule_date": "2026-02-05",
      "start_time": "09:00:00",
      "end_time": "17:00:00",
      "status": 0
    },
    {
      "id": 124,
      "create_dt": "2026-02-04T21:15:00",
      "env": "sim",
      "strategy_type": "2",
      "schedule_date": "2026-02-05",
      "start_time": "10:00:00",
      "end_time": "16:00:00",
      "status": 0
    }
  ],
  "count": 2
}
```

**失败响应示例**:
```json
{
  "success": false,
  "message": "Invalid date format: 2026-2-5. Use YYYY-MM-DD",
  "schedules": [],
  "count": 0
}
```

---

### 4. 检查是否应该交易

**接口**: `GET /orderSchedule/check`

**描述**: 检查当前时间是否在指定环境和策略的交易时间段内

**请求参数** (Query Parameters):

| 参数名 | 类型 | 必填 | 说明 | 示例 |
|--------|------|------|------|------|
| env | string | 是 | 环境类型 | "prod" 或 "sim" |
| strategy_type | string | 是 | 策略类型 | "1", "2", "3" |

**请求示例**:

```bash
# 检查模拟环境的策略1是否应该交易
curl "http://localhost:5000/orderSchedule/check?env=sim&strategy_type=1"

# 检查生产环境的策略2是否应该交易
curl "http://localhost:5000/orderSchedule/check?env=prod&strategy_type=2"
```

**响应参数**:

| 参数名 | 类型 | 说明 |
|--------|------|------|
| success | boolean | 操作是否成功 |
| should_trade | boolean | 是否应该交易 |
| message | string | 操作结果消息 |

**成功响应示例（在交易时间内）**:
```json
{
  "success": true,
  "should_trade": true,
  "message": "In scheduled trading time"
}
```

**成功响应示例（不在交易时间内）**:
```json
{
  "success": true,
  "should_trade": false,
  "message": "Not in scheduled trading time"
}
```

**失败响应示例**:
```json
{
  "success": false,
  "should_trade": false,
  "message": "env and strategy_type are required"
}
```

**错误码**:
- `400` - 缺少必填参数

---

## 状态码说明

### HTTP 状态码

- `200 OK` - 请求成功
- `400 Bad Request` - 请求参数错误或缺少必填参数
- `500 Internal Server Error` - 服务器内部错误

### 计划状态 (status)

| 值 | 说明 | 描述 |
|----|------|------|
| 0 | plan | 计划中 - 计划已创建但尚未到执行时间 |
| 1 | running | 运行中 - 计划正在执行中 |
| 2 | completed | 已完成 - 计划已执行完毕 |
| 3 | canceled | 已取消 - 计划被用户取消 |

---

## 完整使用示例

### Python 示例

```python
import requests
import json
from datetime import date, timedelta

BASE_URL = "http://localhost:5000"

# 1. 创建订单计划
def create_schedule():
    url = f"{BASE_URL}/orderSchedule/create"
    payload = {
        "env": "sim",
        "strategy_type": "1",
        "schedule_date": (date.today() + timedelta(days=1)).isoformat(),
        "start_time": "09:00",
        "end_time": "17:00"
    }
    response = requests.post(url, json=payload)
    result = response.json()
    print(f"Create: {result}")
    return result.get('schedule_id')

# 2. 查询订单计划
def query_schedules():
    url = f"{BASE_URL}/orderSchedule/query"
    params = {"env": "sim", "strategy_type": "1"}
    response = requests.get(url, params=params)
    result = response.json()
    print(f"Query: {result}")
    return result

# 3. 检查是否应该交易
def check_trading():
    url = f"{BASE_URL}/orderSchedule/check"
    params = {"env": "sim", "strategy_type": "1"}
    response = requests.get(url, params=params)
    result = response.json()
    print(f"Check: {result}")
    return result.get('should_trade')

# 4. 取消订单计划
def cancel_schedule(schedule_id):
    url = f"{BASE_URL}/orderSchedule/cancel"
    payload = {"schedule_id": schedule_id}
    response = requests.post(url, json=payload)
    result = response.json()
    print(f"Cancel: {result}")
    return result

# 执行示例
if __name__ == "__main__":
    # 创建计划
    schedule_id = create_schedule()
    
    # 查询计划
    query_schedules()
    
    # 检查交易
    should_trade = check_trading()
    
    # 取消计划
    if schedule_id:
        cancel_schedule(schedule_id)
```

### JavaScript (Node.js) 示例

```javascript
const axios = require('axios');

const BASE_URL = 'http://localhost:5000';

// 1. 创建订单计划
async function createSchedule() {
  try {
    const response = await axios.post(`${BASE_URL}/orderSchedule/create`, {
      env: 'sim',
      strategy_type: '1',
      schedule_date: '2026-02-05',
      start_time: '09:00',
      end_time: '17:00'
    });
    console.log('Create:', response.data);
    return response.data.schedule_id;
  } catch (error) {
    console.error('Error:', error.response?.data);
  }
}

// 2. 查询订单计划
async function querySchedules() {
  try {
    const response = await axios.get(`${BASE_URL}/orderSchedule/query`, {
      params: { env: 'sim', strategy_type: '1' }
    });
    console.log('Query:', response.data);
    return response.data;
  } catch (error) {
    console.error('Error:', error.response?.data);
  }
}

// 3. 检查是否应该交易
async function checkTrading() {
  try {
    const response = await axios.get(`${BASE_URL}/orderSchedule/check`, {
      params: { env: 'sim', strategy_type: '1' }
    });
    console.log('Check:', response.data);
    return response.data.should_trade;
  } catch (error) {
    console.error('Error:', error.response?.data);
  }
}

// 4. 取消订单计划
async function cancelSchedule(scheduleId) {
  try {
    const response = await axios.post(`${BASE_URL}/orderSchedule/cancel`, {
      schedule_id: scheduleId
    });
    console.log('Cancel:', response.data);
    return response.data;
  } catch (error) {
    console.error('Error:', error.response?.data);
  }
}

// 执行示例
(async () => {
  const scheduleId = await createSchedule();
  await querySchedules();
  await checkTrading();
  if (scheduleId) {
    await cancelSchedule(scheduleId);
  }
})();
```

### cURL 完整流程示例

```bash
# 1. 创建明天的交易计划（9:00-17:00）
curl -X POST http://localhost:5000/orderSchedule/create \
  -H "Content-Type: application/json" \
  -d '{
    "env": "sim",
    "strategy_type": "1",
    "schedule_date": "2026-02-05",
    "start_time": "09:00",
    "end_time": "17:00"
  }'

# 响应: {"success": true, "message": "Order schedule created successfully", "schedule_id": 123}

# 2. 查询所有模拟环境的策略1计划
curl "http://localhost:5000/orderSchedule/query?env=sim&strategy_type=1"

# 3. 检查当前是否在交易时间内
curl "http://localhost:5000/orderSchedule/check?env=sim&strategy_type=1"

# 4. 取消计划
curl -X POST http://localhost:5000/orderSchedule/cancel \
  -H "Content-Type: application/json" \
  -d '{"schedule_id": 123}'
```

---

## 错误处理

### 常见错误及解决方案

1. **数据库连接失败**
   ```json
   {
     "success": false,
     "message": "Database not connected"
   }
   ```
   解决方案: 检查数据库配置和连接状态

2. **日期格式错误**
   ```json
   {
     "success": false,
     "message": "Invalid date format: 2026-2-5. Use YYYY-MM-DD"
   }
   ```
   解决方案: 使用正确的日期格式 YYYY-MM-DD

3. **时间格式错误**
   ```json
   {
     "success": false,
     "message": "Invalid time format. Use HH:MM (e.g., '09:00')"
   }
   ```
   解决方案: 使用正确的时间格式 HH:MM

4. **缺少必填参数**
   ```json
   {
     "success": false,
     "message": "env is required"
   }
   ```
   解决方案: 确保所有必填参数都已提供

---

## 注意事项

1. **时间格式**: 
   - 日期使用 `YYYY-MM-DD` 格式 (例如: "2026-02-05")
   - 时间使用 `HH:MM` 格式 (例如: "09:00")
   - 查询结果中的时间为 `HH:MM:SS` 格式

2. **环境类型**: 
   - `prod` - 生产环境
   - `sim` - 模拟环境

3. **策略类型**: 
   - `"1"` - 策略1
   - `"2"` - 策略2
   - `"3"` - 策略3

4. **状态管理**: 
   - 只有状态为 `0` (计划中) 的计划可以被取消
   - `check` 接口只检查状态为 `0` (计划中) 且日期为今天的计划

5. **时区**: 所有时间均使用服务器本地时区

---

## 测试建议

1. 使用 `sim` 环境进行测试，避免影响生产数据
2. 先创建计划，再使用 `check` 接口验证时间判断逻辑
3. 测试边界情况（如跨天时间段、同一时间点的开始和结束）
4. 验证取消操作后计划状态的正确性

---

## 更新日志

- **v1.0** (2026-02-04): 初始版本，支持基本的创建、查询、检查和取消功能
- **v1.1** (2026-02-04): time_period 拆分为 start_time 和 end_time 独立字段

---

## 技术支持

如有问题或建议，请联系开发团队或提交 Issue。
