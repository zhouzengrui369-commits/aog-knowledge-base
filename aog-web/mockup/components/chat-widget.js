// ChatWidget — AOG AI 助手
// Self-contained: injects styles + DOM, exposes window.AOGChat
(function () {
  if (window.AOGChat) return;

  const SUGGESTIONS = [
    'B787 风挡 AOG 怎么处理？',
    '浦东 AOG 联系人？',
    'BMS9-3 玻璃纤维布哪里备？'
  ];

  // 真实感 mock 回复 — 引用必须 ≥ 1 个真实文档
  function mockAnswer(q) {
    const norm = q.trim();
    if (/B787.*风挡|风挡.*B787/i.test(norm)) {
      return {
        text: [
          'B787 风挡 AOG 一般按以下步骤处理：',
          '1. **现场评估**：机务登机检查裂纹 / 破损范围，对照 AMM 56-10-11 判定放行 / 保留 / 停场；',
          '2. **备件调度**：B787-8 风挡常见件号 8AG1841-1 / 8AG1841-3，浦东主基地常备，可 4h 内直飞大兴或白云；',
          '3. **更换施工**：拆装需在机库 / 防风棚内完成，使用 BQG-1 密封胶 + BQ-1 底涂（参考 AMM 56-10-21）；',
          '4. **测试放行**：风挡加温功能测试 + 结构完整性 + 雷击保护三项通过后由值班放行工程师签字。',
          '若现场无备件，可启用 Satair 国际件库从香港 HAECO 中转，4-6h 通关。'
        ].join('\n'),
        refs: [
          { title: 'B787 风挡 AOG 处理流程',        href: 'experience.html#b787-windshield-aog' },
          { title: 'AOG 保障工作流 R1',             href: 'experience.html#aog-workflow-r1' },
          { title: 'B-北京大兴（航材库 / 联系人）', href: 'city.html#B-北京大兴' }
        ]
      };
    }
    if (/浦东|上海/i.test(norm)) {
      return {
        text: [
          '上海浦东 AOG 保障主要联系方式：',
          '• **东航上海总部 AOG（7×24）**：021-22379771 / 79772 / 79773，邮箱 aog-desk@ceair.com，互援；',
          '• **国航上海基地**：021-62575300，邮箱 aog-sha@airchina.com，中介；',
          '• **吉祥自营浦东主基地**：021-61828888 转 AOG 值班（详见内部通讯录）。',
          '库房位于浦东机场东航机务区航材库，主力件常备 B787 主轮 C20649000、A320 主轮 C20195162。'
        ].join('\n'),
        refs: [
          { title: 'S-上海浦东（航材库 / 联系人）', href: 'city.html#S-上海浦东' },
          { title: 'AOG 保障工作流 R1',             href: 'experience.html#aog-workflow-r1' }
        ]
      };
    }
    if (/BMS9-3|玻璃纤维布/i.test(norm)) {
      return {
        text: [
          'BMS9-3 系列玻璃纤维布库存分布：',
          '• **上海浦东**：Type I / II / III 全规格常备，单卷 50m；',
          '• **北京大兴**：Type I / II 库存，Type III 协议保障 24h 到货；',
          '• **广州白云**：Type I / II 库存；',
          '• **国际备援**：HAECO 香港 / Satair 新加坡 48h 通关。',
          '施工注意：戴防割手套 + N95 口罩（玻璃纤维致敏），粘接用 BMS9-3 配套底胶 Adhesive 49，固化 24h。'
        ].join('\n'),
        refs: [
          { title: 'BMS9-3 系列玻璃纤维布的保障经验', href: 'experience.html#bms9-3-fiberglass' },
          { title: 'S-上海浦东（航材库）',             href: 'city.html#S-上海浦东' }
        ]
      };
    }
    // 默认回复
    return {
      text: '暂未在知识库中匹配到「' + norm + '」的相关文档。请尝试更具体的关键词，例如「B787 风挡」「浦东 联系人」「BMS9-3 备件」。\n\n也可以试试：\n• 北京大兴进场保障\n• 米兰取件经验\n• 西兰郑铁路运输',
      refs: [
        { title: 'AOG 保障工作流 R1', href: 'experience.html#aog-workflow-r1' },
        { title: 'B-北京大兴',         href: 'city.html#B-北京大兴' },
        { title: '保障经验列表',       href: 'experiences.html' }
      ]
    };
  }

  function el(html) {
    const t = document.createElement('template');
    t.innerHTML = html.trim();
    return t.content.firstChild;
  }

  function render() {
    // Floating button
    const btn = el(`
      <button id="aogChatBtn" type="button"
        class="fixed bottom-5 right-5 z-40 grid h-14 w-14 place-items-center rounded-full bg-primary text-white shadow-pop transition hover:scale-105 hover:bg-primary-700 sm:bottom-6 sm:right-6"
        aria-label="打开 AI 助手">
        <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 8V4H8"/><rect width="16" height="12" x="4" y="8" rx="2"/><path d="M2 14h2"/><path d="M20 14h2"/><path d="M15 13v2"/><path d="M9 13v2"/></svg>
        <span class="absolute -top-1 -right-1 grid h-5 w-5 place-items-center rounded-full bg-warning text-[10px] font-bold text-white ring-2 ring-white">AI</span>
      </button>
    `);

    // Panel
    const panel = el(`
      <div id="aogChatPanel"
        class="fixed inset-0 z-50 hidden bg-white sm:inset-auto sm:bottom-6 sm:right-6 sm:h-[640px] sm:max-h-[80vh] sm:w-[420px] sm:rounded-2xl sm:border sm:border-ink-100 sm:shadow-pop"
        role="dialog" aria-label="AOG AI 助手">
        <!-- header -->
        <div class="flex items-center justify-between border-b border-ink-100 bg-gradient-to-r from-primary to-primary-700 px-4 py-3 sm:rounded-t-2xl">
          <div class="flex items-center gap-2">
            <div class="grid h-8 w-8 place-items-center rounded-lg bg-white/15 text-white">
              <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 8V4H8"/><rect width="16" height="12" x="4" y="8" rx="2"/><path d="M2 14h2"/><path d="M20 14h2"/><path d="M15 13v2"/><path d="M9 13v2"/></svg>
            </div>
            <div class="leading-tight">
              <div class="text-sm font-semibold text-white">AI 助手</div>
              <div class="text-[10px] text-white/70">MiniMax M3 · Mock</div>
            </div>
          </div>
          <button id="aogChatClose" class="grid h-8 w-8 place-items-center rounded-md text-white/80 hover:bg-white/10 hover:text-white" aria-label="关闭">
            <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 6 6 18"/><path d="m6 6 12 12"/></svg>
          </button>
        </div>
        <!-- messages -->
        <div id="aogChatMsgs" class="flex-1 space-y-3 overflow-y-auto bg-ink-50/50 px-4 py-4 sm:h-[460px]"></div>
        <!-- suggestions -->
        <div id="aogChatSugg" class="border-t border-ink-100 bg-white px-3 py-2 sm:rounded-b-2xl">
          <div class="mb-1 text-[10px] text-ink-500">试试这些问题：</div>
          <div class="flex flex-wrap gap-1.5" id="aogChatSuggList"></div>
        </div>
        <!-- input -->
        <form id="aogChatForm" class="flex items-center gap-2 border-t border-ink-100 bg-white px-3 py-3 sm:rounded-b-2xl">
          <input id="aogChatInput" type="text" placeholder="输入你的 AOG 问题…" autocomplete="off"
            class="flex-1 rounded-md border border-ink-100 bg-ink-50 px-3 py-2 text-sm placeholder:text-ink-500 focus:border-primary focus:bg-white focus:outline-none focus:ring-2 focus:ring-primary/20" />
          <button type="submit" class="grid h-9 w-9 place-items-center rounded-md bg-primary text-white hover:bg-primary-700" aria-label="发送">
            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m22 2-7 20-4-9-9-4Z"/><path d="M22 2 11 13"/></svg>
          </button>
        </form>
      </div>
    `);

    document.body.appendChild(btn);
    document.body.appendChild(panel);

    // Suggestions
    const list = panel.querySelector('#aogChatSuggList');
    SUGGESTIONS.forEach(s => {
      const b = el(`<button type="button" class="rounded-full border border-ink-100 bg-ink-50 px-2.5 py-1 text-[11px] text-ink-700 hover:border-primary hover:bg-primary-50 hover:text-primary">${s}</button>`);
      b.addEventListener('click', () => ask(s));
      list.appendChild(b);
    });

    // Open / close
    const open = () => {
      panel.classList.remove('hidden');
      btn.classList.add('hidden');
      // ensure welcome message if empty
      if (!panel.querySelector('#aogChatMsgs').children.length) {
        addMsg('assistant', '你好，我是 AOG AI 助手。可以问我城市预案、备件库存、保障经验等问题，每个回答都会附带真实文档引用。', []);
        renderSuggestions();
      }
      setTimeout(() => panel.querySelector('#aogChatInput').focus(), 50);
    };
    const close = () => {
      panel.classList.add('hidden');
      btn.classList.remove('hidden');
    };
    btn.addEventListener('click', open);
    panel.querySelector('#aogChatClose').addEventListener('click', close);

    // Send
    function ask(q) {
      if (!q || !q.trim()) return;
      addMsg('user', q);
      panel.querySelector('#aogChatInput').value = '';
      // hide suggestions after first user msg
      const sg = panel.querySelector('#aogChatSugg');
      if (sg) sg.classList.add('hidden');
      // loading
      const loadingId = 'loading-' + Date.now();
      addMsg('assistant', '<span class="inline-flex items-center gap-1"><span class="h-1.5 w-1.5 animate-bounce rounded-full bg-ink-500"></span><span class="h-1.5 w-1.5 animate-bounce rounded-full bg-ink-500 [animation-delay:120ms]"></span><span class="h-1.5 w-1.5 animate-bounce rounded-full bg-ink-500 [animation-delay:240ms]"></span></span>', [], loadingId);
      setTimeout(() => {
        const ans = mockAnswer(q);
        // remove loading
        const ld = document.getElementById(loadingId);
        if (ld) ld.remove();
        addMsg('assistant', formatText(ans.text), ans.refs);
        scrollBottom();
      }, 700);
    }

    function formatText(s) {
      // very small markdown: **bold** + \n -> <br>
      return s
        .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
        .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
        .replace(/\n/g, '<br>');
    }

    function addMsg(role, html, refs, id) {
      const msgs = panel.querySelector('#aogChatMsgs');
      const wrap = el(`<div class="flex ${role === 'user' ? 'justify-end' : 'justify-start'}" ${id ? `id="${id}"` : ''}></div>`);
      const bubble = el(`<div class="max-w-[85%] rounded-2xl px-3.5 py-2.5 text-sm leading-relaxed ${role === 'user' ? 'rounded-tr-sm bg-primary text-white' : 'rounded-tl-sm border border-ink-100 bg-white text-ink-900'}"></div>`);
      bubble.innerHTML = html;
      wrap.appendChild(bubble);
      if (role === 'assistant' && refs && refs.length) {
        const refBox = el(`<div class="mt-1.5 max-w-[85%] rounded-2xl rounded-tl-sm border border-ink-100 bg-white px-3.5 py-2 text-[11px]"></div>`);
        refBox.innerHTML = `
          <div class="mb-1 flex items-center gap-1 text-ink-500">
            <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/></svg>
            参考资料
          </div>
          <ul class="space-y-0.5">
            ${refs.map(r => `<li><a href="${r.href}" class="text-primary hover:underline">${r.title}</a></li>`).join('')}
          </ul>`;
        wrap.appendChild(refBox);
      }
      msgs.appendChild(wrap);
      scrollBottom();
    }

    function renderSuggestions() {
      const sg = panel.querySelector('#aogChatSugg');
      if (sg) sg.classList.remove('hidden');
    }

    function scrollBottom() {
      const msgs = panel.querySelector('#aogChatMsgs');
      msgs.scrollTop = msgs.scrollHeight;
    }

    panel.querySelector('#aogChatForm').addEventListener('submit', (e) => {
      e.preventDefault();
      const v = panel.querySelector('#aogChatInput').value;
      ask(v);
    });

    // expose
    window.AOGChat = { open, close, ask };
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', render);
  } else {
    render();
  }
})();
