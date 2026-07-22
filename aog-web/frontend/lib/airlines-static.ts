// 航司静态数据 (SSG 阶段 import 用于 generateStaticParams)
// 数据源: aog-web/functions/aog-api/data/airlines.json (Sprint C)
// 编译时 inline, build 时被打入 bundle

import type { Airline } from "@/lib/types";

export const AIRLINES_STATIC: Pick<Airline, "iata" | "name_cn" | "name_en" | "name_short">[] = [
  { iata: "CA", name_cn: "中国国际航空", name_en: "Air China", name_short: "国航" },
  { iata: "MU", name_cn: "中国东方航空", name_en: "China Eastern Airlines", name_short: "东航" },
  { iata: "CZ", name_cn: "中国南方航空", name_en: "China Southern Airlines", name_short: "南航" },
  { iata: "HU", name_cn: "海南航空", name_en: "Hainan Airlines", name_short: "海航" },
  { iata: "MF", name_cn: "厦门航空", name_en: "Xiamen Airlines", name_short: "厦航" },
  { iata: "3U", name_cn: "四川航空", name_en: "Sichuan Airlines", name_short: "川航" },
  { iata: "ZH", name_cn: "深圳航空", name_en: "Shenzhen Airlines", name_short: "深航" },
  { iata: "SC", name_cn: "山东航空", name_en: "Shandong Airlines", name_short: "山航" },
  { iata: "9C", name_cn: "春秋航空", name_en: "Spring Airlines", name_short: "春秋" },
  { iata: "HO", name_cn: "吉祥航空", name_en: "Juneyao Airlines", name_short: "吉祥" },
  { iata: "G5", name_cn: "华夏航空", name_en: "China Express Airlines", name_short: "华夏" },
  { iata: "JD", name_cn: "首都航空", name_en: "Capital Airlines", name_short: "首都航" },
  { iata: "PN", name_cn: "西部航空", name_en: "West Air", name_short: "西部" },
  { iata: "DZ", name_cn: "东海航空", name_en: "Donghai Airlines", name_short: "东海" },
  { iata: "BK", name_cn: "奥凯航空", name_en: "Okay Airways", name_short: "奥凯" },
  { iata: "KN", name_cn: "中国联合航空", name_en: "China United Airlines", name_short: "联航" },
  { iata: "A6", name_cn: "红土航空", name_en: "Hongtu Airlines", name_short: "红土" },
  { iata: "DR", name_cn: "瑞丽航空", name_en: "Ruili Airlines", name_short: "瑞丽" },
  { iata: "GY", name_cn: "多彩贵州航空", name_en: "Colorful Guizhou Airlines", name_short: "多彩" },
  { iata: "JR", name_cn: "幸福航空", name_en: "Joy Air", name_short: "幸福" },
  { iata: "8L", name_cn: "祥鹏航空", name_en: "Lucky Air", name_short: "祥鹏" },
  { iata: "GX", name_cn: "北部湾航空", name_en: "GX Airlines", name_short: "北部湾" },
  { iata: "GS", name_cn: "天津航空", name_en: "Tianjin Airlines", name_short: "天津航" },
  { iata: "NS", name_cn: "河北航空", name_en: "Hebei Airlines", name_short: "河北" },
  { iata: "9D", name_cn: "江西航空", name_en: "Jiangxi Air", name_short: "江西" },
];
