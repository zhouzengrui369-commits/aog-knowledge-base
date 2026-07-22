// 航司 mock 数据 — 3 个, 供 dev 模式 / SCF 离线 / SSG 静态导出 fallback
// 与 functions/aog-api/data/airlines.json schema 1:1 对齐 (Sprint C)

import type { Airline } from "@/lib/types";

export const MOCK_AIRLINES: Airline[] = [
  {
    iata: "CA",
    icao: "CCA",
    name_cn: "中国国际航空",
    name_short: "国航",
    name_en: "Air China",
    hubs: [
      { city_code: "B-北京大兴", iata: "PKX", type: "hub", note: "国际枢纽" },
      { city_code: "B-北京首都（暂停）", iata: "PEK", type: "hub", note: "原主基地" },
    ],
    fleet_size: 491,
    alliance: "星空联盟",
    headquarters: "北京市顺义区天竺空港工业区",
    website: "www.airchina.com.cn",
    aog_contact: { phone: "010-64537139", email: "aogoffice@airchina.com" },
    data_source: "mock",
    verified: true,
    verified_at: "2026-07-22",
  },
  {
    iata: "MU",
    icao: "CES",
    name_cn: "中国东方航空",
    name_short: "东航",
    name_en: "China Eastern Airlines",
    hubs: [
      { city_code: null, iata: "PVG", type: "hub", note: "上海浦东" },
    ],
    fleet_size: 595,
    alliance: "天合联盟",
    headquarters: "上海",
    website: "www.ceair.com",
    aog_contact: { phone: "021-22379771", email: "aog-desk@ceair.com" },
    data_source: "mock",
    verified: true,
    verified_at: "2026-07-22",
  },
  {
    iata: "CZ",
    icao: "CSN",
    name_cn: "中国南方航空",
    name_short: "南航",
    name_en: "China Southern Airlines",
    hubs: [
      { city_code: "G-广州", iata: "CAN", type: "hub", note: "主基地" },
    ],
    fleet_size: 860,
    alliance: "天合联盟",
    headquarters: "广州",
    website: "www.csair.com",
    aog_contact: { phone: "020-86138428", email: "aog@csair.com" },
    data_source: "mock",
    verified: true,
    verified_at: "2026-07-22",
  },
];
