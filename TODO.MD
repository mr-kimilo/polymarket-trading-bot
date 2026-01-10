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