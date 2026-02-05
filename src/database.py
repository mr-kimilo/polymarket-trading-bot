"""
Database Module - PostgreSQL Database Operations

Provides database connectivity and operations for the trading bot.
Supports order tracking and strategy performance analysis.

Environment Variables:
    DATABASE_HOST: Database host (default: 127.0.0.1)
    DATABASE_PORT: Database port (default: 5432)
    DATABASE_NAME: Database name (default: poly_market)
    DATABASE_USER: Database user
    DATABASE_PASSWORD: Database password

Example:
    from src.database import Database, ReboundOrder
    
    db = Database()
    
    # Create order record
    order = ReboundOrder(
        coin="BTC",
        side="up",
        segment="A",
        entry_price=0.45,
        entry_btc_price=95000.0,
        size=10.0
    )
    order_id = db.create_rebound_order(order)
    
    # Update order after 15min period ends
    db.update_rebound_order_result(order_id, exit_price=0.55, pnl=1.0)
"""

import os
import logging
from dataclasses import dataclass
from datetime import datetime, date, time
from typing import Optional, List, Dict, Any
from enum import Enum

# Try to import psycopg2
try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
    HAS_PSYCOPG2 = True
except ImportError:
    HAS_PSYCOPG2 = False

# Auto-load .env file
from dotenv import load_dotenv
load_dotenv()

logger = logging.getLogger(__name__)


class Segment(str, Enum):
    """15分钟周期内的时间段"""
    A = "A"  # 15-10分钟
    B = "B"  # 10-5分钟
    C = "C"  # 5-0分钟


class OrderStatus(str, Enum):
    """订单状态"""
    PENDING = "pending"      # 等待执行
    OPEN = "open"            # 已开仓
    CLOSED = "closed"        # 已平仓
    CANCELLED = "cancelled"  # 已取消
    SIMULATED = "simulated"  # 模拟订单


@dataclass
class ReboundOrder:
    """Rebound策略订单记录"""
    # 基本信息
    coin: str
    side: str  # "up" or "down"
    segment: str  # "A", "B", "C"
    
    # 入场信息
    entry_price: float
    entry_btc_price: Optional[float] = None
    size: float = 0.0
    
    # 触发条件
    trigger_up_price: Optional[float] = None
    trigger_down_price: Optional[float] = None
    trigger_up_drop: Optional[float] = None  # UP价格下跌幅度
    trigger_down_drop: Optional[float] = None  # DOWN价格下跌幅度
    btc_drop: Optional[float] = None  # BTC价格变化
    
    # 时间信息
    created_at: Optional[datetime] = None
    period_start: Optional[datetime] = None
    period_end: Optional[datetime] = None
    
    # 出场信息
    exit_price: Optional[float] = None
    exit_btc_price: Optional[float] = None
    exit_at: Optional[datetime] = None
    
    # 盈亏
    pnl: Optional[float] = None
    pnl_percent: Optional[float] = None
    
    # 状态
    status: str = OrderStatus.PENDING.value
    is_simulated: bool = True  # 默认是模拟订单
    
    # 数据库ID
    id: Optional[int] = None
    
    # 市场信息
    market_slug: Optional[str] = None
    token_id: Optional[str] = None
    order_id: Optional[str] = None  # Polymarket订单ID
    
    # Task 64: 策略类型和环境
    strategy_type: Optional[str] = None  # "1", "2", "3"
    env: Optional[str] = None  # "prod", "sim"


class DatabaseError(Exception):
    """Database operation error."""
    pass


