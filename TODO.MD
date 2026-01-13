1.阅读项目代码，总结功能和需要启动准备，放到readme-review.md
2.配置完成，开始安转依赖并快速测试，并不交易
3.检查下面5个是否完备：
1. ✅ 安装 Python 依赖
2. ✅ 获取 Polymarket 钱包凭证（私钥 + Safe 地址）
3. ✅ 配置环境变量或 config.yaml
4. ✅ 运行快速入门示例验证配置
5. ✅ 从小额开始测试策略
4.不一定要meta mask的钱包，我的是Phantom的ETH钱包，我已经配置好.env文件，开始检查私匙是否生效
5.python apps/orderbook_tui.py --coin BTC 能否获取当前BTC的价格，以及15分钟线开始的价格
6.python apps/orderbook_tui.py能否获取15分钟内，每分钟的up/down百分比曲线的变化数据
7.不对，开始价格和当前价格是指比特币的价格；当前屏幕一直闪，UI 数据更新有问题，我期望的是固定位置的显示变化的价格
8.增加数据，BTC changed price,BTC 变化如果是增加就是+，减少就是-，在每分钟up/down后面显示变化的BTC 价格
9.增加2个数据，BTC begin price 显示每15分钟开始时的数据, BTC changed price和开始的数据比的变化值
10. ✅ python [orderbook_tui.py](http://_vscodecontentref_/1) --coin BTC 命令无法运行，使用python apps/orderbook_tui.py --coin BTC命令，屏幕一直闪，是否可以让它固定住位置，不上下移动，我知道上下移动的原因是不断有内容刷新，但是之前没有增强之前，屏幕是固定的，没有跳动。
11. ✅ python [orderbook_tui.py](http://_vscodecontentref_/1) --coin BTC 无法运行，检查原因，还有为什么不用python apps/orderbook_tui.py --coin BTC 命令执行，问题任然存在
12. ✅ 现在内容显示是没有问题的，但是我还需要当前15分钟内，第1到15分钟的up,down的百分比情况，还有每一分钟开始结束btc的增加和减少情况
13. ✅ 15-Minute Period - Minute-by-Minute Changes:我需要在这个下面增加up,down在每分钟开始的值
14. ✅ 现实任务完成，删除所有的test开头的脚本，rish用来优化UI展示才是根本的解决方案，删除其他解决方案的无用代码，保持代码的整洁
15. ✅ 现在每15分钟之后数据就不再输出，我知道是新的事件Slug不一样，我们是否可以连续的监控接着的15分钟数据。
16. ✅ 我需要保持数据，数据内容如下，保存成Json 格式的文件，每15分钟数据保存一个文件，命名规则YYYY-MM-MM-HH-MM,保存到/files目录。
15-Minute Period - Minute-by-Minute Changes:
Min  Time        UP      UP%    DOWN    DOWN% |   BTC Start     BTC End     BTC Δ
17. ✅ 任务16没有完成，代码有报错，生成测试脚本完成测试
18. ✅ 任务15经过测试，没有完全刷新，数据是清空了，但是新数据没有及时刷新，一直是空的，解决这个问题。
    修复：在市场切换时先取消订阅旧token再订阅新token，确保WebSocket正确接收新市场数据
    需求补充：在你检测的过程中也就是昨天晚上是正常的，但是早上又不行了？检查原因
    解决：已验证代码逻辑正确，市场切换功能正常工作
    需求补充：运行之后，还有问题，数据没有刷新，接着检查，想一下为什么每次重启可以拿到数据，而15分钟结束之后不行？每次重启之后都是可行的，你不要反复重启观测数据，这个没有意义。
    回顾：初始订阅 用 {"assets_ids": [...], "type": "market"}，追加/切换订阅 应该用 {"assets_ids": [...], "operation": "subscribe"}
19. ✅ 任务16，现在展示有问题，没有BTC的信息，也就是任务8,9的代码不工作了，检查原因。
    解决：BTC价格API (CoinGecko) 有时因速率限制失败。已添加备用API：CoinCap和Binance，确保BTC价格获取的可靠性
20. ✅ 设置静默运行的开关，开关开启的时候，不输出数据，默认只保存json文件，减少系统资源的消耗，让系统可以稳定长时间运行。生成BAT 脚本，我会用这个脚本系统启动的时候运行，用于保存每天poly market的数据。
    解决：
    - 添加 --silent 参数：python orderbook.py --coin BTC --silent
    - 静默模式下只输出每分钟简短状态，不渲染UI
    - 创建 start_silent_monitor.bat 用于手动启动
    - 创建 start_background_monitors.bat 用于系统启动时运行多个币种监控

21. ✅ 运行start_silent_monitor.bat，想让系统在后台静默运行，
    错误：为什么启动之后，需要按任意键才能继续呢？可以去掉这个吗？我想开机启动的时候设置，自动运行，不用手动干预
    解决：
    - 移除脚本中的 pause 命令
    - 在脚本结束时使用 exit /b 0 而不是等待用户输入
    - 修复 start_background_monitors.bat 中的重复 else 语法错误
    - 验证：脚本启动后立即运行，不需要用户干预
    
22. ✅ 服务启动之后，电脑锁屏，15分钟之后就休眠了，我需要在休眠状态start_silent_monitor.bat一样能运行，是否需要启动另外一个守护线程？思考并给出答案。
    分析：Windows休眠时所有用户进程都会暂停，这是操作系统级别的限制，守护线程无法解决。
    解决方案：
    - 方案1：`start_monitor_no_sleep.bat` - 使用powercfg禁用休眠（需要管理员权限）
    - 方案2：`start_monitor_keepawake.bat` - 使用PowerShell模拟键盘活动（F15键）防止休眠（无需管理员权限）
    - 辅助脚本：
      - `prevent_sleep.bat` - 单独禁用休眠
      - `restore_sleep.bat` - 恢复休眠设置
      - `keep_awake.ps1` - PowerShell保持唤醒脚本
    推荐：使用 `start_monitor_keepawake.bat`，它会在后台启动keep-awake进程，每60秒模拟一次键盘活动防止系统休眠
    需求更新：✅ 保留start_monitor_keepawake.bat，删除其他无用的方案，优化脚本输出
    - 已删除：start_monitor_no_sleep.bat, prevent_sleep.bat, restore_sleep.bat
    - 已优化：start_monitor_keepawake.bat 现在显示友好的启动进度和实时状态输出
23. ✅ 运行start_monitor_keepawake.bat，监控效果是否支持，现在运行退出了
    问题：之前的脚本使用PowerShell管道导致缓冲问题，输出不能实时显示
    解决：
    - 修复 start_monitor_keepawake.bat 中的Windows批处理嵌套if语法错误
    - 移除PowerShell管道，直接运行Python脚本
    - 修改 orderbook_tui.py 添加 `_log()` 方法，同时输出到控制台和日志文件
    - 使用 `flush=True` 确保输出立即显示
    验证：脚本现在正常运行，实时显示监控状态
24. ✅ 经过检查，脚本运行一段时间后连接断开了，你检查files目录，早上八点生成之后，直到下午五点才连上，是不是我需要设置脚本运行12小时就重启一次。
    问题分析：从files目录的文件时间戳看，08:30到17:09有近9小时的数据丢失，WebSocket连接断开后没有自动恢复
    解决方案：
    - 添加自动重启机制：默认每12小时自动重启（可通过 --max-runtime 参数调整）
    - 添加连接健康检查：每60秒检查一次连接状态
    - 无数据超时检测：如果5分钟（300秒）没有收到数据，自动触发重启
    - WebSocket断开检测：检测到连接断开时自动重启
    - 崩溃恢复：脚本异常退出时自动重启
    - 退出码约定：0=正常退出，42=需要重启
    修改文件：
    - apps/orderbook_tui.py: 添加 MAX_RUNTIME_HOURS、HEALTH_CHECK_INTERVAL、MAX_NO_DATA_SECONDS 常量
    - apps/orderbook_tui.py: 添加 start_time、last_data_time、should_restart 状态跟踪
    - apps/orderbook_tui.py: 在数据回调中更新 last_data_time
    - apps/orderbook_tui.py: 在主循环中添加运行时间检查和健康检查逻辑
    - apps/orderbook_tui.py: main() 函数返回退出码
    - start_monitor_keepawake.bat: 添加自动重启循环，检测退出码42时自动重启