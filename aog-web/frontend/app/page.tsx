import { NavBar } from "@/components/nav-bar";
import { Hero } from "@/components/hero";
import { HomeData } from "./home-data";

export default function HomePage() {
  return (
    <>
      <NavBar active="home" />
      <Hero />
      <HomeData />
    </>
  );
}
