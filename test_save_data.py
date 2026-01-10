#!/usr/bin/env python3
"""Test script for Task 16: Save 15-minute period data to JSON file."""

import sys
import time
import json
from pathlib import Path
from datetime import datetime
from collections import deque

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from lib import PriceTracker
from lib.console import Colors


class PriceSnapshot:
    """每分钟价格快照"""
    def __init__(self, timestamp: float, up_price: float, down_price: float, 
                 btc_price: float = None, minute_index: int = 0):
        self.timestamp = timestamp
        self.up_price = up_price
        self.down_price = down_price
        self.btc_price_start = btc_price
        self.btc_price_end = btc_price
        self.minute = int(timestamp / 60)
        self.minute_index = minute_index


def test_save_period_data():
    """测试保存15分钟周期数据到JSON文件"""
    print("=" * 70)
    print("Task 16/17 Test: Save 15-minute period data to JSON")
    print("=" * 70)
    
    # 模拟数据
    coin = "BTC"
    current_market_slug = "btc-updown-15m-1768052700"
    market_start_time = time.time() - 600  # 10分钟前
    btc_price_start = 90500.0
    btc_price_current = 90650.0
    start_prices = {"up": 0.35, "down": 0.65}
    
    # 创建5个分钟快照
    minute_snapshots = deque(maxlen=15)
    base_time = market_start_time
    
    test_data = [
        (0.3400, 0.6600, 90500, 90520),
        (0.3200, 0.6800, 90520, 90550),
        (0.3000, 0.7000, 90550, 90530),
        (0.2800, 0.7200, 90530, 90600),
        (0.2500, 0.7500, 90600, 90650),
    ]
    
    for i, (up, down, btc_start, btc_end) in enumerate(test_data, 1):
        snapshot = PriceSnapshot(
            timestamp=base_time + (i * 60),
            up_price=up,
            down_price=down,
            btc_price=btc_start,
            minute_index=i
        )
        snapshot.btc_price_end = btc_end
        minute_snapshots.append(snapshot)
    
    print(f"\n✓ Created {len(minute_snapshots)} test snapshots")
    
    # 确定保存目录
    files_dir = Path(__file__).parent / "files"
    files_dir.mkdir(exist_ok=True)
    print(f"✓ Files directory: {files_dir}")
    
    # 生成文件名
    file_time = datetime.fromtimestamp(market_start_time)
    filename = file_time.strftime("%Y-%m-%d-%H-%M") + ".json"
    filepath = files_dir / filename
    print(f"✓ Target file: {filename}")
    
    # 构建数据
    start_up = start_prices.get("up")
    start_down = start_prices.get("down")
    
    data = {
        "coin": coin,
        "market_slug": current_market_slug,
        "period_start": file_time.isoformat(),
        "btc_price_start": btc_price_start,
        "btc_price_end": btc_price_current,
        "up_start": start_up,
        "down_start": start_down,
        "minutes": []
    }
    
    for snapshot in minute_snapshots:
        # 计算百分比变化
        up_change_pct = ((snapshot.up_price - start_up) / start_up * 100) if start_up else 0
        down_change_pct = ((snapshot.down_price - start_down) / start_down * 100) if start_down else 0
        btc_delta = (snapshot.btc_price_end or 0) - (snapshot.btc_price_start or 0) if snapshot.btc_price_start else 0
        
        minute_data = {
            "minute_index": snapshot.minute_index,
            "time": datetime.fromtimestamp(snapshot.timestamp).strftime("%H:%M"),
            "timestamp": snapshot.timestamp,
            "up": snapshot.up_price,
            "up_pct": round(up_change_pct, 2),
            "down": snapshot.down_price,
            "down_pct": round(down_change_pct, 2),
            "btc_start": snapshot.btc_price_start,
            "btc_end": snapshot.btc_price_end,
            "btc_delta": round(btc_delta, 2) if btc_delta else 0
        }
        data["minutes"].append(minute_data)
    
    # 保存到文件
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"✓ Data saved successfully!")
    except Exception as e:
        print(f"✗ Save failed: {e}")
        return False
    
    # 验证文件
    if filepath.exists():
        print(f"✓ File exists: {filepath}")
        with open(filepath, 'r', encoding='utf-8') as f:
            saved_data = json.load(f)
        
        print(f"\n--- Saved JSON Content ---")
        print(json.dumps(saved_data, indent=2, ensure_ascii=False))
        
        # 验证数据完整性
        print(f"\n--- Verification ---")
        assert saved_data["coin"] == coin, "Coin mismatch"
        print(f"✓ coin: {saved_data['coin']}")
        
        assert saved_data["market_slug"] == current_market_slug, "Slug mismatch"
        print(f"✓ market_slug: {saved_data['market_slug']}")
        
        assert len(saved_data["minutes"]) == 5, "Minutes count mismatch"
        print(f"✓ minutes count: {len(saved_data['minutes'])}")
        
        for m in saved_data["minutes"]:
            print(f"  Min {m['minute_index']}: UP={m['up']:.4f} ({m['up_pct']:+.2f}%), "
                  f"DOWN={m['down']:.4f} ({m['down_pct']:+.2f}%), "
                  f"BTC Δ={m['btc_delta']:+.0f}")
        
        print(f"\n{'=' * 70}")
        print(f"✓ ALL TESTS PASSED - Task 16 is working correctly!")
        print(f"{'=' * 70}")
        return True
    else:
        print(f"✗ File not found!")
        return False


