import { slugify } from "@/lib/slugify";
import type { ExperienceContent } from "@/lib/types";

interface Props {
  sections: ExperienceContent[];
}

/** 经验正文渲染 — 来自 mockup 的结构化 content 数组 */
export function ExperienceContentView({ sections }: Props) {
  if (!sections || sections.length === 0) {
    return (
      <p className="text-ink-500">
        该经验暂无详细内容，可参考相关经验或联系 AOG 中心获取完整版。
      </p>
    );
  }
  return (
    <div className="exp-content">
      {sections.map((sec, i) => {
        const id = `h-${slugify(sec.h)}`;
        return (
          <section key={i}>
            <h2 id={id}>{sec.h}</h2>
            {sec.type === "list" ? (
              <ul>
                {(sec.items || []).map((item, j) => (
                  <li key={j}>{item}</li>
                ))}
              </ul>
            ) : (
              <p>{sec.text}</p>
            )}
          </section>
        );
      })}
    </div>
  );
}
