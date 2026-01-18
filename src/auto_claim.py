"""
Auto Claim Module - Automatic redemption of winning positions

当钱包余额低于阈值时，自动claim已解决市场的获胜仓位。

Features:
- 检查USDC余额
- 获取可redeem的仓位
- 使用官方py-builder-relayer-client库通过Relayer执行gasless交易

Example:
    from src.auto_claim import AutoClaimer
    
    claimer = AutoClaimer(
        safe_address="0x...",
        private_key="0x...",
        min_balance=10.0  # 当余额低于10 USDC时触发claim
    )
    
    # 检查并执行claim
    await claimer.check_and_claim()
"""

import logging
import os
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from web3 import Web3
from eth_abi import encode

import requests
import yaml

logger = logging.getLogger(__name__)


# Contract addresses on Polygon
USDC_ADDRESS = "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174"  # USDC.e on Polygon
CTF_ADDRESS = "0x4D97DCd97eC945f40cF65F87097ACe5EA0476045"  # CTF contract
NEG_RISK_CTF_ADDRESS = "0xC5d563A36AE78145C45a50134d48A1215220f80a"  # Neg Risk CTF

# API endpoints
DATA_API_URL = "https://data-api.polymarket.com"
RELAYER_URL = "https://relayer-v2.polymarket.com"
CHAIN_ID = 137  # Polygon

# ABIs
USDC_ABI = [
    {
        "constant": True,
        "inputs": [{"name": "_owner", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "balance", "type": "uint256"}],
        "type": "function"
    }
]


@dataclass
class RedeemablePosition:
    """可redeem的仓位信息"""
    condition_id: str
    asset: str
    size: float
    current_value: float
    outcome: str
    title: str
    neg_risk: bool


