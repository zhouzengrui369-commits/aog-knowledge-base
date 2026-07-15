// 共享 slugify 工具（无 client 依赖，server + client 都可用）
export function slugify(s: string): string {
  return s
    .replace(/[一二三四五六七八九十]+、?\s*/g, "")
    .replace(/[^\w\u4e00-\u9fa5]+/g, "-")
    .toLowerCase()
    .slice(0, 30);
}
