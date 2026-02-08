-- ============================================================
-- Polymarket Trading Bot - 数据库初始化脚本
-- ============================================================
-- 说明: 
--   这个脚本只需要运行一次来初始化数据库
--   后续启动不会再执行DDL操作，只会检查表是否存在
-- 
-- 使用方法:
--   psql -U sniper_user -d poly_market -f db_init.sql
--   或者在PostgreSQL客户端中直接执行
-- ============================================================

-- ============================================================
-- 1. rebound_orders 表 - 反弹策略订单记录
-- ============================================================

CREATE TABLE IF NOT EXISTS rebound_orders (
    id SERIAL PRIMARY KEY,
    
    -- 基本信息
    coin VARCHAR(10) NOT NULL,
    side VARCHAR(10) NOT NULL,
    segment VARCHAR(5) NOT NULL,
    
    -- 入场信息
    entry_price DECIMAL(10, 6) NOT NULL,
    entry_btc_price DECIMAL(15, 2),
    size DECIMAL(15, 4) NOT NULL DEFAULT 0,
    
    -- 触发条件
    trigger_up_price DECIMAL(10, 6),
    trigger_down_price DECIMAL(10, 6),
    trigger_up_drop DECIMAL(10, 6),
    trigger_down_drop DECIMAL(10, 6),
    btc_drop DECIMAL(15, 2),
    
    -- 时间信息
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    period_start TIMESTAMP,
    period_end TIMESTAMP,
    
    -- 出场信息
    exit_price DECIMAL(10, 6),
    exit_btc_price DECIMAL(15, 2),
    exit_at TIMESTAMP,
    
    -- 盈亏
    pnl DECIMAL(15, 4),
    pnl_percent DECIMAL(10, 4),
    
    -- 反弹趋势记录 (任务56)
    rebound_trend TEXT,
    
    -- 状态
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    is_simulated BOOLEAN NOT NULL DEFAULT TRUE,
    
    -- 市场信息
    market_slug VARCHAR(255),
    token_id VARCHAR(255),
    order_id VARCHAR(255),
    
    -- 策略类型和环境 (任务64)
    strategy_type VARCHAR(5),
    env VARCHAR(10)
);

-- rebound_orders 索引
CREATE INDEX IF NOT EXISTS idx_rebound_orders_coin ON rebound_orders(coin);
CREATE INDEX IF NOT EXISTS idx_rebound_orders_status ON rebound_orders(status);
CREATE INDEX IF NOT EXISTS idx_rebound_orders_created_at ON rebound_orders(created_at);
CREATE INDEX IF NOT EXISTS idx_rebound_orders_is_simulated ON rebound_orders(is_simulated);
CREATE INDEX IF NOT EXISTS idx_rebound_orders_strategy_type ON rebound_orders(strategy_type);
CREATE INDEX IF NOT EXISTS idx_rebound_orders_env ON rebound_orders(env);

-- ============================================================
-- 2. order_schedule 表 - 交易时段调度 (任务65)
-- ============================================================

CREATE TABLE IF NOT EXISTS order_schedule (
    id SERIAL PRIMARY KEY,
    create_dt TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    env VARCHAR(10) NOT NULL,
    strategy_type VARCHAR(5) NOT NULL,
    schedule_date DATE NOT NULL,
    start_time TIME NOT NULL,
    end_time TIME NOT NULL,
    status INTEGER NOT NULL DEFAULT 0
);

-- order_schedule 索引
CREATE INDEX IF NOT EXISTS idx_order_schedule_env ON order_schedule(env);
CREATE INDEX IF NOT EXISTS idx_order_schedule_strategy_type ON order_schedule(strategy_type);
CREATE INDEX IF NOT EXISTS idx_order_schedule_date ON order_schedule(schedule_date);
CREATE INDEX IF NOT EXISTS idx_order_schedule_status ON order_schedule(status);

-- ============================================================
-- 3. strategy3_rules 表 - 策略3动态规则 (任务60)
-- ============================================================

CREATE TABLE IF NOT EXISTS strategy3_rules (
    id SERIAL PRIMARY KEY,
    create_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_update_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status VARCHAR(20) NOT NULL DEFAULT 'inactive',
    env VARCHAR(20) NOT NULL DEFAULT 'simulate',
    stage_buy VARCHAR(5) NOT NULL DEFAULT 'A',
    price_down_percentage DECIMAL(5, 4) NOT NULL DEFAULT 0.25,
    price_down DECIMAL(10, 2) NOT NULL DEFAULT 50.0,
    take_profit DECIMAL(5, 4) NOT NULL DEFAULT 0.80,
    stop_loss DECIMAL(5, 4) NOT NULL DEFAULT 0.20
);

-- strategy3_rules 索引
CREATE INDEX IF NOT EXISTS idx_strategy3_rules_status ON strategy3_rules(status);
CREATE INDEX IF NOT EXISTS idx_strategy3_rules_env ON strategy3_rules(env);

-- ============================================================
-- 完成提示
-- ============================================================

DO $$
BEGIN
    RAISE NOTICE '✓ 数据库初始化完成！';
    RAISE NOTICE '  - rebound_orders 表已创建';
    RAISE NOTICE '  - order_schedule 表已创建';
    RAISE NOTICE '  - strategy3_rules 表已创建';
    RAISE NOTICE '  - 所有索引已创建';
    RAISE NOTICE '';
    RAISE NOTICE '现在可以启动trading bot了：';
    RAISE NOTICE '  python apps/run_rebound.py --coin BTC';
    RAISE NOTICE '  或者 run_rebound_live.bat';
END $$;
