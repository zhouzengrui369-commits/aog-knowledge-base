"""City 模型 - CONTRACT §1.1"""
from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, Field


Region = Literal[
    "华北", "华东", "华南", "华中", "西南", "西北", "东北",
    "国际-欧洲", "国际-亚洲", "国际-美洲", "国际-中东", "国际-非洲", "国际-大洋洲",
]

Status = Literal["现行", "暂停", "已废"]


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
    org: str = Field(..., description="单位名称")
    phone: List[str] = Field(..., description="联系电话列表")
    email: Optional[str] = Field(None, description="邮箱")
    role: str = Field(..., description="职责, 例 '7×24'")


class Warehouse(BaseModel):
    location: str = Field(..., description="仓库位置")
    main: List[str] = Field(..., description="主要备件清单")


class Logistics(BaseModel):
    rail: str = Field(..., description="铁路物流方案")
    air: str = Field(..., description="航空物流方案")
    road: str = Field(..., description="公路物流方案")


class City(BaseModel):
    """航站/城市预案 - CONTRACT §1.1"""

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
