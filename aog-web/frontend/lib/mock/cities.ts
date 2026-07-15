// Mock 城市数据 — 字段 1:1 来自 aog-web/mockup/data/cities.js
// 真实数据来源: /Users/njx/Project/AOG知识库/AOG知识库/02_外战预案/
// 当前 mockup 阶段收录 30 个城市（4 个 featured 含完整数据，26 个仅基础字段）
// 后端 T1 启动后此文件作为 fallback 兜底

import type { City } from "@/lib/types";

export const MOCK_CITIES: City[] = [
  // ----- Featured (full content) -----
  {
    code: "B-北京大兴",
    name: "北京大兴",
    region: "华北",
    status: "active",
    iata: "PKX",
    pinyin: "beijingdaxing",
    summary:
      "国际枢纽航站，AOG 备件 24h 响应。北京大兴国际机场为吉祥航空 A320/A321 短停基地，航材保障覆盖前轮/主轮/滑油/液压油等关键件。",
    airport: "北京大兴国际机场",
    airport_obj: { name: "北京大兴国际机场", code: "PKX", province: "北京市" },
    tags: ["AOG预案", "国际枢纽", "24h响应"],
    fleet: [
      { model: "B787", short_stay: false, after: false },
      { model: "A320", short_stay: true, after: false },
      { model: "A321", short_stay: true, after: false },
    ],
    parts_mockup: [
      { name: "前轮", pn: "3-1531-3", stock: true, note: "自我保障" },
      { name: "A320 主轮", pn: "C20195162", stock: false, note: "求援国航/南航/东航/海航" },
      { name: "A321 主轮", pn: "C20500100", stock: true, note: "自我保障" },
      { name: "B787 前轮", pn: "C20598000", stock: false, note: "自我保障" },
      { name: "B787 主轮", pn: "C20649000", stock: false, note: "自我保障" },
      { name: "滑油", pn: "EASTMAN#TO#2197", stock: true, note: "自我保障" },
      { name: "液压油", pn: "HYJET#V#GAL", stock: false, note: "液压油协议由东航保障，也可视情求援国航/海航/南航" },
      { name: "其他航材", pn: "—", stock: false, note: "视情求援国航/东航/海航/南航" },
    ],
    contacts_mockup: [
      { org: "东航", scope: "东航北京基地，配有 A320、A321 资源", method: "互援", phone: "021-22379771/79772/79773", email: "aog-desk@ceair.com" },
      { org: "国航", scope: "国航北京总基地，配有 A320、A321 资源", method: "中介", phone: "010-64537139", email: "aogoffice@airchina.com" },
      { org: "南航", scope: "南航北京基地，配有 A320、A321 资源", method: "互援", phone: "020-86138428 / 86138730 / 13924136820", email: "aogcsn@csair.com" },
      { org: "海航（首都航）", scope: "海航北京基地，配有 A320、A321 资源", method: "中介", phone: "010-57817323", email: "aogdesk-pek@hnair.com" },
      { org: "空客北京", scope: "Satair Group", method: "点对点", contact: "Pei Shi 石培 · Account Director", phone: "+86 10 6148 7915 / +86 186 0086 6651", email: "SPE@satair.com" },
    ],
    warehouse_mockup: {
      name: "北京大兴国际机场东航机务区航材库房",
      address: "北京大兴国际机场东航机务区航材库房",
      phone: "库房电话 15311975805",
      owners: "东航北京负责人李伟男 13910301946；东航上海商务徐涛 189 3090 6700",
    },
    logistics_mockup: [
      { type: "公路", note: "京津冀 4h 圈覆盖；可用自有车辆 / 协议货代" },
      { type: "航空", note: "国内 6h 跨城直飞，首都/大兴双场互转" },
      { type: "铁路", note: "京广 / 京沪高铁货运动车组可行" },
    ],
    content_md: "# 北京大兴国际机场 AOG 应急保障预案\n\n## 一、机场信息\n- 名称：北京大兴国际机场\n- 三字代码：PKX\n- 地区：北京市 / 华北\n- 状态：现行\n\n## 二、执飞机型\n- B787（航后非短停）\n- A320（短停）\n- A321（短停）\n\n## 三、航材保障\n主力备件覆盖前轮/主轮/滑油/液压油等关键件。",
    updated_at: "2026-04-15",
  },
  {
    code: "S-上海浦东",
    name: "上海浦东",
    region: "华东",
    status: "active",
    iata: "PVG",
    pinyin: "shanghaipudong",
    summary: "国内最大国际枢纽，常备波音/空客件。浦东是吉祥主基地之一，浦东 / 虹桥双场联动保障。",
    airport: "上海浦东国际机场",
    airport_obj: { name: "上海浦东国际机场", code: "PVG", province: "上海市" },
    tags: ["AOG预案", "国际枢纽", "主基地"],
    fleet: [
      { model: "B787", short_stay: true, after: true },
      { model: "A320", short_stay: true, after: true },
      { model: "A321", short_stay: true, after: true },
    ],
    parts_mockup: [
      { name: "B787 主轮", pn: "C20649000", stock: true, note: "主基地常备" },
      { name: "A320 主轮", pn: "C20195162", stock: true, note: "主基地常备" },
      { name: "前轮", pn: "3-1531-3", stock: true, note: "自我保障" },
      { name: "滑油", pn: "EASTMAN#TO#2197", stock: true, note: "协议保障" },
      { name: "液压油", pn: "HYJET#V#GAL", stock: true, note: "协议保障" },
    ],
    contacts_mockup: [
      { org: "东航", scope: "东航上海总部，AOG 7×24", method: "互援", phone: "021-22379771/79772/79773", email: "aog-desk@ceair.com" },
      { org: "国航", scope: "国航上海基地", method: "中介", phone: "021-62575300", email: "aog-sha@airchina.com" },
      { org: "吉祥自营", scope: "浦东主基地 AOG 值班", method: "内部", phone: "详见内部通讯录 / 021-61828888" },
    ],
    warehouse_mockup: {
      name: "浦东机场东航机务区航材库",
      address: "上海浦东国际机场东机坪区",
      phone: "021-68888888 转 AOG",
      owners: "浦东值班经理（内部通讯录）",
    },
    logistics_mockup: [
      { type: "公路", note: "长三角 4h 圈；自有车辆 + 协议货代" },
      { type: "航空", note: "国际-国内中转 4h 通关" },
      { type: "铁路", note: "沪宁 / 沪杭高铁货运动车组" },
    ],
    content_md: "# 上海浦东 AOG 应急保障预案\n\n## 一、机场信息\n- 名称：上海浦东国际机场\n- 三字代码：PVG\n- 地区：上海市 / 华东\n- 状态：现行\n\n## 二、执飞机型\n- B787（短停 + 航后）\n- A320（短停 + 航后）\n- A321（短停 + 航后）\n\n## 三、航材保障\n浦东主基地常备 B787 主轮、A320 主轮、前轮、滑油、液压油。",
    updated_at: "2026-04-15",
  },
  {
    code: "G-广州白云",
    name: "广州白云",
    region: "华南",
    status: "active",
    iata: "CAN",
    pinyin: "guangzhoubaiyun",
    summary: "东南亚枢纽，AOG 经验丰富。白云机场是吉祥华南主基地，A320/A321 高频运行。",
    airport: "广州白云国际机场",
    airport_obj: { name: "广州白云国际机场", code: "CAN", province: "广东省" },
    tags: ["AOG预案", "东南亚枢纽", "主基地"],
    fleet: [
      { model: "B787", short_stay: true, after: false },
      { model: "A320", short_stay: true, after: true },
      { model: "A321", short_stay: true, after: true },
    ],
    parts_mockup: [
      { name: "前轮", pn: "3-1531-3", stock: true, note: "自我保障" },
      { name: "A320 主轮", pn: "C20195162", stock: true, note: "主基地常备" },
      { name: "A321 主轮", pn: "C20500100", stock: false, note: "求援南航/东航" },
      { name: "滑油", pn: "EASTMAN#TO#2197", stock: true, note: "自我保障" },
    ],
    contacts_mockup: [
      { org: "南航", scope: "南航广州总部", method: "互援", phone: "020-86138428/86138730", email: "aogcsn@csair.com" },
      { org: "东航", scope: "东航华南基地", method: "互援", phone: "021-22379771/79772/79773", email: "aog-desk@ceair.com" },
      { org: "九元航", scope: "九元航空 AOG", method: "互援", phone: "020-22008888" },
    ],
    warehouse_mockup: {
      name: "白云机场南航机务区航材库",
      address: "广州白云国际机场南航机务区",
      phone: "020-86123456",
      owners: "南航 AOG 值班 / 吉祥华南负责人",
    },
    logistics_mockup: [
      { type: "公路", note: "珠三角 3h 圈；港珠澳陆运 5h" },
      { type: "航空", note: "东南亚 4h 航程覆盖" },
      { type: "海运", note: "粤港澳驳船 24h 通关" },
    ],
    content_md: "# 广州白云 AOG 应急保障预案\n\n## 一、机场信息\n- 名称：广州白云国际机场\n- 三字代码：CAN\n- 地区：广东省 / 华南\n- 状态：现行\n\n## 二、执飞机型\n- B787（短停）\n- A320（短停 + 航后）\n- A321（短停 + 航后）\n\n## 三、航材保障\nA320 主轮常备，A321 主轮求援南航/东航。",
    updated_at: "2026-04-15",
  },
  {
    code: "H-香港",
    name: "香港",
    region: "华南",
    status: "active",
    iata: "HKG",
    pinyin: "xianggang",
    summary: "国际货运转运中心。香港机场是国际 AOG 件中转核心节点，自有 + 协议件库覆盖波音/空客主流机型。",
    airport: "香港国际机场",
    airport_obj: { name: "香港国际机场", code: "HKG", province: "香港特别行政区" },
    tags: ["AOG预案", "国际货运转运", "中转枢纽"],
    fleet: [
      { model: "B787", short_stay: true, after: true },
      { model: "A320", short_stay: true, after: false },
      { model: "A321", short_stay: true, after: false },
    ],
    parts_mockup: [
      { name: "B787 主轮", pn: "C20649000", stock: true, note: "国际件库常备" },
      { name: "A320 主轮", pn: "C20195162", stock: true, note: "国际件库常备" },
      { name: "前轮", pn: "3-1531-3", stock: true, note: "协议保障" },
    ],
    contacts_mockup: [
      { org: "国泰航空", scope: "国泰港龙 AOG", method: "互援", phone: "+852 2747 8888", email: "aog@cathaypacific.com" },
      { org: "港龙", scope: "港龙航空", method: "中介", phone: "+852 3193 3838" },
      { org: "HAECO", scope: "港机工程", method: "协议", phone: "+852 2760 8000" },
    ],
    warehouse_mockup: {
      name: "香港机场国泰航材库",
      address: "香港国际机场航材区",
      phone: "+852 2747 8888",
      owners: "国泰 AOG 调度",
    },
    logistics_mockup: [
      { type: "航空", note: "国际中转 4-6h 通关" },
      { type: "陆运", note: "港珠澳陆运 5h；皇岗 / 福田 24h 通关" },
      { type: "海运", note: "国际海运驳船 12h" },
    ],
    content_md: "# 香港国际机场 AOG 应急保障预案\n\n## 一、机场信息\n- 名称：香港国际机场\n- 三字代码：HKG\n- 地区：香港特别行政区 / 华南\n- 状态：现行\n\n## 二、执飞机型\n- B787（短停 + 航后）\n- A320（短停）\n- A321（短停）",
    updated_at: "2026-04-15",
  },

  // ----- 其他城市（仅基础字段，详情在生产数据库） -----
  { code: "A-澳门", name: "澳门", region: "华南", status: "active", iata: "MFM", airport: "澳门国际机场", summary: "" },
  { code: "B-北京首都", name: "北京首都", region: "华北", status: "paused", iata: "PEK", airport: "北京首都国际机场", summary: "" },
  { code: "C-成都天府", name: "成都天府", region: "西南", status: "active", iata: "TFU", airport: "成都天府国际机场", summary: "" },
  { code: "C-重庆江北", name: "重庆江北", region: "西南", status: "active", iata: "CKG", airport: "重庆江北国际机场", summary: "" },
  { code: "D-大连", name: "大连", region: "东北", status: "active", iata: "DLC", airport: "大连周水子国际机场", summary: "" },
  { code: "F-福州长乐", name: "福州长乐", region: "华东", status: "active", iata: "FOC", airport: "福州长乐国际机场", summary: "" },
  { code: "G-桂林两江", name: "桂林两江", region: "华南", status: "active", iata: "KWL", airport: "桂林两江国际机场", summary: "" },
  { code: "H-杭州萧山", name: "杭州萧山", region: "华东", status: "active", iata: "HGH", airport: "杭州萧山国际机场", summary: "" },
  { code: "H-合肥新桥", name: "合肥新桥", region: "华东", status: "active", iata: "HFE", airport: "合肥新桥国际机场", summary: "" },
  { code: "H-海口美兰", name: "海口美兰", region: "华南", status: "active", iata: "HAK", airport: "海口美兰国际机场", summary: "" },
  { code: "H-哈尔滨太平", name: "哈尔滨太平", region: "东北", status: "active", iata: "HRB", airport: "哈尔滨太平国际机场", summary: "" },
  { code: "J-济南遥墙", name: "济南遥墙", region: "华东", status: "active", iata: "TNA", airport: "济南遥墙国际机场", summary: "" },
  { code: "K-昆明长水", name: "昆明长水", region: "西南", status: "active", iata: "KMG", airport: "昆明长水国际机场", summary: "" },
  { code: "L-兰州中川", name: "兰州中川", region: "西北", status: "active", iata: "LHW", airport: "兰州中川国际机场", summary: "" },
  { code: "L-连城", name: "连城", region: "华东", status: "active", iata: "LCX", airport: "连城冠豸山机场", summary: "" },
  { code: "N-南京禄口", name: "南京禄口", region: "华东", status: "active", iata: "NKG", airport: "南京禄口国际机场", summary: "" },
  { code: "N-宁波栎社", name: "宁波栎社", region: "华东", status: "active", iata: "NGB", airport: "宁波栎社国际机场", summary: "" },
  { code: "Q-青岛胶东", name: "青岛胶东", region: "华东", status: "active", iata: "TAO", airport: "青岛胶东国际机场", summary: "" },
  { code: "Q-秦皇岛", name: "秦皇岛", region: "华北", status: "active", iata: "SHP", airport: "秦皇岛北戴河机场", summary: "" },
  { code: "S-深圳宝安", name: "深圳宝安", region: "华南", status: "active", iata: "SZX", airport: "深圳宝安国际机场", summary: "" },
  { code: "S-沈阳桃仙", name: "沈阳桃仙", region: "东北", status: "active", iata: "SHE", airport: "沈阳桃仙国际机场", summary: "" },
  { code: "W-武汉天河", name: "武汉天河", region: "华中", status: "active", iata: "WUH", airport: "武汉天河国际机场", summary: "" },
  { code: "W-乌鲁木齐", name: "乌鲁木齐", region: "西北", status: "active", iata: "URC", airport: "乌鲁木齐地窝堡国际机场", summary: "" },
  { code: "X-西安咸阳", name: "西安咸阳", region: "西北", status: "active", iata: "XIY", airport: "西安咸阳国际机场", summary: "" },
  { code: "X-厦门高崎", name: "厦门高崎", region: "华东", status: "active", iata: "XMN", airport: "厦门高崎国际机场", summary: "" },
  { code: "Y-烟台蓬莱", name: "烟台蓬莱", region: "华东", status: "active", iata: "YNT", airport: "烟台蓬莱国际机场", summary: "" },
  { code: "Z-郑州新郑", name: "郑州新郑", region: "华中", status: "active", iata: "CGO", airport: "郑州新郑国际机场", summary: "" },
];

/** 全部 30 个城市（featured + 基础） */
export const ALL_CITIES = MOCK_CITIES;

/** 仅 4 个 featured 城市（首页推荐用） */
export const FEATURED_CITY_CODES = ["B-北京大兴", "S-上海浦东", "G-广州白云", "H-香港"];
