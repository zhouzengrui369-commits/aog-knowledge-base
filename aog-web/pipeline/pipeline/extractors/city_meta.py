"""City 字段提取: 从 docx 表格抽 city/airport/iata/region/fleet/parts/contacts/warehouse/logistics。

文件名规则 (CONTRACT §5.4):
  `字母-城市名（状态）.docx` 例 `B-北京大兴.docx` / `A-阿姆斯特丹（暂停）.docx`
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Union

from pypinyin import lazy_pinyin

from ..parsers.docx import DocxSection, DocxTable, parse_docx, docx_table_to_markdown

PathLike = Union[str, Path]

# 城市名 (中文) → 常见 IATA 代码 (docx 缺失时的 fallback)
COMMON_IATA: dict[str, str] = {
    "阿姆斯特丹": "AMS", "雅典": "ATH", "曼谷": "BKK", "北京": "PEK", "北京大兴": "PKX",
    "北京首都": "PEK", "柏林": "BER", "布鲁塞尔": "BRU", "布达佩斯": "BUD",
    "广州": "CAN", "长沙": "CSX", "成都": "CTU", "重庆": "CKG", "大连": "DLC",
    "东京成田": "NRT", "东京羽田": "HND", "达卡": "DAC", "迪拜": "DXB",
    "法兰克福": "FRA", "福冈": "FUK", "桂林": "KWL", "海参崴": "VVO",
    "杭州": "HGH", "赫尔辛基": "HEL", "香港": "HKG", "札幌": "CTS",
    "雅加达": "CGK", "吉隆坡": "KUL", "昆明": "KMG", "伦敦希思罗": "LHR",
    "伦敦盖特威客": "LGW", "洛杉矶": "LAX", "马德里": "MAD", "马尼拉": "MNL",
    "曼彻斯特": "MAN", "墨尔本": "MEL", "米兰": "MXP", "名古屋": "NGO",
    "南京": "NKG", "纽约肯尼迪": "JFK", "纽约纽瓦克": "EWR", "大阪": "KIX",
    "巴黎": "CDG", "青岛": "TAO", "青岛流亭": "TAO", "青岛胶东": "TAO",
    "罗马": "FCO", "首尔仁川": "ICN", "首尔金浦": "GMP", "三亚": "SYX",
    "上海": "SHA", "上海浦东": "PVG", "上海虹桥": "SHA", "深圳": "SZX",
    "新加坡": "SIN", "沈阳": "SHE", "札幌新千岁": "CTS", "悉尼": "SYD",
    "台北": "TPE", "天津": "TSN", "东京": "TYO", "多伦多": "YYZ",
    "乌鲁木齐": "URC", "威尼斯": "VCE", "维也纳": "VIE", "厦门": "XMN",
    "西安": "XIY", "西雅图": "SEA", "烟台": "YNT", "仰光": "RGN",
    "伊尔库茨克": "IKT", "银川": "INC", "郑州": "CGO", "芝加哥": "ORD",
    "珠海": "ZUH",
}


# 中国省份 → 大区 (CONTRACT §1.1)
REGION_DOMESTIC: dict[str, str] = {
    "北京": "华北", "天津": "华北", "河北": "华北", "山西": "华北", "内蒙古": "华北",
    "上海": "华东", "江苏": "华东", "浙江": "华东", "安徽": "华东", "福建": "华东", "江西": "华东", "山东": "华东",
    "广东": "华南", "广西": "华南", "海南": "华南",
    "河南": "华中", "湖北": "华中", "湖南": "华中",
    "重庆": "西南", "四川": "西南", "贵州": "西南", "云南": "西南", "西藏": "西南",
    "陕西": "西北", "甘肃": "西北", "青海": "西北", "宁夏": "西北", "新疆": "西北",
    "辽宁": "东北", "吉林": "东北", "黑龙江": "东北",
    "台湾": "华东",  # 暂归华东
}

# 国家/地区 → 国际区 (CONTRACT §1.1)
REGION_INTL: dict[str, str] = {
    # 亚洲
    "日本": "国际-亚洲", "韩国": "国际-亚洲", "朝鲜": "国际-亚洲", "蒙古": "国际-亚洲",
    "泰国": "国际-亚洲", "越南": "国际-亚洲", "缅甸": "国际-亚洲", "老挝": "国际-亚洲",
    "柬埔寨": "国际-亚洲", "马来西亚": "国际-亚洲", "新加坡": "国际-亚洲", "印度尼西亚": "国际-亚洲",
    "菲律宾": "国际-亚洲", "文莱": "国际-亚洲", "印度": "国际-亚洲", "巴基斯坦": "国际-亚洲",
    "孟加拉": "国际-亚洲", "斯里兰卡": "国际-亚洲", "尼泊尔": "国际-亚洲", "马尔代夫": "国际-亚洲",
    "阿联酋": "国际-中东", "沙特": "国际-中东", "伊朗": "国际-中东", "伊拉克": "国际-中东",
    "卡塔尔": "国际-中东", "科威特": "国际-中东", "巴林": "国际-中东", "阿曼": "国际-中东",
    "也门": "国际-中东", "约旦": "国际-中东", "黎巴嫩": "国际-中东", "叙利亚": "国际-中东",
    "以色列": "国际-中东", "土耳其": "国际-中东",
    # 欧洲
    "英国": "国际-欧洲", "法国": "国际-欧洲", "德国": "国际-欧洲", "意大利": "国际-欧洲",
    "西班牙": "国际-欧洲", "葡萄牙": "国际-欧洲", "荷兰": "国际-欧洲", "比利时": "国际-欧洲",
    "瑞士": "国际-欧洲", "奥地利": "国际-欧洲", "希腊": "国际-欧洲", "爱尔兰": "国际-欧洲",
    "瑞典": "国际-欧洲", "挪威": "国际-欧洲", "芬兰": "国际-欧洲", "丹麦": "国际-欧洲",
    "冰岛": "国际-欧洲", "波兰": "国际-欧洲", "捷克": "国际-欧洲", "匈牙利": "国际-欧洲",
    "罗马尼亚": "国际-欧洲", "保加利亚": "国际-欧洲", "塞尔维亚": "国际-欧洲", "克罗地亚": "国际-欧洲",
    "斯洛文尼亚": "国际-欧洲", "斯洛伐克": "国际-欧洲", "波黑": "国际-欧洲",
    "黑山": "国际-欧洲", "北马其顿": "国际-欧洲", "阿尔巴尼亚": "国际-欧洲", "科索沃": "国际-欧洲",
    "爱沙尼亚": "国际-欧洲", "拉脱维亚": "国际-欧洲", "立陶宛": "国际-欧洲",
    "白俄罗斯": "国际-欧洲", "乌克兰": "国际-欧洲", "摩尔多瓦": "国际-欧洲",
    "俄罗斯": "国际-欧洲", "哈萨克": "国际-欧洲",  # 跨界,暂归欧洲
    # 美洲
    "美国": "国际-美洲", "加拿大": "国际-美洲", "墨西哥": "国际-美洲",
    "巴西": "国际-美洲", "阿根廷": "国际-美洲", "智利": "国际-美洲", "秘鲁": "国际-美洲",
    "古巴": "国际-美洲", "牙买加": "国际-美洲",
    # 非洲
    "埃及": "国际-非洲", "南非": "国际-非洲", "摩洛哥": "国际-非洲", "突尼斯": "国际-非洲",
    "肯尼亚": "国际-非洲", "埃塞俄比亚": "国际-非洲", "尼日利亚": "国际-非洲",
    "毛里求斯": "国际-非洲", "塞舌尔": "国际-非洲", "坦桑尼亚": "国际-非洲",
    # 大洋洲
    "澳大利亚": "国际-大洋洲", "新西兰": "国际-大洋洲", "斐济": "国际-大洋洲",
    "巴布亚新几内亚": "国际-大洋洲",
    # 中国港澳台
    "中国香港": "华南", "香港": "华南", "中国澳门": "华南", "澳门": "华南",
}


def pinyin_of(text: str) -> str:
    """中文转拼音, 无分隔, 全小写。例: 北京大兴 → beijingdaxing"""
    if not text:
        return ""
    return "".join(lazy_pinyin(text)).lower()


def region_from_name(country_or_province: str) -> str:
    """'广东' → '华南'; '日本' → '国际-亚洲'。找不到 → '国际-亚洲' fallback。"""
    if not country_or_province:
        return "国际-亚洲"
    s = country_or_province.strip()
    if s in REGION_DOMESTIC:
        return REGION_DOMESTIC[s]
    if s in REGION_INTL:
        return REGION_INTL[s]
    # 模糊匹配
    for k, v in REGION_DOMESTIC.items():
        if k in s or s in k:
            return v
    for k, v in REGION_INTL.items():
        if k in s or s in k:
            return v
    return "国际-亚洲"


def parse_code_and_status(filename: str) -> tuple[str, str, str, str]:
    """从文件名解析 (code, name, status, raw_label)。

    code 保留状态后缀以保证主键唯一 (e.g. 'A-阿姆斯特丹（暂停）')。
    name 去除后缀 (e.g. '阿姆斯特丹')。

    例: 'B-北京大兴.docx' → ('B-北京大兴', '北京大兴', '现行', 'B')
        'A-阿姆斯特丹（暂停）.docx' → ('A-阿姆斯特丹（暂停）', '阿姆斯特丹', '暂停', 'A')
    """
    name = filename
    for ext in (".docx", ".doc", ".md", ".pdf", ".xlsx"):
        if name.lower().endswith(ext):
            name = name[: -len(ext)]
            break

    # 保留 original name 用于 code
    name_orig = name

    # 状态后缀
    status = "现行"
    m = re.match(r"^(.+?)（([^）]+)）$", name)
    if m:
        name_inner = m.group(1)
        suffix = m.group(2)
        if any(k in suffix for k in ["暂停", "停航", "废弃", "废除", "已废"]):
            status = "暂停" if "暂停" in suffix else "已废"
        name = name_inner
    else:
        # 也支持全角 () 变体
        m2 = re.match(r"^(.+?)\(([^)]+)\)$", name)
        if m2 and any(k in m2.group(2) for k in ["暂停", "停航", "废弃", "废除", "已废"]):
            name = m2.group(1)
            status = "暂停" if "暂停" in m2.group(2) else "已废"

    # code 格式: 字母-城市。code 用 name_orig (含后缀), name 用去后缀的 name。
    m3 = re.match(r"^([A-Za-z])[-_](.+)$", name)
    if m3:
        raw_label = m3.group(1).upper()
        # code: raw_label + name_orig 的后半段 (含后缀)
        m_orig = re.match(r"^([A-Za-z])[-_](.+)$", name_orig)
        code_name = m_orig.group(2) if m_orig else m3.group(2)
        return f"{raw_label}-{code_name}", m3.group(2), status, raw_label
    # 没有前缀字母 - 整段作为 code
    return name_orig, name, status, name[0].upper() if name else "X"


# ---------- City dataclass ----------

@dataclass
class City:
    code: str
    name: str
    airport: str
    iata: str
    pinyin: str
    region: str
    status: str
    tags: list[str]
    fleet: list[dict]
    parts: list[dict]
    contacts: list[dict]
    warehouse: dict
    logistics: dict
    content_md: str
    source_path: str
    updated_at: str

    def to_dict(self) -> dict:
        return asdict(self)


# ---------- Section 识别 ----------

def _find_section(dt: DocxTable, *names: str) -> DocxSection | None:
    """按 name 找 section (支持模糊)。优先匹配非空 name 的 section。

    跳过空 section (name=""), 因为空 section 是表内分隔行。
    """
    # 1) 优先: 非空 name 匹配
    for sec in dt.sections:
        n = (sec.name or "").strip()
        if not n:
            continue
        for want in names:
            if want in n or n in want:
                return sec
    # 2) fallback: 任意 name 匹配 (含空)
    for sec in dt.sections:
        n = sec.name or ""
        for want in names:
            if want in n or n in want:
                return sec
    return None


def _extract_airport(dt: DocxTable) -> str:
    """机场名 = 第一个 title row。"""
    if dt.title_rows and dt.title_rows[0]:
        return dt.title_rows[0][0]
    return ""


def _extract_iata(dt: DocxTable, fallback_name: str = "") -> str:
    """找"三字代码"行, 取其值 (3 字符大写)。fallback: 从城市名查 COMMON_IATA。"""
    for sec in dt.sections:
        for row in sec.rows:
            cells = row
            for i, c in enumerate(cells):
                if "三字代码" in c:
                    # 该 cell 之后的最后一个 3-字符大写值
                    for v in reversed(cells[i + 1 :]):
                        v2 = v.strip()
                        if re.match(r"^[A-Z]{3}$", v2):
                            return v2
                    # 同 cell 行内 (i 之前) 的 3 字符
                    for v in cells[:i]:
                        v2 = v.strip()
                        if re.match(r"^[A-Z]{3}$", v2):
                            return v2
            # 兜底: row 内任何 3 字符大写 (但要避开 ICAO 4 字代码)
            four_code_seen = any("四字代码" in c for c in cells)
            if four_code_seen:
                continue
            for c in reversed(cells):
                c2 = c.strip()
                if re.match(r"^[A-Z]{3}$", c2):
                    return c2
    # fallback: 从城市名查
    if fallback_name and fallback_name in COMMON_IATA:
        return COMMON_IATA[fallback_name]
    return ""


def _extract_region(dt: DocxTable) -> str:
    """找"省份/地区"或"国家/地区"行, 取国家/省份映射大区。

    表格布局: cell[0]='机场信息'(section 标签), cell[1]='国家/地区'(key),
    cell[2]='荷兰/阿姆斯特丹'(value), cell[3]='四字代码'(key), cell[4]='EHAM'(value)
    """
    for sec in dt.sections:
        for row in sec.rows:
            cells = row
            # 找包含 "国家/地区" 或 "省份/地区" 的 cell, 取它之后的非空 cell 作为 value
            for i, c in enumerate(cells):
                if "国家/地区" in c or "省份/地区" in c:
                    for v in cells[i + 1 :]:
                        v = v.strip()
                        if v:
                            if "/" in v:
                                head = v.split("/")[0].strip()
                                return region_from_name(head)
                            return region_from_name(v)
    return "国际-亚洲"


def _extract_fleet(dt: DocxTable) -> list[dict]:
    """执飞机型: 找 '吉祥执飞' section, 解析机型行。

    行格式: ['吉祥执飞', 'B787', '√', '√', '×'] 或 ['吉祥执飞', 'B787', '√', '√', '√', '√']
    列: 类型 / 短停 / 短停2 / 航后 / 航后2 (有重复是 docx 合并列导致)
    """
    sec = _find_section(dt, "吉祥执飞", "执飞")
    if not sec:
        return []
    fleet: list[dict] = []
    for row in sec.rows[1:]:  # skip header
        if len(row) < 2:
            continue
        model = row[1].strip()
        if not model or model in ("类型",):
            continue
        # 短停/航后: 找有 √ 的列
        flags = [c.strip() for c in row[2:]]
        # 去重连续相同
        dedup: list[str] = []
        for f in flags:
            if not dedup or dedup[-1] != f:
                dedup.append(f)
        # dedup 后: [短停/√, 短停/√, 航后/√, 航后/√]
        # 短停 = 第一个非空 (只要有一个 √)
        short_stay = "√" in dedup[: max(1, len(dedup) // 2)]
        after = "√" in dedup[len(dedup) // 2 :] if dedup else False
        fleet.append({"model": model, "short_stay": short_stay, "after": after})
    return fleet


def _extract_parts(dt: DocxTable) -> list[dict]:
    """航材清单: 找 '航材保障预案' section。"""
    sec = _find_section(dt, "航材保障预案", "航材清单")
    if not sec:
        return []
    parts: list[dict] = []
    for row in sec.rows[1:]:
        if len(row) < 3:
            continue
        name = row[1].strip()
        if not name or name == "航材清单":
            continue
        pn = row[2].strip() if len(row) > 2 else ""
        stock_cell = row[3].strip() if len(row) > 3 else ""
        # 库存: √ → 1, × → 0, 数字 → 数字
        if "√" in stock_cell:
            stock = 1
        elif "×" in stock_cell or "x" in stock_cell.lower():
            stock = 0
        else:
            try:
                stock = int(stock_cell)
            except ValueError:
                stock = 0
        # 库存 unit 默认 "个"
        parts.append({"pn": pn or "—", "name": name, "stock": stock, "unit": "个"})
    return parts


def _extract_contacts(dt: DocxTable) -> list[dict]:
    """联系人: 找 '当地及周边资源' section。

    行格式: ['东航', '东航上海总部 AOG', '东航上海总部 AOG', '互援', '021-22379771...']
    """
    sec = _find_section(dt, "当地及周边资源", "联系人", "周边资源")
    if not sec:
        return []
    contacts: list[dict] = []
    for row in sec.rows[1:]:
        if len(row) < 4:
            continue
        org = row[0].strip()
        if not org or org in ("机队规模及备注",):
            continue
        scope = row[1].strip()
        method = row[-2].strip() if len(row) >= 2 else ""
        phone_str = row[-1].strip() if len(row) >= 1 else ""
        # 抽 phone
        phones = re.findall(r"[\d\-\+\s\(\)]{7,}", phone_str)
        phones = [re.sub(r"\s+", " ", p).strip() for p in phones]
        # email
        email_match = re.search(r"[\w\.\-]+@[\w\.\-]+\.[a-zA-Z]{2,}", phone_str)
        email = email_match.group(0) if email_match else None
        contact: dict = {
            "org": org,
            "phone": phones[:3] if phones else [],
            "role": method or "7×24",
        }
        if email:
            contact["email"] = email
        contacts.append(contact)
    return contacts


def _extract_warehouse(dt: DocxTable) -> dict:
    """仓储单位 / 营业部 section。"""
    sec = _find_section(dt, "仓储单位", "营业部", "仓储")
    if not sec or not sec.rows:
        return {"location": "", "main": []}
    location = ""
    mains: list[str] = []
    for row in sec.rows[1:]:
        cells = [c for c in row[1:] if c]
        if not cells:
            continue
        if "地址" in row[0] or "地址" in row[1] if len(row) > 1 else False:
            location = cells[1] if len(cells) > 1 else cells[0]
        else:
            mains.extend(cells)
    return {"location": location, "main": mains[:5]}


def _extract_logistics(dt: DocxTable) -> dict:
    """物流运输 section: 空运/陆运/海运/铁路。"""
    sec = _find_section(dt, "物流运输", "物流", "运输")
    if not sec:
        return {"rail": "", "air": "", "road": ""}
    out = {"rail": "", "air": "", "road": ""}
    for row in sec.rows[1:]:
        if len(row) < 2:
            continue
        key = row[1].strip()
        val = row[2].strip() if len(row) > 2 else ""
        if not key or key in ("类型",):
            continue
        if "空" in key or "航" in key:
            out["air"] = val
        elif "铁" in key:
            out["rail"] = val
        elif "陆" in key or "公" in key or "路" in key:
            out["road"] = val
        elif "海" in key:
            out["rail"] = (out.get("rail", "") + " | 海运: " + val).strip(" |")
    return out


# ---------- Main extract ----------

def extract_city(path: PathLike, knowledge_base_root: PathLike | None = None) -> City:
    """从 docx 抽 City 完整字段。

    knowledge_base_root: 用于算 source_path 相对路径。如果不传, 用 path 自身的相对部分。
    """
    p = Path(path)
    if p.suffix.lower() != ".docx":
        raise ValueError(f"City extract 需要 .docx: {p}")

    code, name, status, _ = parse_code_and_status(p.name)
    dt = parse_docx(p)
    md_text = docx_table_to_markdown(dt)

    airport = _extract_airport(dt)
    iata = _extract_iata(dt, fallback_name=name)
    region = _extract_region(dt)
    fleet = _extract_fleet(dt)
    parts = _extract_parts(dt)
    contacts = _extract_contacts(dt)
    warehouse = _extract_warehouse(dt)
    logistics = _extract_logistics(dt)

    # source_path
    if knowledge_base_root:
        try:
            source_path = str(p.relative_to(knowledge_base_root))
        except ValueError:
            source_path = str(p)
    else:
        source_path = str(p)

    # tags
    tags: list[str] = ["AOG预案"]
    if iata and iata != "—":
        tags.append(iata)
    if "国际" in region:
        tags.append("国际站")
    else:
        tags.append("国内站")
    if status == "现行":
        tags.append("24h响应")

    return City(
        code=code,
        name=name,
        airport=airport,
        iata=iata or "—",
        pinyin=pinyin_of(name),
        region=region,
        status=status,
        tags=tags,
        fleet=fleet,
        parts=parts,
        contacts=contacts,
        warehouse=warehouse,
        logistics=logistics,
        content_md=md_text,
        source_path=source_path,
        updated_at=datetime.now(timezone.utc).isoformat(),
    )
