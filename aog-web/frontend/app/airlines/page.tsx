import type { Metadata } from "next";
import { NavBar } from "@/components/nav-bar";
import { AirlinesClient } from "./list-client";

export const metadata: Metadata = {
  title: "航司互援资源",
  description: "中国主要航司 · 基地机场 / 机队规模 / 联盟 / AOG 联系方式",
};

export default function AirlinesPage() {
  return (
    <>
      <NavBar active="airlines" />
      <AirlinesClient />
    </>
  );
}