class AutoClaimer:
    """
    自动claim管理器
    
    当USDC余额低于阈值时，自动redeem已解决市场的获胜仓位。
    使用官方py-builder-relayer-client库执行gasless交易。
    """
    
    def __init__(
        self,
        safe_address: str,
        private_key: Optional[str] = None,
        min_balance: float = 10.0,
        rpc_url: str = "https://polygon-rpc.com",
        builder_api_key: Optional[str] = None,
        builder_api_secret: Optional[str] = None,
        builder_api_passphrase: Optional[str] = None
    ):
        """
        初始化AutoClaimer
        
        Args:
            safe_address: Polymarket Safe/Proxy钱包地址
            private_key: 私钥（用于签名交易）
            min_balance: 最小USDC余额阈值
            rpc_url: Polygon RPC URL
            builder_api_key: Builder API Key
            builder_api_secret: Builder API Secret
            builder_api_passphrase: Builder API Passphrase
        """
        self.safe_address = Web3.to_checksum_address(safe_address)
        self.private_key = private_key
        self.min_balance = min_balance
        self.rpc_url = rpc_url
        
        # Web3 connection (添加POA中间件支持Polygon)
        self.w3 = Web3(Web3.HTTPProvider(rpc_url))
        try:
            from web3.middleware import ExtraDataToPOAMiddleware
            self.w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)
        except ImportError:
            try:
                from web3.middleware import geth_poa_middleware
                self.w3.middleware_onion.inject(geth_poa_middleware, layer=0)
            except ImportError:
                pass
        
        # USDC contract
        self.usdc_contract = self.w3.eth.contract(
            address=Web3.to_checksum_address(USDC_ADDRESS),
            abi=USDC_ABI
        )
        
        # Builder credentials
        self.builder_api_key = builder_api_key or os.environ.get("POLY_BUILDER_API_KEY", "")
        self.builder_api_secret = builder_api_secret or os.environ.get("POLY_BUILDER_API_SECRET", "")
        self.builder_api_passphrase = builder_api_passphrase or os.environ.get("POLY_BUILDER_API_PASSPHRASE", "")
        
        # 如果环境变量没有，尝试从config.yaml读取
        if not all([self.builder_api_key, self.builder_api_secret, self.builder_api_passphrase]):
            self._load_config_credentials()
        
        # 初始化RelayClient（如果有私钥和builder凭证）
        self.relay_client = None
        if self.private_key and all([self.builder_api_key, self.builder_api_secret, self.builder_api_passphrase]):
            self._init_relay_client()
    
    def _load_config_credentials(self):
        """从config.yaml加载builder凭证"""
        try:
            with open("config.yaml", "r") as f:
                config = yaml.safe_load(f)
                builder = config.get("builder", {})
                self.builder_api_key = self.builder_api_key or builder.get("api_key", "")
                self.builder_api_secret = self.builder_api_secret or builder.get("api_secret", "")
                self.builder_api_passphrase = self.builder_api_passphrase or builder.get("api_passphrase", "")
        except Exception as e:
            logger.debug(f"Could not load config.yaml: {e}")
    
    def _init_relay_client(self):
        """初始化官方RelayClient"""
        try:
            from py_builder_relayer_client.client import RelayClient, BuilderConfig, SafeTransaction
            from py_builder_signing_sdk.config import BuilderApiKeyCreds
            
            # 配置本地签名
            builder_config = BuilderConfig(
                local_builder_creds=BuilderApiKeyCreds(
                    key=self.builder_api_key,
                    secret=self.builder_api_secret,
                    passphrase=self.builder_api_passphrase,
                )
            )
            
            self.relay_client = RelayClient(
                RELAYER_URL,
                CHAIN_ID,
                self.private_key,
                builder_config
            )
            
            logger.info("RelayClient initialized successfully")
            
        except ImportError as e:
            logger.warning(f"Could not import py_builder_relayer_client: {e}")
            logger.warning("Install it with: pip install py-builder-relayer-client")
        except Exception as e:
            logger.error(f"Failed to initialize RelayClient: {e}")
    
    def get_usdc_balance(self) -> float:
        """
        获取USDC余额
        
        Returns:
            USDC余额（单位：USDC，6位小数转换后）
        """
        try:
            balance_raw = self.usdc_contract.functions.balanceOf(
                self.safe_address
            ).call()
            # USDC has 6 decimals
            return balance_raw / 1e6
        except Exception as e:
            logger.error(f"Failed to get USDC balance: {e}")
            return 0.0
    
    def get_redeemable_positions(self, min_value: float = 0.01) -> List[RedeemablePosition]:
        """
        获取可redeem的仓位列表
        
        Args:
            min_value: 最小价值过滤（只返回currentValue >= min_value的仓位）
            
        Returns:
            可redeem的仓位列表
        """
        try:
            url = f"{DATA_API_URL}/positions"
            params = {
                "user": self.safe_address,
                "redeemable": "true",
                "sizeThreshold": 0
            }
            
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            
            positions = response.json()
            
            redeemable = []
            for pos in positions:
                # 只添加有价值的可redeem仓位（过滤输掉的仓位）
                if pos.get("redeemable", False) and pos.get("currentValue", 0) >= min_value:
                    redeemable.append(RedeemablePosition(
                        condition_id=pos.get("conditionId", ""),
                        asset=pos.get("asset", ""),
                        size=pos.get("size", 0),
                        current_value=pos.get("currentValue", 0),
                        outcome=pos.get("outcome", ""),
                        title=pos.get("title", ""),
                        neg_risk=pos.get("negativeRisk", False)
                    ))
            
            return redeemable
            
        except Exception as e:
            logger.error(f"Failed to get redeemable positions: {e}")
            return []
    
    def _build_redeem_tx_data(
        self,
        condition_id: str,
        neg_risk: bool = False
    ) -> str:
        """
        构建redeem交易数据
        
        Args:
            condition_id: 市场条件ID
            neg_risk: 是否为neg_risk市场
            
        Returns:
            交易数据（十六进制字符串）
        """
        # Polymarket使用的collateral token是USDC
        collateral_token = Web3.to_checksum_address(USDC_ADDRESS)
        
        # parentCollectionId在Polymarket中为空 (32 bytes of zeros)
        parent_collection_id = b'\x00' * 32
        
        # indexSets: [1, 2] 代表两个outcome
        index_sets = [1, 2]
        
        # 处理condition_id
        if condition_id.startswith("0x"):
            cond_id_bytes = bytes.fromhex(condition_id[2:])
        else:
            cond_id_bytes = bytes.fromhex(condition_id)
        
        # 函数选择器: redeemPositions(address,bytes32,bytes32,uint256[])
        # keccak256("redeemPositions(address,bytes32,bytes32,uint256[])") 前4字节
        function_selector = "0x01b7037c"
        
        # 编码参数
        encoded_args = encode(
            ['address', 'bytes32', 'bytes32', 'uint256[]'],
            [collateral_token, parent_collection_id, cond_id_bytes, index_sets]
        )
        
        return function_selector + encoded_args.hex()
    
    async def redeem_position(self, position: RedeemablePosition) -> bool:
        """
        Redeem单个仓位
        
        Args:
            position: 要redeem的仓位
            
        Returns:
            是否成功
        """
        try:
            logger.info(f"Redeeming position: {position.title} ({position.outcome})")
            
            # 选择正确的合约地址
            contract_address = NEG_RISK_CTF_ADDRESS if position.neg_risk else CTF_ADDRESS
            
            # 构建交易数据
            tx_data = self._build_redeem_tx_data(
                position.condition_id,
                position.neg_risk
            )
            
            # 使用官方RelayClient执行
            if self.relay_client:
                try:
                    from py_builder_relayer_client.client import SafeTransaction
                    # 获取OperationType enum
                    OperationType = SafeTransaction.__annotations__['operation']
                    
                    transactions = [SafeTransaction(
                        to=contract_address,
                        operation=OperationType.Call,
                        data=tx_data,
                        value="0"
                    )]
                    
                    logger.info("Submitting via RelayClient...")
                    response = self.relay_client.execute(
                        transactions,
                        f"Redeem {position.title}"
                    )
                    
                    # 等待交易确认
                    result = response.wait()
                    
                    if result is not None:
                        # 交易成功（没有抛出异常）
                        logger.info(f"Redeem successful! TX: {response.transaction_hash}")
                        return True
                    elif response.transaction_hash:
                        # 虽然wait返回None，但交易可能已经成功
                        logger.info(f"Transaction submitted: {response.transaction_hash}")
                        return True
                    else:
                        logger.warning("Relayer returned no result")
                        
                except Exception as e:
                    logger.error(f"RelayClient execution failed: {e}")
            else:
                logger.warning("RelayClient not initialized - check private_key and builder credentials")
            
            return False
                
        except Exception as e:
            logger.error(f"Failed to redeem position: {e}")
            return False
    
    async def redeem_all_positions(self, positions: List[RedeemablePosition]) -> Dict[str, Any]:
        """
        批量redeem所有仓位（一次交易）
        
        Args:
            positions: 要redeem的仓位列表
            
        Returns:
            执行结果
        """
        if not positions:
            return {"success": False, "error": "No positions to redeem"}
        
        if not self.relay_client:
            return {"success": False, "error": "RelayClient not initialized"}
        
        try:
            from py_builder_relayer_client.client import SafeTransaction
            # 获取OperationType enum
            OperationType = SafeTransaction.__annotations__['operation']
            
            # 构建所有交易
            transactions = []
            for pos in positions:
                contract_address = NEG_RISK_CTF_ADDRESS if pos.neg_risk else CTF_ADDRESS
                tx_data = self._build_redeem_tx_data(pos.condition_id, pos.neg_risk)
                transactions.append(SafeTransaction(
                    to=contract_address,
                    operation=OperationType.Call,
                    data=tx_data,
                    value="0"
                ))
            
            logger.info(f"Submitting batch redeem for {len(transactions)} positions...")
            response = self.relay_client.execute(
                transactions,
                f"Batch redeem {len(positions)} positions"
            )
            
            result = response.wait()
            
            if result is not None or response.transaction_hash:
                tx_hash = response.transaction_hash
                logger.info(f"Batch redeem successful! TX: {tx_hash}")
                return {
                    "success": True,
                    "transaction_hash": tx_hash,
                    "redeemed_count": len(positions)
                }
            else:
                return {"success": False, "error": "No result from relayer"}
                
        except Exception as e:
            logger.error(f"Batch redeem failed: {e}")
            return {"success": False, "error": str(e)}
    
    async def check_and_claim(self) -> Dict[str, Any]:
        """
        检查余额并在必要时执行claim
        
        Returns:
            执行结果
        """
        result = {
            "balance": 0.0,
            "redeemable_count": 0,
            "redeemed_count": 0,
            "redeemed_value": 0.0,
            "positions": []
        }
        
        # 获取当前余额
        balance = self.get_usdc_balance()
        result["balance"] = balance
        
        logger.info(f"Current USDC balance: ${balance:.2f}")
        
        # 如果余额高于阈值，不需要claim
        if balance >= self.min_balance:
            logger.info(f"Balance ${balance:.2f} >= threshold ${self.min_balance:.2f}, no claim needed")
            return result
        
        logger.info(f"Balance ${balance:.2f} < threshold ${self.min_balance:.2f}, checking for redeemable positions...")
        
        # 获取可redeem的仓位
        positions = self.get_redeemable_positions()
        result["redeemable_count"] = len(positions)
        
        if not positions:
            logger.info("No redeemable positions found")
            return result
        
        logger.info(f"Found {len(positions)} redeemable positions")
        
        # 记录仓位信息
        for pos in positions:
            result["positions"].append({
                "title": pos.title,
                "outcome": pos.outcome,
                "value": pos.current_value
            })
        
        # 尝试批量redeem
        batch_result = await self.redeem_all_positions(positions)
        
        if batch_result.get("success"):
            result["redeemed_count"] = len(positions)
            result["redeemed_value"] = sum(pos.current_value for pos in positions)
        else:
            # 如果批量失败，尝试逐个redeem
            logger.info("Batch redeem failed, trying individual redemptions...")
            for pos in positions:
                success = await self.redeem_position(pos)
                if success:
                    result["redeemed_count"] += 1
                    result["redeemed_value"] += pos.current_value
        
        # 更新最终余额
        result["balance"] = self.get_usdc_balance()
        
        logger.info(
            f"Claim complete: redeemed {result['redeemed_count']}/{result['redeemable_count']} "
            f"positions, value=${result['redeemed_value']:.2f}"
        )
        
        return result


# 便捷函数
async def auto_claim_if_needed(
    safe_address: str,
    private_key: Optional[str] = None,
    min_balance: float = 10.0
) -> Dict[str, Any]:
    """
    检查余额并在需要时自动claim
    
    Args:
        safe_address: Polymarket Safe钱包地址
        private_key: 私钥（必需，用于签名交易）
        min_balance: 最小余额阈值
        
    Returns:
        执行结果
    """
    claimer = AutoClaimer(
        safe_address=safe_address,
        private_key=private_key,
        min_balance=min_balance
    )
    return await claimer.check_and_claim()
