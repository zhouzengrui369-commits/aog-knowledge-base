"""City 模型 - CONTRACT §1.1 + P0-5 数据可信度 9 字段 (Owner 7/29 授权)
"""
from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, Field


Region = Literal[
    "华北", "华东", "华南", "华中", "西南", "西北", "东北",
    "国际-欧洲", "国际-亚洲", "国际-美洲", "国际-中东", "国际-非洲", "国际-大洋洲",
]

Status = Literal["现行", "暂停", "已废"]

# ★ P0-5: 数据可信度 6 状态 (Owner 7/29 授权, D-044-D)
ReviewStatus = Literal[
    "VERIFIED",      # 已人工或交叉验证
    "UNVERIFIED",    # 来源存在但未审核
    "STALE",         # 来源过期 (>30 天)
    "MISSING",       # 来源缺失, UI 显示"暂无已核验数据"
    "FIXTURE",       # 测试 fixture, UI 显著标识
    "REDACTED",      # 已脱敏, 仅显示 role 不显示具体值
]

# ★ P0-5: PII 等级
PiiClassification = Literal["none", "internal", "confidential", "restricted"]

# ★ P0-5: 适用环境
Environment = Literal["dev", "staging", "production", "all"]


class FleetItem(BaseModel):
    model: str = Field(..., description="机型, 例 'B787'")
    short_stay: bool = Field(..., description="是否短停执飞")
    after: bool = Field(..., description="是否航后执飞")


class PartItem(BaseModel):
    pn: str = Field(..., description="件号")
    name: str = Field(..., description="备件名称")
    stock: int = Field(..., ge=0, description="库存数量")
    unit: str = Field(..., description="单位, 例 '个'")


class ContactItem(BaseModel):
    """联系人 - D-030 permission 字段 + P0-6 redacted 字段"""
    org: str = Field(..., description="单位名称")
    phone: List[str] = Field(..., description="联系电话列表")
    email: Optional[str] = Field(None, description="邮箱")
    role: str = Field(..., description="职责, 例 '7×24'")
    # D-030 (commit c883905, 7/27): 联系人权限级别
    #   - public:     航司公开 desk 公共电话
    #   - internal:   库房/负责人/商务内部手机号 (前端半透明)
    #   - restricted: 供应商商务联系人 (Satair/空客/...) — 前端折叠+需登录
    # P0-6 (Owner 7/29): 保持 D-030 命名, 加 redacted 兜底
    permission: Literal["public", "internal", "restricted"] = Field(
        "public", description="D-030 权限级别 (P0-6 沿用)"
    )
    # ★ P0-6: 脱敏标志 (Owner 7/29 授权)
    # true 时 _decode_contact 把 phone/email 替换为 "REDACTED"
    # 触发场景: 个人手机号 (13910301946) / 商业联系人邮箱 (Satair SPE) / 数据缺失
    redacted: bool = Field(
        False, description="P0-6 是否脱敏 (true → phone/email 返 REDACTED)"
    )


class Warehouse(BaseModel):
    location: str = Field(..., description="仓库位置")
    main: List[str] = Field(..., description="主要备件清单")


class Logistics(BaseModel):
    rail: str = Field(..., description="铁路物流方案")
    air: str = Field(..., description="航空物流方案")
    road: str = Field(..., description="公路物流方案")


# ★ P0-5: 数据可信度 9 字段 (Owner 7/29 授权, D-044-D)
class DataTrust(BaseModel):
    """数据可信度 9 字段 + 1 状态枚举 (D-044-D)

    9 字段:
    1.  source_document    - 源文件相对路径, e.g. 'AOG知识库/02_外战预案/B-北京大兴.docx'
    2.  source_location    - 源在仓库的位置, e.g. 'filesystem:02_外战预案' 或 'wiki:00_MOC'
    3.  source_version     - 源版本, e.g. '2026-07-15 v1.0'
    4.  updated_at         - 最后更新时间 ISO8601
    5.  reviewed_at        - 最后审核时间 ISO8601
    6.  reviewed_by        - 审核人 (e.g. 'NJX' / 'Mavis PM')
    7.  review_status      - 审核状态: VERIFIED/UNVERIFIED/STALE/MISSING/FIXTURE/REDACTED
    8.  confidence         - 置信度 0.0-1.0, 0=纯猜, 1=权威源
    9.  environment        - 适用环境: dev/staging/production/all
    10. pii_classification - PII 等级: none/internal/confidential/restricted

    6 状态枚举:
    - VERIFIED   - 已人工或交叉验证
    - UNVERIFIED - 来源存在但未审核 (default)
    - STALE      - 来源过期 (>30 天)
    - MISSING    - 来源缺失 (上海浦东/虹桥当前是), UI 显示"暂无已核验数据"
    - FIXTURE    - 测试 fixture, UI 显著标识
    - REDACTED   - 已脱敏, 仅显示 role 不显示具体值
    """
    source_document: Optional[str] = Field(
        None, description="源文件相对路径"
    )
    source_location: Optional[str] = Field(
        None, description="源在仓库的位置"
    )
    source_version: Optional[str] = Field(
        None, description="源版本"
    )
    updated_at: Optional[str] = Field(
        None, description="最后更新时间 ISO8601"
    )
    reviewed_at: Optional[str] = Field(
        None, description="最后审核时间 ISO8601"
    )
    reviewed_by: Optional[str] = Field(
        None, description="审核人"
    )
    review_status: ReviewStatus = Field(
        "UNVERIFIED",
        description="审核状态 (VERIFIED/UNVERIFIED/STALE/MISSING/FIXTURE/REDACTED)",
    )
    confidence: Optional[float] = Field(
        None, ge=0.0, le=1.0,
        description="置信度 0.0-1.0, 0=纯猜, 1=权威源",
    )
    environment: Environment = Field(
        "all", description="适用环境 (dev/staging/production/all)"
    )
    pii_classification: PiiClassification = Field(
        "none", description="PII 等级 (none/internal/confidential/restricted)"
    )


class City(BaseModel):
    """航站/城市预案 - CONTRACT §1.1 + P0-5 数据可信度"""

    code: str = Field(..., description="主键, 例 'B-北京大兴'")
    name: str
    airport: str
    iata: str
    pinyin: str
    region: Region
    status: Status
    tags: List[str] = Field(default_factory=list)
    fleet: List[FleetItem] = Field(default_factory=list)
    parts: List[PartItem] = Field(default_factory=list)
    contacts: List[ContactItem] = Field(default_factory=list)
    warehouse: Warehouse
    logistics: Logistics
    content_md: str = Field(..., min_length=0, description="完整预案 md 文本")
    source_path: str
    updated_at: str = Field(..., description="ISO8601")

    # ★ P0-5: 数据可信度 9 字段 (D-044-D, 内嵌为子模型, 跟前端 types 对齐)
    trust: DataTrust = Field(
        default_factory=DataTrust,
        description="数据可信度 9 字段 (D-044-D, Owner 7/29 授权)",
    )