class Database:
    """
    PostgreSQL数据库操作类
    
    用于管理交易订单的存储和查询
    """
    
    def __init__(self):
        """初始化数据库连接"""
        if not HAS_PSYCOPG2:
            logger.warning("psycopg2 not installed. Database features disabled.")
            self._conn = None
            return
            
        self._host = os.environ.get("DATABASE_HOST", "127.0.0.1")
        self._port = int(os.environ.get("DATABASE_PORT", "5432"))
        self._name = os.environ.get("DATABASE_NAME", "poly_market")
        self._user = os.environ.get("DATABASE_USER", "")
        self._password = os.environ.get("DATABASE_PASSWORD", "")
        
        self._conn = None
        self._connect()
        
    def _connect(self) -> None:
        """建立数据库连接"""
        if not HAS_PSYCOPG2:
            return
            
        if not self._user or not self._password:
            logger.warning("Database credentials not configured. Database features disabled.")
            return
            
        try:
            self._conn = psycopg2.connect(
                host=self._host,
                port=self._port,
                dbname=self._name,
                user=self._user,
                password=self._password
            )
            self._conn.autocommit = True
            logger.info(f"Connected to database {self._name}@{self._host}:{self._port}")
            
            # 确保表存在
            self._ensure_tables()
            
        except Exception as e:
            logger.error(f"Failed to connect to database: {e}")
            self._conn = None
    
    def _ensure_tables(self) -> None:
        """确保必要的表存在"""
        if not self._conn:
            return
        
        # 首先检查表是否存在以及结构是否正确
        check_table_sql = """
        SELECT column_name FROM information_schema.columns 
        WHERE table_name = 'rebound_orders' AND column_name = 'coin';
        """
        
        try:
            with self._conn.cursor() as cur:
                cur.execute(check_table_sql)
                result = cur.fetchone()
                
                # 如果表存在但没有coin列，先删除旧表
                if result is None:
                    # 检查表是否存在
                    cur.execute("""
                        SELECT EXISTS (
                            SELECT FROM information_schema.tables 
                            WHERE table_name = 'rebound_orders'
                        );
                    """)
                    table_exists = cur.fetchone()[0]
                    if table_exists:
                        logger.warning("Table rebound_orders exists but has wrong schema. Dropping and recreating...")
                        cur.execute("DROP TABLE IF EXISTS rebound_orders CASCADE;")
        except Exception as e:
            logger.warning(f"Error checking table schema: {e}")
            
        create_table_sql = """
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
            
            -- Task 64: 策略类型和环境
            strategy_type VARCHAR(5),
            env VARCHAR(10)
        );
        """
        
        # 索引创建语句（在添加缺失列后执行）
        create_indexes_sql = """
        CREATE INDEX IF NOT EXISTS idx_rebound_orders_coin ON rebound_orders(coin);
        CREATE INDEX IF NOT EXISTS idx_rebound_orders_status ON rebound_orders(status);
        CREATE INDEX IF NOT EXISTS idx_rebound_orders_created_at ON rebound_orders(created_at);
        CREATE INDEX IF NOT EXISTS idx_rebound_orders_is_simulated ON rebound_orders(is_simulated);
        CREATE INDEX IF NOT EXISTS idx_rebound_orders_strategy_type ON rebound_orders(strategy_type);
        CREATE INDEX IF NOT EXISTS idx_rebound_orders_env ON rebound_orders(env);
        """
        
        try:
            with self._conn.cursor() as cur:
                cur.execute(create_table_sql)
            logger.info("Database table created")
            
            # 添加缺失的列（用于现有表的迁移）- 必须在索引创建前执行
            self.add_missing_columns()
            
            # 创建索引（在列存在后）
            with self._conn.cursor() as cur:
                cur.execute(create_indexes_sql)
            logger.info("Database indexes ensured")
            
            # 确保order_schedule表存在 (任务65)
            self.ensure_order_schedule_table()
            logger.info("Database initialization complete")
        except Exception as e:
            logger.error(f"Failed to create tables: {e}")
    
    @property
    def is_connected(self) -> bool:
        """检查数据库是否连接"""
        return self._conn is not None
    
    def close(self) -> None:
        """关闭数据库连接"""
        if self._conn:
            self._conn.close()
            self._conn = None
            logger.info("Database connection closed")
    
    def create_rebound_order(self, order: ReboundOrder) -> Optional[int]:
        """
        创建Rebound订单记录
        
        Args:
            order: ReboundOrder对象
            
        Returns:
            订单ID，如果失败返回None
        """
        if not self._conn:
            logger.warning("Database not connected. Order not saved.")
            return None
            
        insert_sql = """
        INSERT INTO rebound_orders (
            coin, side, segment,
            entry_price, entry_btc_price, size,
            trigger_up_price, trigger_down_price, trigger_up_drop, trigger_down_drop, btc_drop,
            period_start, period_end,
            status, is_simulated,
            market_slug, token_id, order_id,
            strategy_type, env
        ) VALUES (
            %s, %s, %s,
            %s, %s, %s,
            %s, %s, %s, %s, %s,
            %s, %s,
            %s, %s,
            %s, %s, %s,
            %s, %s
        ) RETURNING id;
        """
        
        try:
            with self._conn.cursor() as cur:
                cur.execute(insert_sql, (
                    order.coin, order.side, order.segment,
                    order.entry_price, order.entry_btc_price, order.size,
                    order.trigger_up_price, order.trigger_down_price, 
                    order.trigger_up_drop, order.trigger_down_drop, order.btc_drop,
                    order.period_start, order.period_end,
                    order.status, order.is_simulated,
                    order.market_slug, order.token_id, order.order_id,
                    order.strategy_type, order.env
                ))
                result = cur.fetchone()
                order_id = result[0] if result else None
                logger.info(f"Created rebound order: {order_id} (simulated={order.is_simulated}, strategy={order.strategy_type}, env={order.env})")
                return order_id
        except Exception as e:
            logger.error(f"Failed to create rebound order: {e}")
            return None
    
    def update_rebound_order_result(
        self,
        order_id: int,
        exit_price: float,
        exit_btc_price: Optional[float] = None,
        pnl: Optional[float] = None,
        pnl_percent: Optional[float] = None,
        status: str = OrderStatus.CLOSED.value,
        rebound_trend: Optional[str] = None
    ) -> bool:
        """
        更新Rebound订单的结果
        
        Args:
            order_id: 订单ID
            exit_price: 出场价格
            exit_btc_price: 出场时BTC价格
            pnl: 盈亏金额
            pnl_percent: 盈亏百分比
            status: 订单状态
            rebound_trend: 反弹趋势记录 (逗号分隔的百分比字符串)
            
        Returns:
            是否更新成功
        """
        if not self._conn:
            logger.warning("Database not connected. Order not updated.")
            return False
            
        update_sql = """
        UPDATE rebound_orders
        SET exit_price = %s,
            exit_btc_price = %s,
            exit_at = CURRENT_TIMESTAMP,
            pnl = %s,
            pnl_percent = %s,
            status = %s,
            rebound_trend = %s
        WHERE id = %s;
        """
        
        try:
            with self._conn.cursor() as cur:
                cur.execute(update_sql, (
                    exit_price, exit_btc_price, pnl, pnl_percent, status, rebound_trend, order_id
                ))
                logger.info(f"Updated rebound order {order_id}: pnl={pnl}, status={status}")
                return True
        except Exception as e:
            logger.error(f"Failed to update rebound order: {e}")
            return False
    
    def update_rebound_trend_only(
        self,
        order_id: int,
        rebound_trend: str
    ) -> bool:
        """
        仅更新Rebound订单的反弹趋势记录 (任务56补充)
        
        用于在15分钟周期结束时更新趋势记录，即使订单已提前关闭。
        这样可以记录从开单到15分钟结束的完整趋势，而不是订单关闭时的趋势。
        
        Args:
            order_id: 订单ID
            rebound_trend: 反弹趋势记录 (逗号分隔的百分比字符串)
            
        Returns:
            是否更新成功
        """
        if not self._conn:
            logger.warning("Database not connected. Trend not updated.")
            return False
            
        update_sql = """
        UPDATE rebound_orders
        SET rebound_trend = %s
        WHERE id = %s;
        """
        
        try:
            with self._conn.cursor() as cur:
                cur.execute(update_sql, (rebound_trend, order_id))
                logger.info(f"Updated rebound trend for order {order_id}")
                return True
        except Exception as e:
            logger.error(f"Failed to update rebound trend: {e}")
            return False
    
    def get_rebound_order(self, order_id: int) -> Optional[ReboundOrder]:
        """
        获取单个订单
        
        Args:
            order_id: 订单ID
            
        Returns:
            ReboundOrder对象，如果不存在返回None
        """
        if not self._conn:
            return None
            
        select_sql = "SELECT * FROM rebound_orders WHERE id = %s;"
        
        try:
            with self._conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(select_sql, (order_id,))
                row = cur.fetchone()
                if row:
                    return self._row_to_order(row)
                return None
        except Exception as e:
            logger.error(f"Failed to get rebound order: {e}")
            return None
    
    def get_open_rebound_orders(self, coin: Optional[str] = None) -> List[ReboundOrder]:
        """
        获取所有未平仓的订单
        
        Args:
            coin: 可选，筛选特定币种
            
        Returns:
            ReboundOrder列表
        """
        if not self._conn:
            return []
            
        if coin:
            select_sql = """
            SELECT * FROM rebound_orders 
            WHERE status IN ('pending', 'open') AND coin = %s
            ORDER BY created_at DESC;
            """
            params = (coin,)
        else:
            select_sql = """
            SELECT * FROM rebound_orders 
            WHERE status IN ('pending', 'open')
            ORDER BY created_at DESC;
            """
            params = None
        
        try:
            with self._conn.cursor(cursor_factory=RealDictCursor) as cur:
                if params:
                    cur.execute(select_sql, params)
                else:
                    cur.execute(select_sql)
                rows = cur.fetchall()
                return [self._row_to_order(row) for row in rows]
        except Exception as e:
            logger.error(f"Failed to get open rebound orders: {e}")
            return []
    
    def get_rebound_orders_stats(
        self, 
        coin: Optional[str] = None,
        is_simulated: Optional[bool] = None,
        days: int = 30
    ) -> Dict[str, Any]:
        """
        获取订单统计信息
        
        Args:
            coin: 可选，筛选特定币种
            is_simulated: 可选，筛选模拟/真实订单
            days: 统计最近多少天
            
        Returns:
            统计信息字典
        """
        if not self._conn:
            return {}
            
        # 构建查询条件
        conditions: List[str] = ["created_at >= CURRENT_DATE - INTERVAL '%s days'"]
        params: List[Any] = [days]
        
        if coin:
            conditions.append("coin = %s")
            params.append(coin)
        if is_simulated is not None:
            conditions.append("is_simulated = %s")
            params.append(is_simulated)
            
        where_clause = " AND ".join(conditions)
        
        stats_sql = f"""
        SELECT 
            COUNT(*) as total_orders,
            COUNT(CASE WHEN status = 'closed' THEN 1 END) as closed_orders,
            COUNT(CASE WHEN status = 'closed' AND pnl > 0 THEN 1 END) as winning_orders,
            COUNT(CASE WHEN status = 'closed' AND pnl <= 0 THEN 1 END) as losing_orders,
            COALESCE(SUM(CASE WHEN status = 'closed' THEN pnl END), 0) as total_pnl,
            COALESCE(AVG(CASE WHEN status = 'closed' THEN pnl END), 0) as avg_pnl,
            COALESCE(MAX(CASE WHEN status = 'closed' THEN pnl END), 0) as max_pnl,
            COALESCE(MIN(CASE WHEN status = 'closed' THEN pnl END), 0) as min_pnl
        FROM rebound_orders
        WHERE {where_clause};
        """
        
        try:
            with self._conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(stats_sql, params)
                row = cur.fetchone()
                if row:
                    stats = dict(row)
                    # 计算胜率
                    closed = stats.get('closed_orders', 0)
                    winning = stats.get('winning_orders', 0)
                    stats['win_rate'] = (winning / closed * 100) if closed > 0 else 0
                    return stats
                return {}
        except Exception as e:
            logger.error(f"Failed to get rebound orders stats: {e}")
            return {}
    
    def _row_to_order(self, row: Dict[str, Any]) -> ReboundOrder:
        """将数据库行转换为ReboundOrder对象"""
        return ReboundOrder(
            id=row.get('id'),
            coin=row.get('coin', ''),
            side=row.get('side', ''),
            segment=row.get('segment', ''),
            entry_price=float(row.get('entry_price', 0)),
            entry_btc_price=float(row['entry_btc_price']) if row.get('entry_btc_price') else None,
            size=float(row.get('size', 0)),
            trigger_up_price=float(row['trigger_up_price']) if row.get('trigger_up_price') else None,
            trigger_down_price=float(row['trigger_down_price']) if row.get('trigger_down_price') else None,
            trigger_up_drop=float(row['trigger_up_drop']) if row.get('trigger_up_drop') else None,
            trigger_down_drop=float(row['trigger_down_drop']) if row.get('trigger_down_drop') else None,
            btc_drop=float(row['btc_drop']) if row.get('btc_drop') else None,
            created_at=row.get('created_at'),
            period_start=row.get('period_start'),
            period_end=row.get('period_end'),
            exit_price=float(row['exit_price']) if row.get('exit_price') else None,
            exit_btc_price=float(row['exit_btc_price']) if row.get('exit_btc_price') else None,
            exit_at=row.get('exit_at'),
            pnl=float(row['pnl']) if row.get('pnl') else None,
            pnl_percent=float(row['pnl_percent']) if row.get('pnl_percent') else None,
            status=row.get('status', OrderStatus.PENDING.value),
            is_simulated=row.get('is_simulated', True),
            market_slug=row.get('market_slug'),
            token_id=row.get('token_id'),
            order_id=row.get('order_id'),
            strategy_type=row.get('strategy_type'),
            env=row.get('env')
        )
    
    # ==================== Strategy3 Rules (任务60) ====================
    
    def ensure_strategy3_rules_table(self) -> None:
        """确保strategy3_rules表存在 (任务60)"""
        if not self._conn:
            return
        
        create_table_sql = """
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
        
        CREATE INDEX IF NOT EXISTS idx_strategy3_rules_status ON strategy3_rules(status);
        CREATE INDEX IF NOT EXISTS idx_strategy3_rules_env ON strategy3_rules(env);
        """
        
        try:
            with self._conn.cursor() as cur:
                cur.execute(create_table_sql)
            logger.info("strategy3_rules table ensured")
        except Exception as e:
            logger.error(f"Failed to create strategy3_rules table: {e}")
    
    def create_strategy3_rule(
        self,
        env: str = "simulate",
        stage_buy: str = "A",
        price_down_percentage: float = 0.25,
        price_down: float = 50.0,
        take_profit: float = 0.80,
        stop_loss: float = 0.20
    ) -> Optional[int]:
        """
        创建策略3规则 (任务60)
        
        Args:
            env: 环境 ("production" 或 "simulate")
            stage_buy: 买入阶段 ("A", "B", "C")
            price_down_percentage: 价格下跌百分比阈值
            price_down: BTC价格下跌阈值
            take_profit: 止盈比例
            stop_loss: 止损比例
            
        Returns:
            规则ID
        """
        if not self._conn:
            return None
        
        # 确保表存在
        self.ensure_strategy3_rules_table()
        
        insert_sql = """
        INSERT INTO strategy3_rules (
            env, stage_buy, price_down_percentage, price_down, take_profit, stop_loss
        ) VALUES (%s, %s, %s, %s, %s, %s)
        RETURNING id;
        """
        
        try:
            with self._conn.cursor() as cur:
                cur.execute(insert_sql, (
                    env, stage_buy, price_down_percentage, price_down, take_profit, stop_loss
                ))
                result = cur.fetchone()
                rule_id = result[0] if result else None
                logger.info(f"Created strategy3 rule: {rule_id}")
                return rule_id
        except Exception as e:
            logger.error(f"Failed to create strategy3 rule: {e}")
            return None
    
    def activate_strategy3_rule(self, rule_id: int) -> bool:
        """
        激活策略3规则 (任务60)
        
        会先将同环境的其他规则设为inactive
        
        Args:
            rule_id: 规则ID
            
        Returns:
            是否成功
        """
        if not self._conn:
            return False
        
        try:
            with self._conn.cursor(cursor_factory=RealDictCursor) as cur:
                # 获取要激活的规则的环境
                cur.execute("SELECT env FROM strategy3_rules WHERE id = %s", (rule_id,))
                result = cur.fetchone()
                if not result:
                    logger.warning(f"Rule {rule_id} not found")
                    return False
                
                env = result['env']
                
                # 将同环境的其他规则设为inactive
                cur.execute(
                    "UPDATE strategy3_rules SET status = 'inactive', last_update_date = CURRENT_TIMESTAMP WHERE env = %s AND status = 'active'",
                    (env,)
                )
                
                # 激活指定规则
                cur.execute(
                    "UPDATE strategy3_rules SET status = 'active', last_update_date = CURRENT_TIMESTAMP WHERE id = %s",
                    (rule_id,)
                )
                
                logger.info(f"Activated strategy3 rule: {rule_id}")
                return True
        except Exception as e:
            logger.error(f"Failed to activate strategy3 rule: {e}")
            return False
    
    def get_active_strategy3_rule(self, env: str = "simulate") -> Optional[Dict]:
        """
        获取当前激活的策略3规则 (任务60)
        
        Args:
            env: 环境 ("production" 或 "simulate")
            
        Returns:
            规则参数字典，如果没有激活的规则返回None
        """
        if not self._conn:
            return None
        
        # 确保表存在
        self.ensure_strategy3_rules_table()
        
        select_sql = """
        SELECT id, stage_buy, price_down_percentage, price_down, take_profit, stop_loss,
               create_date, last_update_date
        FROM strategy3_rules
        WHERE status = 'active' AND env = %s
        ORDER BY last_update_date DESC
        LIMIT 1;
        """
        
        try:
            with self._conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(select_sql, (env,))
                row = cur.fetchone()
                if row:
                    return {
                        "id": row['id'],
                        "stage_buy": row['stage_buy'],
                        "price_down_percentage": float(row['price_down_percentage']),
                        "price_down": float(row['price_down']),
                        "take_profit": float(row['take_profit']),
                        "stop_loss": float(row['stop_loss']),
                        "create_date": row['create_date'],
                        "last_update_date": row['last_update_date']
                    }
                return None
        except Exception as e:
            logger.error(f"Failed to get active strategy3 rule: {e}")
            return None
    
    def query_strategy3_rules(
        self,
        rule_ids: Optional[List[int]] = None,
        create_date_from: Optional[datetime] = None,
        env: Optional[str] = None
    ) -> List[Dict]:
        """
        查询策略3规则 (任务60)
        
        Args:
            rule_ids: 规则ID列表（可选）
            create_date_from: 创建日期起始（可选）
            env: 环境筛选（可选）
            
        Returns:
            规则列表
        """
        if not self._conn:
            return []
        
        # 确保表存在
        self.ensure_strategy3_rules_table()
        
        conditions = []
        params = []
        
        if rule_ids:
            conditions.append("id = ANY(%s)")
            params.append(rule_ids)
        
        if create_date_from:
            conditions.append("create_date >= %s")
            params.append(create_date_from)
        
        if env:
            conditions.append("env = %s")
            params.append(env)
        
        where_clause = " AND ".join(conditions) if conditions else "1=1"
        
        select_sql = f"""
        SELECT id, status, env, stage_buy, price_down_percentage, price_down, 
               take_profit, stop_loss, create_date, last_update_date
        FROM strategy3_rules
        WHERE {where_clause}
        ORDER BY create_date DESC;
        """
        
        try:
            with self._conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(select_sql, params)
                rows = cur.fetchall()
                return [
                    {
                        "id": row['id'],
                        "status": row['status'],
                        "env": row['env'],
                        "stage_buy": row['stage_buy'],
                        "price_down_percentage": float(row['price_down_percentage']),
                        "price_down": float(row['price_down']),
                        "take_profit": float(row['take_profit']),
                        "stop_loss": float(row['stop_loss']),
                        "create_date": row['create_date'].isoformat() if row['create_date'] else None,
                        "last_update_date": row['last_update_date'].isoformat() if row['last_update_date'] else None
                    }
                    for row in rows
                ]
        except Exception as e:
            logger.error(f"Failed to query strategy3 rules: {e}")
            return []

    # ==================== Order Schedule (任务65) ====================

    def ensure_order_schedule_table(self) -> None:
        """确保order_schedule表存在 (任务65 + 任务65补充)"""
        if not self._conn:
            return
        
        create_table_sql = """
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
        
        CREATE INDEX IF NOT EXISTS idx_order_schedule_env ON order_schedule(env);
        CREATE INDEX IF NOT EXISTS idx_order_schedule_strategy_type ON order_schedule(strategy_type);
        CREATE INDEX IF NOT EXISTS idx_order_schedule_date ON order_schedule(schedule_date);
        CREATE INDEX IF NOT EXISTS idx_order_schedule_status ON order_schedule(status);
        """
        
        try:
            with self._conn.cursor() as cur:
                cur.execute(create_table_sql)
            logger.info("order_schedule table ensured")
        except Exception as e:
            logger.error(f"Failed to create order_schedule table: {e}")
    
    def migrate_order_schedule_table(self) -> None:
        """迁移order_schedule表，将time_period拆分为start_time和end_time (任务65补充)"""
        if not self._conn:
            return
        
        try:
            with self._conn.cursor() as cur:
                # 检查是否存在旧的time_period列
                cur.execute("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name = 'order_schedule' AND column_name = 'time_period';
                """)
                has_time_period = cur.fetchone() is not None
                
                if has_time_period:
                    logger.info("Migrating order_schedule table: splitting time_period into start_time and end_time")
                    
                    # 添加新列
                    cur.execute("ALTER TABLE order_schedule ADD COLUMN IF NOT EXISTS start_time TIME;")
                    cur.execute("ALTER TABLE order_schedule ADD COLUMN IF NOT EXISTS end_time TIME;")
                    
                    # 迁移数据：将time_period (如 "09:00-10:00") 拆分为start_time和end_time
                    cur.execute("""
                        UPDATE order_schedule
                        SET start_time = split_part(time_period, '-', 1)::TIME,
                            end_time = split_part(time_period, '-', 2)::TIME
                        WHERE start_time IS NULL AND end_time IS NULL AND time_period IS NOT NULL;
                    """)
                    
                    # 删除旧列
                    cur.execute("ALTER TABLE order_schedule DROP COLUMN IF EXISTS time_period;")
                    
                    # 设置新列为NOT NULL（如果数据已迁移）
                    cur.execute("ALTER TABLE order_schedule ALTER COLUMN start_time SET NOT NULL;")
                    cur.execute("ALTER TABLE order_schedule ALTER COLUMN end_time SET NOT NULL;")
                    
                    logger.info("order_schedule table migration completed")
        except Exception as e:
            logger.error(f"Failed to migrate order_schedule table: {e}")

    def create_order_schedule(
        self,
        env: str,
        strategy_type: str,
        schedule_date: date,
        start_time: time,
        end_time: time,
        status: int = 0
    ) -> Optional[int]:
        """
        创建订单计划 (任务65 + 任务65补充)
        
        Args:
            env: 环境 ("prod" 或 "sim")
            strategy_type: 策略类型 ("1", "2", "3")
            schedule_date: 计划日期
            start_time: 开始时间
            end_time: 结束时间
            status: 状态 (0=plan, 1=running, 2=completed, 3=canceled)
            
        Returns:
            计划ID
        """
        if not self._conn:
            return None
        
        # 确保表存在并执行迁移
        self.ensure_order_schedule_table()
        self.migrate_order_schedule_table()
        
        insert_sql = """
        INSERT INTO order_schedule (env, strategy_type, schedule_date, start_time, end_time, status)
        VALUES (%s, %s, %s, %s, %s, %s)
        RETURNING id;
        """
        
        try:
            with self._conn.cursor() as cur:
                cur.execute(insert_sql, (env, strategy_type, schedule_date, start_time, end_time, status))
                result = cur.fetchone()
                schedule_id = result[0] if result else None
                logger.info(f"Created order schedule: {schedule_id} ({start_time}-{end_time})")
                return schedule_id
        except Exception as e:
            logger.error(f"Failed to create order schedule: {e}")
            return None

    def get_order_schedule(self, schedule_id: int) -> Optional[Dict]:
        """
        获取订单计划详情 (任务65)
        
        Args:
            schedule_id: 计划ID
            
        Returns:
            计划详情字典
        """
        if not self._conn:
            return None
        
        select_sql = """
        SELECT id, create_dt, env, strategy_type, schedule_date, start_time, end_time, status
        FROM order_schedule
        WHERE id = %s;
        """
        
        try:
            with self._conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(select_sql, (schedule_id,))
                row = cur.fetchone()
                if row:
                    return {
                        "id": row['id'],
                        "create_dt": row['create_dt'].isoformat() if row['create_dt'] else None,
                        "env": row['env'],
                        "strategy_type": row['strategy_type'],
                        "schedule_date": row['schedule_date'].isoformat() if row['schedule_date'] else None,
                        "start_time": str(row['start_time']) if row['start_time'] else None,
                        "end_time": str(row['end_time']) if row['end_time'] else None,
                        "status": row['status']
                    }
                return None
        except Exception as e:
            logger.error(f"Failed to get order schedule: {e}")
            return None

    def cancel_order_schedule(self, schedule_id: int) -> bool:
        """
        取消订单计划 (任务65)
        
        Args:
            schedule_id: 计划ID
            
        Returns:
            是否成功
        """
        if not self._conn:
            return False
        
        update_sql = """
        UPDATE order_schedule
        SET status = 3
        WHERE id = %s AND status = 0;
        """
        
        try:
            with self._conn.cursor() as cur:
                cur.execute(update_sql, (schedule_id,))
                # Check if any row was actually updated
                if cur.rowcount > 0:
                    logger.info(f"Canceled order schedule: {schedule_id}")
                    return True
                else:
                    logger.warning(f"Order schedule {schedule_id} not found or already processed")
                    return False
        except Exception as e:
            logger.error(f"Failed to cancel order schedule: {e}")
            return False

    def check_should_trade(self, env: str, strategy_type: str) -> bool:
        """
        检查当前时间是否应该交易 (任务65 + 任务65补充)
        
        根据order_schedule表检查当前时间是否在计划的交易时间段内
        
        Args:
            env: 环境 ("prod" 或 "sim")
            strategy_type: 策略类型 ("1", "2", "3")
            
        Returns:
            是否应该交易
        """
        if not self._conn:
            return False
        
        # 确保表存在并执行迁移
        self.ensure_order_schedule_table()
        self.migrate_order_schedule_table()
        
        # 查询今天状态为plan(0)的计划
        select_sql = """
        SELECT start_time, end_time
        FROM order_schedule
        WHERE env = %s 
          AND strategy_type = %s 
          AND schedule_date = CURRENT_DATE
          AND status = 0;
        """
        
        try:
            with self._conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(select_sql, (env, strategy_type))
                rows = cur.fetchall()
                
                if not rows:
                    return False
                
                # 获取当前时间
                now = datetime.now()
                current_time = now.time()
                
                # 检查是否在任何计划的时间段内
                for row in rows:
                    start_time = row['start_time']
                    end_time = row['end_time']
                    
                    # 比较时间对象
                    if start_time <= current_time <= end_time:
                        return True
                
                return False
        except Exception as e:
            logger.error(f"Failed to check should trade: {e}")
            return False

    def query_order_schedules(
        self,
        env: Optional[str] = None,
        strategy_type: Optional[str] = None,
        schedule_date: Optional[date] = None,
        status: Optional[int] = None
    ) -> List[Dict]:
        """
        查询订单计划 (任务65)
        
        Args:
            env: 环境筛选
            strategy_type: 策略类型筛选
            schedule_date: 日期筛选
            status: 状态筛选
            
        Returns:
            计划列表
        """
        if not self._conn:
            return []
        
        # 确保表存在
        self.ensure_order_schedule_table()
        
        conditions = []
        params = []
        
        if env:
            conditions.append("env = %s")
            params.append(env)
        
        if strategy_type:
            conditions.append("strategy_type = %s")
            params.append(strategy_type)
        
        if schedule_date:
            conditions.append("schedule_date = %s")
            params.append(schedule_date)
        
        if status is not None:
            conditions.append("status = %s")
            params.append(status)
        
        where_clause = " AND ".join(conditions) if conditions else "1=1"
        
        # 确保迁移已完成
        self.migrate_order_schedule_table()
        
        select_sql = f"""
        SELECT id, create_dt, env, strategy_type, schedule_date, start_time, end_time, status
        FROM order_schedule
        WHERE {where_clause}
        ORDER BY schedule_date DESC, create_dt DESC;
        """
        
        try:
            with self._conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(select_sql, params)
                rows = cur.fetchall()
                return [
                    {
                        "id": row['id'],
                        "create_dt": row['create_dt'].isoformat() if row['create_dt'] else None,
                        "env": row['env'],
                        "strategy_type": row['strategy_type'],
                        "schedule_date": row['schedule_date'].isoformat() if row['schedule_date'] else None,
                        "start_time": row['start_time'].strftime("%H:%M:%S") if row['start_time'] else None,
                        "end_time": row['end_time'].strftime("%H:%M:%S") if row['end_time'] else None,
                        "status": row['status']
                    }
                    for row in rows
                ]
        except Exception as e:
            logger.error(f"Failed to query order schedules: {e}")
            return []

    def add_missing_columns(self) -> None:
        """
        添加缺失的列到现有表 (任务64迁移)
        
        用于将新字段添加到已存在的表中
        """
        if not self._conn:
            return
        
        alter_statements = [
            "ALTER TABLE rebound_orders ADD COLUMN IF NOT EXISTS strategy_type VARCHAR(5);",
            "ALTER TABLE rebound_orders ADD COLUMN IF NOT EXISTS env VARCHAR(10);",
        ]
        
        try:
            with self._conn.cursor() as cur:
                for stmt in alter_statements:
                    try:
                        cur.execute(stmt)
                    except Exception as e:
                        # Column might already exist, ignore error
                        logger.debug(f"Column might exist: {e}")
                
                # Create indexes if not exist
                try:
                    cur.execute("CREATE INDEX IF NOT EXISTS idx_rebound_orders_strategy_type ON rebound_orders(strategy_type);")
                    cur.execute("CREATE INDEX IF NOT EXISTS idx_rebound_orders_env ON rebound_orders(env);")
                except Exception as e:
                    logger.debug(f"Index might exist: {e}")
            
            logger.info("Added missing columns to rebound_orders table")
        except Exception as e:
            logger.error(f"Failed to add missing columns: {e}")


# 全局数据库实例（懒加载）
_db_instance: Optional[Database] = None


def get_database() -> Database:
    """获取数据库单例实例"""
    global _db_instance
    if _db_instance is None:
        _db_instance = Database()
    return _db_instance