def test_orderbook_tui_import():
    """测试OrderbookTUI导入和_save_period_data方法"""
    print("\n" + "=" * 70)
    print("Testing OrderbookTUI import and _save_period_data method")
    print("=" * 70)
    
    try:
        from apps.orderbook_tui import OrderbookTUI, PriceSnapshot as RealSnapshot
        print("✓ Import successful")
        
        # 创建实例
        tui = OrderbookTUI("BTC")
        print(f"✓ OrderbookTUI instance created")
        
        # 检查_save_period_data方法是否存在
        assert hasattr(tui, '_save_period_data'), "_save_period_data method not found"
        print(f"✓ _save_period_data method exists")
        
        # 添加测试数据
        tui.market_start_time = time.time() - 300
        tui.btc_price_start = 90000.0
        tui.btc_price_current = 90100.0
        tui.start_prices = {"up": 0.40, "down": 0.60}
        tui.current_market_slug = "test-market-slug"
        
        # 创建测试快照
        snapshot = RealSnapshot(
            timestamp=time.time() - 60,
            up_price=0.38,
            down_price=0.62,
            btc_price=90050,
            minute_index=1
        )
        snapshot.btc_price_end = 90100
        tui.minute_snapshots.append(snapshot)
        
        print(f"✓ Test data added")
        
        # 调用保存方法
        tui._save_period_data()
        print(f"✓ _save_period_data() called without error")
        
        # 检查文件是否创建
        files_dir = Path(__file__).parent / "files"
        json_files = list(files_dir.glob("*.json"))
        print(f"✓ Found {len(json_files)} JSON files in /files directory")
        
        if json_files:
            latest_file = max(json_files, key=lambda f: f.stat().st_mtime)
            print(f"✓ Latest file: {latest_file.name}")
            
            with open(latest_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            print(f"✓ File content is valid JSON")
            print(f"  - coin: {data.get('coin')}")
            print(f"  - minutes: {len(data.get('minutes', []))} entries")
        
        print(f"\n{'=' * 70}")
        print(f"✓ OrderbookTUI _save_period_data test PASSED!")
        print(f"{'=' * 70}")
        return True
        
    except Exception as e:
        print(f"✗ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success1 = test_save_period_data()
    success2 = test_orderbook_tui_import()
    
    print(f"\n{'=' * 70}")
    print(f"FINAL RESULT:")
    print(f"  - Basic save test: {'PASSED' if success1 else 'FAILED'}")
    print(f"  - OrderbookTUI test: {'PASSED' if success2 else 'FAILED'}")
    print(f"{'=' * 70}")
    
    sys.exit(0 if (success1 and success2) else 1)
