/* Japanese dictionary SPA + flashcard study + daily plan */
(() => {
  // 词典库缺失时后端返回 503。这里统一拦一次，把「加载失败」变成一句可操作的提示。
  const rawFetch = window.fetch.bind(window);
  let setupBannerShown = false;
  window.fetch = async (...args) => {
    const res = await rawFetch(...args);
    if (res.status === 503 && !setupBannerShown) {
      setupBannerShown = true;
      const banner = document.getElementById("setup-banner");
      if (banner) banner.hidden = false;
    }
    return res;
  };

  const setupBannerClose = document.getElementById("setup-banner-close");
  if (setupBannerClose) {
    setupBannerClose.addEventListener("click", () => {
      const banner = document.getElementById("setup-banner");
      if (banner) banner.hidden = true;
    });
  }

  // 启动时探一次词库状态：缺 jmdict.db 时后端返回 503，直接把提示条亮出来，
  // 不用等用户点进查词页才发现「加载失败」。
  rawFetch("/api/jlpt/counts")
    .then((res) => {
      if (res.status === 503) {
        const banner = document.getElementById("setup-banner");
        if (banner) banner.hidden = false;
      }
    })
    .catch(() => {});
  const FAV_KEY = "jmdict_favorites_v1";
  const STUDY_KEY = "jmdict_study_v1";
  const DAILY_KEY = "jmdict_daily_v1";
  const SESSION_SIZE = 20;
  const BOX_DELAYS = [0, 1, 3, 7, 14];
  const CONJ_PREF = ["ます形", "ない形", "て形", "た形", "可能形", "ば形"];

  const el = {
    search: document.getElementById("view-search"),
    detail: document.getElementById("view-detail"),
    favorites: document.getElementById("view-favorites"),
    study: document.getElementById("view-study"),
    q: document.getElementById("q"),
    clear: document.getElementById("btn-clear"),
    results: document.getElementById("results"),
    resultsWrap: document.getElementById("results-wrap"),
    hint: document.getElementById("search-hint"),
    detailBox: document.getElementById("detail"),
    back: document.getElementById("btn-back"),
    favList: document.getElementById("fav-list"),
    favWrap: document.getElementById("fav-wrap"),
    favEmpty: document.getElementById("fav-empty"),
    navSearch: document.getElementById("nav-search"),
    navStudy: document.getElementById("nav-study"),
    navFav: document.getElementById("nav-fav"),
    hot: document.getElementById("hot-chips"),
    grammarSection: document.getElementById("grammar-section"),
    grammarList: document.getElementById("grammar-list"),
    studyHome: document.getElementById("study-home"),
    studySession: document.getElementById("study-session"),
    studyEnd: document.getElementById("study-end"),
    studySources: document.getElementById("study-sources"),
    studyHomeHint: document.getElementById("study-home-hint"),
    btnStudyStart: document.getElementById("btn-study-start"),
    flashcard: document.getElementById("flashcard"),
    fcWord: document.getElementById("fc-word"),
    fcKana: document.getElementById("fc-kana"),
    fcAccent: document.getElementById("fc-accent"),
    fcMeaning: document.getElementById("fc-meaning"),
    fcGlossZh: document.getElementById("fc-gloss-zh"),
    fcGlossEn: document.getElementById("fc-gloss-en"),
    fcGloss: document.getElementById("fc-gloss"),
    fcTap: document.getElementById("fc-tap"),
    studyBar: document.getElementById("study-bar"),
    studyProgressText: document.getElementById("study-progress-text"),
    btnKnown: document.getElementById("btn-known"),
    btnUnknown: document.getElementById("btn-unknown"),
    studyEndStats: document.getElementById("study-end-stats"),
    btnStudyAgain: document.getElementById("btn-study-again"),
    btnStudyHome: document.getElementById("btn-study-home"),
    countFav: document.getElementById("count-fav"),
    dailyLevel: document.getElementById("daily-level"),
    dailyQuota: document.getElementById("daily-quota"),
    dailyProgressText: document.getElementById("daily-progress-text"),
    dailyBar: document.getElementById("daily-bar"),
    dailySub: document.getElementById("daily-sub"),
    dailyHint: document.getElementById("daily-hint"),
    btnDailyGen: document.getElementById("btn-daily-gen"),
    btnDailyStart: document.getElementById("btn-daily-start"),
    reviewCount: document.getElementById("review-count"),
    reviewSub: document.getElementById("review-sub"),
    reviewEmpty: document.getElementById("review-empty"),
    btnReviewStart: document.getElementById("btn-review-start"),
    navExam: document.getElementById("nav-exam"),
    navGrammar: document.getElementById("nav-grammar"),
    grammarView: document.getElementById("view-grammar"),
    grammarHome: document.getElementById("grammar-home"),
    grammarDetailView: document.getElementById("view-grammar-detail"),
    grammarDetail: document.getElementById("grammar-detail"),
    grammarQ: document.getElementById("grammar-q"),
    btnGrammarClear: document.getElementById("btn-grammar-clear"),
    grammarBrowseList: document.getElementById("grammar-browse-list"),
    grammarListMeta: document.getElementById("grammar-list-meta"),
    btnGrammarMore: document.getElementById("btn-grammar-more"),
    grammarBrowseEmpty: document.getElementById("grammar-browse-empty"),
    grammarLevelChips: document.getElementById("grammar-level-chips"),
    btnGrammarBack: document.getElementById("btn-grammar-back"),
    exam: document.getElementById("view-exam"),
    examHome: document.getElementById("exam-home"),
    examSession: document.getElementById("exam-session"),
    examResult: document.getElementById("exam-result"),
    examLevel: document.getElementById("exam-level"),
    examList: document.getElementById("exam-list"),
    examEmpty: document.getElementById("exam-empty"),
    examTitle: document.getElementById("exam-title"),
    examProgressText: document.getElementById("exam-progress-text"),
    examBar: document.getElementById("exam-bar"),
    examSubject: document.getElementById("exam-subject"),
    examPassage: document.getElementById("exam-passage"),
    examQuestion: document.getElementById("exam-question"),
    examOptions: document.getElementById("exam-options"),
    btnExamBack: document.getElementById("btn-exam-back"),
    btnExamPrev: document.getElementById("btn-exam-prev"),
    btnExamNext: document.getElementById("btn-exam-next"),
    btnExamSubmit: document.getElementById("btn-exam-submit"),
    btnExamHome: document.getElementById("btn-exam-home"),
    examResultStats: document.getElementById("exam-result-stats"),
    examResultTiming: document.getElementById("exam-result-timing"),
    examReview: document.getElementById("exam-review"),
    examHistoryList: document.getElementById("exam-history-list"),
    examHistoryEmpty: document.getElementById("exam-history-empty"),
    examMedia: document.getElementById("exam-media"),
    examAudio: document.getElementById("exam-audio"),
    examTranscript: document.getElementById("exam-transcript"),
    examSubtitle: document.getElementById("exam-subtitle"),
    examTranslation: document.getElementById("exam-translation"),
    weaknessCard: document.getElementById("weakness-card"),
    weaknessSub: document.getElementById("weakness-sub"),
    weaknessBars: document.getElementById("weakness-bars"),
    weaknessSuggestions: document.getElementById("weakness-suggestions"),
    weaknessHint: document.getElementById("weakness-hint"),
    btnWeaknessRefresh: document.getElementById("btn-weakness-refresh"),
  };

  let debounceTimer = null;
  let lastQuery = "";
  /** @type {string|null} */
  let selectedSource = null;
  /** @type {object[]} */
  let sessionQueue = [];
  let sessionIndex = 0;
  let sessionFlipped = false;
  let sessionKnown = 0;
  let sessionUnknown = 0;
  /** @type {string|null} */
  let lastSource = null;
  /** @type {"normal"|"daily"|"review"} */
  let sessionMode = "normal";

  /** AI chat state for current word (manual only — no auto on open) */
  let aiSeq = null;
  /** @type {{role:string, content:string}[]} */
  let aiHistory = [];
  let aiBusy = false;

  /** Grammar AI state (manual only) */
  /** @type {number|null} */
  let gAiId = null;
  /** @type {{role:string, content:string}[]} */
  let gAiHistory = [];
  let gAiBusy = false;

  /** Grammar browse */
  let grammarOffset = 0;
  const GRAMMAR_PAGE = 30;
  let grammarTotal = 0;
  let grammarQuery = "";
  let grammarLoading = false;
  let grammarLevel = "N2";
  /** 模考刷题 state */
  const EXAM_SUBJECT_LABEL = {
    vocabulary: "文字·词汇",
    grammar: "文法",
    reading: "读解",
    listening: "听力",
  };
  const EXAM_DRILL_SUBJECTS = new Set(["vocabulary", "grammar", "reading", "listening"]);
  let examLevel = "N2";
  /** @type {string|null} null = 整卷 */
  let examDrillSubject = null;
  let examData = null; // { objectId, title, tag, questions: [...] }
  let examIndex = 0;
  let examAnswers = []; // 每题选中的选项下标，未答为 null
  let examLoading = false;
  const EXAM_LOG_KEY = "jmdict_exam_logs_v1";
  const EXAM_LOG_CAP = 50;
  /** @type {string|null} */
  let examStartedAt = null;
  /** @type {number[]} */
  let examSeconds = [];
  /** @type {number|null} ms */
  let examQuestionEnteredAt = null;
  /** @type {string|null} */
  let examActiveSubject = null;

  function getFavs() {
    try {
      const raw = localStorage.getItem(FAV_KEY);
      const arr = raw ? JSON.parse(raw) : [];
      return Array.isArray(arr) ? arr.map(Number).filter((n) => !Number.isNaN(n)) : [];
    } catch {
      return [];
    }
  }

  function setFavs(seqs) {
    localStorage.setItem(FAV_KEY, JSON.stringify([...new Set(seqs)]));
  }

  function isFav(seq) {
    return getFavs().includes(Number(seq));
  }

  function toggleFav(seq) {
    const n = Number(seq);
    let favs = getFavs();
    if (favs.includes(n)) favs = favs.filter((x) => x !== n);
    else favs.unshift(n);
    setFavs(favs);
    return favs.includes(n);
  }

  function getStudyMap() {
    try {
      const raw = localStorage.getItem(STUDY_KEY);
      const obj = raw ? JSON.parse(raw) : {};
      return obj && typeof obj === "object" ? obj : {};
    } catch {
      return {};
    }
  }

  function setStudyMap(map) {
    localStorage.setItem(STUDY_KEY, JSON.stringify(map));
  }

  function todayISO() {
    const d = new Date();
    const y = d.getFullYear();
    const m = String(d.getMonth() + 1).padStart(2, "0");
    const day = String(d.getDate()).padStart(2, "0");
    return `${y}-${m}-${day}`;
  }

  function addDaysISO(iso, days) {
    const [y, m, d] = iso.split("-").map(Number);
    const dt = new Date(y, m - 1, d);
    dt.setDate(dt.getDate() + days);
    const yy = dt.getFullYear();
    const mm = String(dt.getMonth() + 1).padStart(2, "0");
    const dd = String(dt.getDate()).padStart(2, "0");
    return `${yy}-${mm}-${dd}`;
  }

  function markKnown(seq) {
    const map = getStudyMap();
    const key = String(seq);
    const cur = map[key] || { box: 0, due: todayISO() };
    const newBox = Math.min(4, (cur.box || 0) + 1);
    map[key] = { box: newBox, due: addDaysISO(todayISO(), BOX_DELAYS[newBox]) };
    setStudyMap(map);
  }

  function markUnknown(seq) {
    const map = getStudyMap();
    map[String(seq)] = { box: 0, due: todayISO() };
    setStudyMap(map);
  }

  function isDue(seq, map, today) {
    const rec = map[String(seq)];
    if (!rec) return false;
    return !rec.due || rec.due <= today;
  }

  function pickDeck(cards, size) {
    const limit = size || SESSION_SIZE;
    const map = getStudyMap();
    const today = todayISO();
    const due = [];
    const unseen = [];
    const rest = [];
    for (const c of cards) {
      const rec = map[String(c.seq)];
      if (!rec) unseen.push(c);
      else if (isDue(c.seq, map, today)) due.push(c);
      else rest.push(c);
    }
    // Prefer unseen then due for daily; for normal: due then unseen
    const out = sessionMode === "daily" ? [...unseen, ...due] : [...due, ...unseen];
    if (out.length < limit) {
      for (const c of rest) {
        if (out.length >= limit) break;
        out.push(c);
      }
    }
    return out.slice(0, limit);
  }


  /* —— weakness / 复盘 —— */
  let lastWeakness = null;

  function subjectAccuracyClass(acc) {
    if (acc == null) return "";
    if (acc < 60) return "bad";
    if (acc < 75) return "mid";
    return "";
  }

  function renderWeakness(data) {
    lastWeakness = data;
    if (!el.weaknessBars) return;
    const subjects = (data && data.subjects) || [];
    el.weaknessBars.innerHTML = "";
    let any = false;
    subjects.forEach((s) => {
      if (!s.total) return;
      any = true;
      const acc = s.accuracy != null ? s.accuracy : 0;
      const row = document.createElement("div");
      row.className = "weakness-row";
      const cls = subjectAccuracyClass(s.accuracy);
      row.innerHTML =
        `<span class="wl">${escapeHtml(s.label || s.subject)}</span>` +
        `<div class="weakness-track ${cls}"><span style="width:${Math.min(100, acc)}%"></span></div>` +
        `<span class="wr">${s.accuracy != null ? s.accuracy + "%" : "—"}</span>`;
      el.weaknessBars.appendChild(row);
    });
    if (el.weaknessSub) {
      el.weaknessSub.textContent = (data && data.summary) || "根据模考错题自动分析";
    }
    if (el.weaknessSuggestions) {
      el.weaknessSuggestions.innerHTML = "";
      const sugg = (data && data.suggestions) || [];
      sugg.forEach((sg) => {
        const li = document.createElement("li");
        li.innerHTML =
          `<span class="ws-reason"><strong>${escapeHtml(sg.label)}</strong> · ${escapeHtml(sg.reason)}</span>`;
        const btn = document.createElement("button");
        btn.type = "button";
        btn.textContent = sg.action_label || "去练习";
        btn.addEventListener("click", () => {
          if (sg.drill && EXAM_DRILL_SUBJECTS && EXAM_DRILL_SUBJECTS.has(sg.drill)) {
            examDrillSubject = sg.drill;
            location.hash = "#/exam";
            return;
          }
          if (sg.href && sg.href.indexOf("grammar") >= 0) {
            location.hash = "#/grammar";
            return;
          }
          if (sg.bias_daily || sg.subject === "vocabulary") {
            location.hash = "#/";
            if (el.dailyHint) el.dailyHint.textContent = "建议：点「生成今日」加强词汇（已纳入薄弱点加权）";
            return;
          }
          location.hash = sg.href || "#/exam";
        });
        li.appendChild(btn);
        el.weaknessSuggestions.appendChild(li);
      });
      if (!sugg.length && any) {
        const li = document.createElement("li");
        li.innerHTML = `<span class="ws-reason">暂无明显短板，保持每日计划即可</span>`;
        el.weaknessSuggestions.appendChild(li);
      }
    }
    if (el.weaknessHint) {
      if (!any) {
        el.weaknessHint.textContent = "还没有足够的模考记录。去「模考」做一套专项后回来刷新。";
      } else if (data && data.bias_daily_vocab) {
        el.weaknessHint.textContent = "检测到词汇偏弱：生成今日词表时会更偏向未学 / 到期复习。";
      } else {
        el.weaknessHint.textContent = "";
      }
    }
  }

  async function refreshWeakness() {
    if (el.weaknessHint) el.weaknessHint.textContent = "分析中…";
    try {
      const local = typeof getExamLogsLocal === "function" ? getExamLogsLocal() : [];
      const res = await fetch("/api/weakness/analyze", {
        method: "POST",
        headers: { "Content-Type": "application/json; charset=utf-8" },
        body: JSON.stringify({ sessions: local.slice(0, 40) }),
      });
      if (!res.ok) throw new Error(await readError(res));
      const data = await res.json();
      renderWeakness(data);
    } catch (e) {
      console.warn(e);
      try {
        const res2 = await fetch("/api/weakness");
        if (res2.ok) {
          renderWeakness(await res2.json());
          return;
        }
      } catch (_) {}
      if (el.weaknessHint) el.weaknessHint.textContent = "薄弱点分析暂不可用";
    }
  }

  /* —— daily plan —— */
  function getDaily() {
    try {
      const raw = localStorage.getItem(DAILY_KEY);
      const obj = raw ? JSON.parse(raw) : null;
      if (!obj || typeof obj !== "object") return null;
      return obj;
    } catch {
      return null;
    }
  }

  function setDaily(obj) {
    localStorage.setItem(DAILY_KEY, JSON.stringify(obj));
  }

  function dailyDoneCount(plan) {
    if (!plan || !Array.isArray(plan.done)) return 0;
    const set = new Set((plan.seqs || []).map(Number));
    return plan.done.map(Number).filter((n) => set.has(n)).length;
  }

  function refreshDailyUI() {
    const plan = getDaily();
    const today = todayISO();
    if (!plan || plan.date !== today || !Array.isArray(plan.seqs) || !plan.seqs.length) {
      if (el.dailyProgressText) el.dailyProgressText.textContent = "0/100";
      if (el.dailyBar) el.dailyBar.style.width = "0%";
      if (el.dailySub) el.dailySub.textContent = "选择 JLPT 等级，生成今日词表";
      if (el.btnDailyStart) {
        el.btnDailyStart.disabled = true;
        el.btnDailyStart.textContent = "开始今日";
      }
      return;
    }
    const quota = plan.quota || plan.seqs.length || 100;
    const done = dailyDoneCount(plan);
    if (el.dailyProgressText) el.dailyProgressText.textContent = `${done}/${quota}`;
    if (el.dailyBar) el.dailyBar.style.width = `${Math.min(100, Math.round((done / quota) * 100))}%`;
    if (el.dailyLevel) el.dailyLevel.value = plan.level || "N5";
    if (el.dailyQuota) el.dailyQuota.value = String(quota);
    if (el.dailySub) {
      el.dailySub.textContent = `${plan.level} · 今日 ${plan.seqs.length} 词 · ${plan.date}`;
    }
    if (el.btnDailyStart) {
      const remaining = plan.seqs.filter((s) => !(plan.done || []).map(Number).includes(Number(s)));
      el.btnDailyStart.disabled = remaining.length === 0 && done >= quota;
      el.btnDailyStart.textContent = done > 0 && remaining.length ? "继续" : done >= quota ? "已完成" : "开始今日";
      if (remaining.length === 0 && done < quota) {
        // all in list marked done somehow
        el.btnDailyStart.disabled = true;
        el.btnDailyStart.textContent = "已完成";
      }
      if (remaining.length) el.btnDailyStart.disabled = false;
    }
  }

  function markDailyDone(seq) {
    const plan = getDaily();
    if (!plan || plan.date !== todayISO()) return;
    const n = Number(seq);
    if (!Array.isArray(plan.done)) plan.done = [];
    if (!plan.done.map(Number).includes(n)) {
      plan.done.push(n);
      setDaily(plan);
    }
    refreshDailyUI();
  }

  async function generateDailyPlan() {
    const level = (el.dailyLevel && el.dailyLevel.value) || "N5";
    let quota = Number(el.dailyQuota && el.dailyQuota.value) || 100;
    quota = Math.max(10, Math.min(200, quota));
    if (el.dailyHint) el.dailyHint.textContent = "正在生成今日词表…";
    if (el.btnDailyGen) el.btnDailyGen.disabled = true;
    try {
      const fetchLimit = Math.min(200, Math.max(quota * 2, quota));
      const res = await fetch(`/api/jlpt?level=${encodeURIComponent(level)}&limit=${fetchLimit}`);
      if (!res.ok) throw new Error("jlpt failed");
      const cards = await res.json();
      if (!Array.isArray(cards) || !cards.length) {
        if (el.dailyHint) el.dailyHint.textContent = "该等级暂无词条";
        return;
      }
      sessionMode = "daily";
      let picked = pickDeck(cards, quota);
      // If vocabulary is a weak subject, prefer more unseen+due (re-pick with larger pool already)
      const biasVocab = !!(lastWeakness && lastWeakness.bias_daily_vocab);
      if (biasVocab && cards.length > picked.length) {
        const map = getStudyMap();
        const today = todayISO();
        const weakFirst = [...cards].sort((a, b) => {
          const ra = map[String(a.seq)];
          const rb = map[String(b.seq)];
          const sa = !ra ? 0 : isDue(a.seq, map, today) ? 1 : 2;
          const sb = !rb ? 0 : isDue(b.seq, map, today) ? 1 : 2;
          return sa - sb;
        });
        picked = weakFirst.slice(0, quota);
      }
      sessionMode = "normal";
      const seqs = picked.map((c) => Number(c.seq));
      const plan = {
        date: todayISO(),
        level,
        quota: seqs.length,
        seqs,
        done: [],
        cache: picked,
        biasWeakness: biasVocab,
      };
      setDaily(plan);
      if (el.dailyHint) {
        el.dailyHint.textContent = biasVocab
          ? `已生成 ${seqs.length} 个词（薄弱点加权：未学 / 到期优先）`
          : `已生成 ${seqs.length} 个词（优先未学 / 到期）`;
      }
      refreshDailyUI();
    } catch (err) {
      console.error(err);
      if (el.dailyHint) el.dailyHint.textContent = "生成失败，请确认后端已启动";
    } finally {
      if (el.btnDailyGen) el.btnDailyGen.disabled = false;
    }
  }

  async function startDailySession() {
    let plan = getDaily();
    if (!plan || plan.date !== todayISO() || !plan.seqs || !plan.seqs.length) {
      if (el.dailyHint) el.dailyHint.textContent = "请先点「生成今日」";
      return;
    }
    const doneSet = new Set((plan.done || []).map(Number));
    const remainingSeqs = plan.seqs.map(Number).filter((s) => !doneSet.has(s));
    if (!remainingSeqs.length) {
      if (el.dailyHint) el.dailyHint.textContent = "今日计划已完成";
      refreshDailyUI();
      return;
    }

    // Prefer cached card objects; refill missing
    const cacheMap = {};
    for (const c of plan.cache || []) cacheMap[Number(c.seq)] = c;
    const cards = [];
    for (const seq of remainingSeqs) {
      if (cacheMap[seq]) {
        cards.push(cacheMap[seq]);
        continue;
      }
      try {
        const res = await fetch(`/api/word/${seq}`);
        if (!res.ok) continue;
        const data = await res.json();
        cards.push(cardFromWord(data));
      } catch {
        /* skip */
      }
    }
    if (!cards.length) {
      if (el.dailyHint) el.dailyHint.textContent = "无法加载今日词条";
      return;
    }
    sessionMode = "daily";
    lastSource = "daily";
    sessionQueue = cards;
    sessionIndex = 0;
    sessionKnown = 0;
    sessionUnknown = 0;
    sessionFlipped = false;
    location.hash = "#/study/session";
    show("study");
    showStudyPane("session");
    renderCurrentCard();
  }

  function firstEnglishGloss(data) {
    if (data.gloss_en && String(data.gloss_en).trim()) return String(data.gloss_en).trim();
    const g =
      data.senses && data.senses[0] && data.senses[0].gloss && data.senses[0].gloss[0];
    return g ? String(g).trim() : "";
  }

  function cardFromWord(data) {
    const word_form =
      (data.kanji && data.kanji[0]) || (data.kana && data.kana[0]) || String(data.seq);
    const kana = (data.kana && data.kana[0]) || "";
    const gloss_zh = (data.gloss_zh && String(data.gloss_zh).trim()) || "";
    const gloss_en = firstEnglishGloss(data);
    const gloss_first = gloss_zh || gloss_en || "";
    return {
      seq: data.seq,
      word_form,
      kana,
      accent: (data.accent || "").trim() || null,
      gloss_zh: gloss_zh || null,
      gloss_en: gloss_en || null,
      gloss_first,
    };
  }

  function looksEnglishGloss(s) {
    const t = String(s || "").trim();
    if (!t) return false;
    const ascii = [...t].filter((ch) => /[A-Za-z]/.test(ch)).length;
    return ascii >= Math.max(3, Math.floor(t.length / 2));
  }

  function normalizeStudyCard(card) {
    if (!card) return card;
    let gloss_zh = (card.gloss_zh && String(card.gloss_zh).trim()) || "";
    let gloss_en = (card.gloss_en && String(card.gloss_en).trim()) || "";
    const gloss_first = (card.gloss_first && String(card.gloss_first).trim()) || "";
    // Older cached daily cards may only have gloss_first (zh or en).
    if (!gloss_zh && !gloss_en && gloss_first) {
      if (looksEnglishGloss(gloss_first)) gloss_en = gloss_first;
      else gloss_zh = gloss_first;
    } else if (!gloss_zh && gloss_first && !looksEnglishGloss(gloss_first)) {
      gloss_zh = gloss_first;
    } else if (!gloss_en && gloss_first && looksEnglishGloss(gloss_first)) {
      gloss_en = gloss_first;
    }
    return {
      ...card,
      gloss_zh: gloss_zh || null,
      gloss_en: gloss_en || null,
      gloss_first: gloss_zh || gloss_en || gloss_first || "",
    };
  }

  /* —— review learned —— */
  function getLearnedSeqs() {
    const map = getStudyMap();
    const today = todayISO();
    const learned = [];
    const dueFirst = [];
    for (const [k, rec] of Object.entries(map)) {
      const seq = Number(k);
      if (Number.isNaN(seq)) continue;
      if (!rec || (rec.box || 0) < 1) continue;
      if (!rec.due || rec.due <= today) dueFirst.push(seq);
      else learned.push(seq);
    }
    return [...dueFirst, ...learned];
  }

  function refreshReviewUI() {
    const seqs = getLearnedSeqs();
    if (el.reviewCount) el.reviewCount.textContent = String(seqs.length);
    if (el.btnReviewStart) el.btnReviewStart.disabled = seqs.length === 0;
    if (el.reviewEmpty) el.reviewEmpty.classList.toggle("hidden", seqs.length > 0);
    if (el.reviewSub) {
      el.reviewSub.textContent = seqs.length
        ? `已学 ${seqs.length} 词 · 优先复习到期的`
        : "SRS 中已学过的词（box ≥ 1）";
    }
  }

  async function startReviewSession() {
    const seqs = getLearnedSeqs().slice(0, SESSION_SIZE);
    if (!seqs.length) {
      refreshReviewUI();
      return;
    }
    const cards = [];
    for (const seq of seqs) {
      try {
        const res = await fetch(`/api/word/${seq}`);
        if (!res.ok) continue;
        cards.push(cardFromWord(await res.json()));
      } catch {
        /* skip */
      }
    }
    if (!cards.length) {
      if (el.studyHomeHint) {
        el.studyHomeHint.textContent = "复习词加载失败";
        el.studyHomeHint.classList.remove("hidden");
      }
      return;
    }
    sessionMode = "review";
    lastSource = "review";
    sessionQueue = cards;
    sessionIndex = 0;
    sessionKnown = 0;
    sessionUnknown = 0;
    sessionFlipped = false;
    location.hash = "#/study/session";
    showStudyPane("session");
    renderCurrentCard();
  }

  function syncClearBtn() {
    if (!el.clear) return;
    el.clear.hidden = !el.q.value;
  }

  function setNav(view) {
    const map = {
      search: el.navSearch,
      detail: el.navSearch,
      favorites: el.navFav,
      study: el.navStudy,
      exam: el.navExam,
      grammar: el.navGrammar,
      "grammar-detail": el.navGrammar,
    };
    [el.navSearch, el.navStudy, el.navFav, el.navExam, el.navGrammar].forEach((a) => {
      if (a) a.classList.remove("active");
    });
    const active = map[view];
    if (active) active.classList.add("active");
  }

  function show(view) {
    el.search.classList.toggle("hidden", view !== "search");
    el.detail.classList.toggle("hidden", view !== "detail");
    el.favorites.classList.toggle("hidden", view !== "favorites");
    if (el.study) el.study.classList.toggle("hidden", view !== "study");
    if (el.exam) el.exam.classList.toggle("hidden", view !== "exam");
    if (el.grammarView) el.grammarView.classList.toggle("hidden", view !== "grammar");
    if (el.grammarDetailView) {
      el.grammarDetailView.classList.toggle("hidden", view !== "grammar-detail");
    }
    const onDetail = view === "detail" || view === "grammar-detail";
    document.body.classList.toggle("detail-screen", onDetail);
    const foot = document.querySelector(".foot");
    if (foot) foot.classList.toggle("hidden", onDetail);
    setNav(view);
    if (view === "search") { refreshDailyUI(); refreshWeakness(); }
    if (view === "grammar") showGrammarPane("home");
    if (onDetail) {
      try { window.scrollTo({ top: 0, behavior: "instant" in window ? "instant" : "auto" }); }
      catch (_) { window.scrollTo(0, 0); }
    }
  }

  function escapeHtml(s) {
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  // ---- 模考富文本白名单清洗 ----------------------------------------------
  // 后端清洗是正则黑名单，`\s+on[a-z]+\s*=` 要求 on 前有空白，
  // `<svg/onload=alert(1)>` 用 `/` 分隔即可整体绕过；<style>/<form> 也不在
  // 移除名单里。模考题干/原文/翻译/解析都是外部 HTML，进 innerHTML 前必须逐节点
  // 重建：<template> 惰性解析不会执行脚本、不会加载资源，只留白名单标签与属性。
  const EXAM_ALLOW_TAGS = new Set([
    "B", "STRONG", "I", "EM", "U", "S", "DEL", "INS", "BR", "P", "DIV", "SPAN",
    "SMALL", "SUB", "SUP", "MARK", "RUBY", "RB", "RT", "RP", "OL", "UL", "LI",
    "BLOCKQUOTE", "IMG",
  ]);
  const EXAM_ALLOW_ATTRS = { IMG: ["src", "alt"] };

  function sanitizeExamHtml(html) {
    if (html == null || html === "") return "";
    const tpl = document.createElement("template");
    tpl.innerHTML = String(html);

    const rebuild = (parent) => {
      const frag = document.createDocumentFragment();
      Array.from(parent.childNodes).forEach((child) => {
        if (child.nodeType === Node.TEXT_NODE) {
          frag.appendChild(document.createTextNode(child.nodeValue));
          return;
        }
        if (child.nodeType !== Node.ELEMENT_NODE) return; // 注释 / CDATA 一律丢弃
        const tag = child.tagName.toUpperCase();
        if (!EXAM_ALLOW_TAGS.has(tag)) {
          // 标签本身不保留，但内部文本继续处理（<script> 文本随之变成纯文本）
          frag.appendChild(rebuild(child));
          return;
        }
        const keep = document.createElement(tag.toLowerCase());
        const extra = EXAM_ALLOW_ATTRS[tag] || [];
        Array.from(child.attributes).forEach((attr) => {
          const name = attr.name.toLowerCase();
          if (name.startsWith("on") || name === "style" || name === "srcdoc") return;
          if (name !== "class" && !extra.includes(name)) return;
          if (name === "src" && !/^https:\/\//i.test(attr.value.trim())) return;
          keep.setAttribute(name, attr.value);
        });
        if (tag === "IMG") {
          keep.setAttribute("loading", "lazy");
          keep.setAttribute("referrerpolicy", "no-referrer");
        }
        keep.appendChild(rebuild(child));
        frag.appendChild(keep);
      });
      return frag;
    };

    const holder = document.createElement("div");
    holder.appendChild(rebuild(tpl.content));
    return holder.innerHTML;
  }
  // 供离线单测调用（static/ 下无构建系统，暴露一个钩子比复制一份逻辑更可靠）
  window.__sanitizeExamHtml = sanitizeExamHtml;

  function route() {
    const hash = location.hash || "#/";
    if (hash.startsWith("#/word/")) {
      const seq = hash.slice("#/word/".length);
      openDetail(seq);
      return;
    }
    if (hash.startsWith("#/favorites")) {
      show("favorites");
      renderFavorites();
      return;
    }
    if (hash.startsWith("#/study")) {
      show("study");
      if (hash.startsWith("#/study/session") && sessionQueue.length && sessionIndex < sessionQueue.length) {
        showStudyPane("session");
      } else if (hash.startsWith("#/study/session") && sessionQueue.length && sessionIndex >= sessionQueue.length) {
        showStudyPane("end");
      } else {
        showStudyPane("home");
        refreshStudyHome();
      }
      return;
    }
    if (hash.startsWith("#/grammar/")) {
      const gid = hash.slice("#/grammar/".length).split(/[/?#]/)[0];
      show("grammar-detail");
      openGrammarDetail(gid);
      return;
    }
    if (hash.startsWith("#/grammar")) {
      show("grammar");
      showGrammarPane("home");
      resetGrammarBrowse();
      return;
    }
    if (hash.startsWith("#/exam/")) {
      const rest = hash.slice("#/exam/".length).trim();
      const parts = rest.split("/").filter(Boolean);
      const examId = parts[0] || "";
      const drill =
        parts[1] && EXAM_DRILL_SUBJECTS.has(parts[1]) ? parts[1] : null;
      if (drill) examDrillSubject = drill;
      show("exam");
      startExam(examId, drill);
      return;
    }
    if (hash.startsWith("#/exam")) {
      show("exam");
      showExamPane("home");
      syncExamDrillChips();
      loadExamList();
      return;
    }
    show("search");
  }

  function showStudyPane(pane) {
    if (!el.studyHome) return;
    el.studyHome.classList.toggle("hidden", pane !== "home");
    el.studySession.classList.toggle("hidden", pane !== "session");
    el.studyEnd.classList.toggle("hidden", pane !== "end");
  }

  async function refreshStudyHome() {
    if (el.countFav) el.countFav.textContent = String(getFavs().length);
    refreshReviewUI();
    try {
      const res = await fetch("/api/jlpt/counts");
      if (res.ok) {
        const counts = await res.json();
        for (const lvl of ["N5", "N4", "N3", "N2", "N1"]) {
          const node = document.getElementById(`count-${lvl}`);
          if (node) node.textContent = String(counts[lvl] ?? "—");
        }
      }
    } catch {
      /* ignore */
    }
    updateStartButton();
  }

  function updateStartButton() {
    if (!el.btnStudyStart) return;
    el.btnStudyStart.disabled = !selectedSource;
    if (!selectedSource) {
      el.studyHomeHint.textContent = "选择词库后点「开始」";
      el.studyHomeHint.classList.remove("hidden");
      return;
    }
    if (selectedSource === "favorites" && getFavs().length === 0) {
      el.studyHomeHint.textContent = "生词本还是空的，先去查词收藏几个吧。";
      el.studyHomeHint.classList.remove("hidden");
      el.btnStudyStart.disabled = true;
      return;
    }
    el.studyHomeHint.textContent = "";
    el.studyHomeHint.classList.add("hidden");
  }

  async function loadSourceCards(source) {
    if (source === "favorites") {
      const favs = getFavs();
      if (!favs.length) return [];
      const items = [];
      for (const seq of favs) {
        try {
          const res = await fetch(`/api/word/${seq}`);
          if (!res.ok) continue;
          items.push(cardFromWord(await res.json()));
        } catch {
          /* skip */
        }
      }
      return items;
    }
    if (source === "review") {
      return [];
    }
    const res = await fetch(`/api/jlpt?level=${encodeURIComponent(source)}&limit=100`);
    if (!res.ok) throw new Error("jlpt fetch failed");
    const data = await res.json();
    return Array.isArray(data) ? data.map(normalizeStudyCard) : [];
  }

  async function startSession(source) {
    lastSource = source;
    sessionMode = source === "daily" ? "daily" : source === "review" ? "review" : "normal";
    el.studyHomeHint.textContent = "准备词卡…";
    el.studyHomeHint.classList.remove("hidden");
    el.btnStudyStart.disabled = true;
    try {
      const cards = await loadSourceCards(source);
      if (source === "favorites" && !cards.length) {
        el.studyHomeHint.textContent = "生词本还是空的，先去查词收藏几个吧。";
        el.btnStudyStart.disabled = true;
        return;
      }
      if (!cards.length) {
        el.studyHomeHint.textContent = "这个词库暂时没有词条。";
        el.btnStudyStart.disabled = false;
        return;
      }
      sessionQueue = pickDeck(cards, SESSION_SIZE);
      sessionIndex = 0;
      sessionKnown = 0;
      sessionUnknown = 0;
      sessionFlipped = false;
      if (!sessionQueue.length) {
        el.studyHomeHint.textContent = "没有可复习的词。";
        el.btnStudyStart.disabled = false;
        return;
      }
      location.hash = "#/study/session";
      showStudyPane("session");
      renderCurrentCard();
    } catch (err) {
      console.error(err);
      el.studyHomeHint.textContent = "加载失败，请确认后端已启动";
      el.studyHomeHint.classList.remove("hidden");
      el.btnStudyStart.disabled = false;
    }
  }

  function renderCurrentCard() {
    if (sessionIndex >= sessionQueue.length) {
      finishSession();
      return;
    }
    const card = sessionQueue[sessionIndex];
    sessionFlipped = false;
    el.fcWord.textContent = card.word_form || "";
    // Always show kana clearly
    const kana = (card.kana || "").trim();
    el.fcKana.textContent = kana || "（无假名）";
    const accent = (card.accent || "").trim();
    if (accent) {
      el.fcAccent.hidden = false;
      el.fcAccent.textContent = accent;
    } else {
      el.fcAccent.hidden = true;
      el.fcAccent.textContent = "";
    }
    const c = normalizeStudyCard(card);
    sessionQueue[sessionIndex] = c;
    const zh = (c.gloss_zh || "").trim();
    const en = (c.gloss_en || "").trim();
    if (el.fcGlossZh) {
      if (zh) {
        el.fcGlossZh.textContent = zh;
        el.fcGlossZh.classList.remove("empty");
      } else {
        el.fcGlossZh.textContent = "词典暂无中文词义";
        el.fcGlossZh.classList.add("empty");
      }
    }
    if (el.fcGlossEn) {
      if (en && en !== zh) {
        el.fcGlossEn.hidden = false;
        el.fcGlossEn.textContent = en;
      } else {
        el.fcGlossEn.hidden = true;
        el.fcGlossEn.textContent = "";
      }
    }
    if (el.fcGloss) {
      el.fcGloss.hidden = true;
      el.fcGloss.textContent = c.gloss_first || "";
    }
    if (el.fcMeaning) el.fcMeaning.classList.add("hidden");
    if (el.fcTap) el.fcTap.textContent = "点击显示释义";
    const total = sessionQueue.length;
    const cur = sessionIndex + 1;
    el.studyProgressText.textContent = `${cur}/${total}`;
    el.studyBar.style.width = `${Math.round((sessionIndex / total) * 100)}%`;
  }

  function flipCard() {
    sessionFlipped = !sessionFlipped;
    if (el.fcMeaning) el.fcMeaning.classList.toggle("hidden", !sessionFlipped);
    if (el.fcTap) el.fcTap.textContent = sessionFlipped ? "再点可隐藏释义" : "点击显示释义";
  }

  function answer(known) {
    const card = sessionQueue[sessionIndex];
    if (!card) return;
    if (known) {
      markKnown(card.seq);
      sessionKnown += 1;
    } else {
      markUnknown(card.seq);
      sessionUnknown += 1;
    }
    if (sessionMode === "daily") markDailyDone(card.seq);
    sessionIndex += 1;
    if (sessionIndex >= sessionQueue.length) {
      el.studyBar.style.width = "100%";
      finishSession();
    } else {
      renderCurrentCard();
    }
  }

  function finishSession() {
    el.studyEndStats.textContent = `认识 ${sessionKnown} · 不认识 ${sessionUnknown} · 共 ${sessionQueue.length} 词`;
    showStudyPane("end");
    refreshDailyUI();
  }

  async function doSearch(q) {
    lastQuery = q;
    syncClearBtn();
    if (!q.trim()) {
      el.results.innerHTML = "";
      if (el.grammarList) el.grammarList.innerHTML = "";
      if (el.grammarSection) el.grammarSection.hidden = true;
      el.resultsWrap.hidden = true;
      el.hint.textContent = "输入日语、假名或中文释义开始查词";
      el.hint.classList.remove("hidden");
      return;
    }
    el.hint.textContent = "搜索中…";
    el.hint.classList.remove("hidden");
    try {
      const [wordRes, gramRes] = await Promise.all([
        fetch(`/api/search?q=${encodeURIComponent(q)}&limit=10`),
        fetch(`/api/grammar?q=${encodeURIComponent(q)}&limit=15`),
      ]);
      if (q !== lastQuery) return;
      if (!wordRes.ok) throw new Error("search failed");
      const data = await wordRes.json();
      const grammar = gramRes.ok ? await gramRes.json() : [];
      if (q !== lastQuery) return;
      const words = Array.isArray(data) ? data : [];
      const grams = Array.isArray(grammar) ? grammar : [];
      renderResults(words, el.results, null);
      renderGrammar(grams);
      const hasWords = words.length > 0;
      const hasGrammar = grams.length > 0;
      if (hasWords || hasGrammar) {
        el.resultsWrap.hidden = false;
        el.hint.classList.add("hidden");
        el.hint.textContent = "";
      } else {
        el.hint.textContent = "没有匹配";
        el.resultsWrap.hidden = true;
        el.hint.classList.remove("hidden");
      }
    } catch (err) {
      if (q !== lastQuery) return;
      el.hint.textContent = "搜索失败，请确认后端已启动";
      el.hint.classList.remove("hidden");
      el.resultsWrap.hidden = true;
      if (el.grammarSection) el.grammarSection.hidden = true;
      console.error(err);
    }
  }

  function renderResults(items, listEl, wrapEl) {
    listEl.innerHTML = "";
    if (!items.length) {
      if (wrapEl) wrapEl.hidden = true;
      return;
    }
    if (wrapEl) wrapEl.hidden = false;
    for (const item of items) {
      const li = document.createElement("li");
      li.className = "cand";
      li.innerHTML = `
        <span class="w">${escapeHtml(item.word_form || "")}</span>
        <span class="k">${escapeHtml(item.kana || "")}</span>
        <span class="g">${escapeHtml(item.gloss_first || "")}</span>
      `;
      li.addEventListener("click", () => {
        location.hash = `#/word/${item.seq}`;
      });
      listEl.appendChild(li);
    }
  }

  function shortExplain(text, maxLen) {
    const s = String(text || "").replace(/\s+/g, " ").trim();
    if (s.length <= maxLen) return s;
    return s.slice(0, maxLen) + "…";
  }

  function renderGrammar(items) {
    if (!el.grammarList || !el.grammarSection) return;
    el.grammarList.innerHTML = "";
    if (!items.length) {
      el.grammarSection.hidden = true;
      return;
    }
    el.grammarSection.hidden = false;
    for (const item of items) {
      const li = document.createElement("li");
      li.className = "cand grammar";
      const pattern = item.pattern || "";
      const explain = item.explain || "";
      const gid = item.id != null ? Number(item.id) : null;
      li.innerHTML = `
        <span class="w">${escapeHtml(pattern)}</span>
        <span class="k">语法</span>
        <span class="g">${escapeHtml(shortExplain(explain, 28))}</span>
        <div class="explain">${escapeHtml(explain)}</div>
      `;
      li.addEventListener("click", () => {
        if (gid != null && !Number.isNaN(gid)) {
          location.hash = `#/grammar/${gid}`;
          return;
        }
        li.classList.toggle("open");
      });
      el.grammarList.appendChild(li);
    }
  }


  function formatAiText(text) {
    let s = escapeHtml(String(text || ""));
    s = s.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
    s = s.replace(/^### (.+)$/gm, '<div class="ai-h">$1</div>');
    s = s.replace(/^## (.+)$/gm, '<div class="ai-h">$1</div>');
    s = s.replace(/^# (.+)$/gm, '<div class="ai-h">$1</div>');
    s = s.replace(/^- (.+)$/gm, "• $1");
    s = s.replace(/\n/g, "<br>");
    return s;
  }

  function renderAiChat() {
    const box = document.getElementById("ai-chat");
    if (!box) return;
    box.innerHTML = "";
    if (!aiHistory.length) {
      const tip = document.createElement("div");
      tip.className = "ai-msg ai-loading";
      tip.textContent = "点「本地讲解」获取概览，或直接提问。";
      box.appendChild(tip);
      return;
    }
    for (const m of aiHistory) {
      const div = document.createElement("div");
      div.className = `ai-msg ${m.role === "user" ? "user" : "assistant"}`;
      if (m.role === "assistant") div.innerHTML = formatAiText(m.content);
      else div.textContent = m.content;
      box.appendChild(div);
    }
    box.scrollTop = box.scrollHeight;
  }

  function setAiBusy(busy) {
    aiBusy = busy;
    const send = document.getElementById("btn-ai-send");
    const auto = document.getElementById("btn-ai-auto");
    const input = document.getElementById("ai-input");
    if (send) send.disabled = busy;
    if (auto) auto.disabled = busy;
    if (input) input.disabled = busy;
  }

  async function askAi(question, isAuto) {
    if (aiSeq == null || aiBusy) return;
    const q = (question || "").trim();
    const box = document.getElementById("ai-chat");
    if (!box) return;

    if (!isAuto && q) {
      aiHistory.push({ role: "user", content: q });
      renderAiChat();
    }

    const loading = document.createElement("div");
    loading.className = "ai-msg ai-loading";
    loading.id = "ai-loading-msg";
    loading.textContent = "本地 AI 思考中…";
    box.appendChild(loading);
    box.scrollTop = box.scrollHeight;

    setAiBusy(true);
    try {
      const payload = {
        seq: Number(aiSeq),
        question: q || null,
        history: [],
      };
      if (isAuto) {
        payload.question = null;
        payload.history = [];
      } else if (q) {
        const prior = aiHistory.slice(0, -1);
        payload.history = prior.map((m) => ({ role: m.role, content: m.content }));
        payload.question = q;
      }

      const res = await fetch("/api/ai/explain", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      let data = null;
      try {
        data = await res.json();
      } catch {
        data = null;
      }
      const loadingEl = document.getElementById("ai-loading-msg");
      if (loadingEl) loadingEl.remove();

      if (!res.ok) {
        const detail =
          (data && (data.detail || data.message)) ||
          (res.status === 503
            ? "本机 Ollama 未响应。AI 讲解是可选的，不影响查词 / 语法 / 模考；" +
              "要用请先安装 Ollama 并执行 ollama pull qwen2.5:7b"
            : "请求失败");
        const err = document.createElement("div");
        err.className = "ai-msg ai-error";
        err.textContent = String(detail);
        box.appendChild(err);
        return;
      }
      const textOut = (data && data.text) || "";
      aiHistory.push({ role: "assistant", content: textOut });
      renderAiChat();
    } catch (err) {
      console.error(err);
      const loadingEl = document.getElementById("ai-loading-msg");
      if (loadingEl) loadingEl.remove();
      const e = document.createElement("div");
      e.className = "ai-msg ai-error";
      e.textContent = "网络错误，请确认后端与 Ollama 已启动";
      box.appendChild(e);
    } finally {
      setAiBusy(false);
    }
  }

  function bindWordAiControls() {
    renderAiChat();
    const autoBtn = document.getElementById("btn-ai-auto");
    if (autoBtn) autoBtn.addEventListener("click", () => askAi("", true));
    const sendBtn = document.getElementById("btn-ai-send");
    const input = document.getElementById("ai-input");
    const send = () => {
      if (!input) return;
      const q = input.value.trim();
      if (!q) return;
      input.value = "";
      askAi(q, false);
    };
    if (sendBtn) sendBtn.addEventListener("click", send);
    if (input) {
      input.addEventListener("keydown", (e) => {
        if (e.key === "Enter") {
          e.preventDefault();
          send();
        }
      });
    }
  }

  function renderGAiChat() {
    const box = document.getElementById("g-ai-chat");
    if (!box) return;
    box.innerHTML = "";
    if (!gAiHistory.length) {
      const tip = document.createElement("div");
      tip.className = "ai-msg ai-loading";
      tip.textContent = "点「本地讲解」获取概览，或直接提问。";
      box.appendChild(tip);
      return;
    }
    for (const m of gAiHistory) {
      const div = document.createElement("div");
      div.className = `ai-msg ${m.role === "user" ? "user" : "assistant"}`;
      if (m.role === "assistant") div.innerHTML = formatAiText(m.content);
      else div.textContent = m.content;
      box.appendChild(div);
    }
    box.scrollTop = box.scrollHeight;
  }

  function setGAiBusy(busy) {
    gAiBusy = busy;
    const send = document.getElementById("btn-g-ai-send");
    const auto = document.getElementById("btn-g-ai-auto");
    const input = document.getElementById("g-ai-input");
    if (send) send.disabled = busy;
    if (auto) auto.disabled = busy;
    if (input) input.disabled = busy;
  }

  async function askGrammarAi(question, isAuto) {
    if (gAiId == null || gAiBusy) return;
    const q = (question || "").trim();
    const box = document.getElementById("g-ai-chat");
    if (!box) return;

    if (!isAuto && q) {
      gAiHistory.push({ role: "user", content: q });
      renderGAiChat();
    }

    const loading = document.createElement("div");
    loading.className = "ai-msg ai-loading";
    loading.id = "g-ai-loading-msg";
    loading.textContent = "本地 AI 思考中…";
    box.appendChild(loading);
    box.scrollTop = box.scrollHeight;

    setGAiBusy(true);
    try {
      const payload = {
        grammar_id: Number(gAiId),
        question: null,
        history: [],
      };
      if (isAuto) {
        payload.question = null;
        payload.history = [];
      } else if (q) {
        const prior = gAiHistory.slice(0, -1);
        payload.history = prior.map((m) => ({ role: m.role, content: m.content }));
        payload.question = q;
      }

      const res = await fetch("/api/ai/grammar", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      let data = null;
      try {
        data = await res.json();
      } catch {
        data = null;
      }
      const loadingEl = document.getElementById("g-ai-loading-msg");
      if (loadingEl) loadingEl.remove();

      if (!res.ok) {
        const detail =
          (data && (data.detail || data.message)) ||
          (res.status === 503
            ? "本机 Ollama 未响应。AI 讲解是可选的，不影响查词 / 语法 / 模考；" +
              "要用请先安装 Ollama 并执行 ollama pull qwen2.5:7b"
            : "请求失败");
        const err = document.createElement("div");
        err.className = "ai-msg ai-error";
        err.textContent = String(detail);
        box.appendChild(err);
        return;
      }
      const textOut = (data && data.text) || "";
      gAiHistory.push({ role: "assistant", content: textOut });
      renderGAiChat();
    } catch (err) {
      console.error(err);
      const loadingEl = document.getElementById("g-ai-loading-msg");
      if (loadingEl) loadingEl.remove();
      const e = document.createElement("div");
      e.className = "ai-msg ai-error";
      e.textContent = "网络错误，请确认后端与 Ollama 已启动";
      box.appendChild(e);
    } finally {
      setGAiBusy(false);
    }
  }

  function bindGrammarAiControls() {
    renderGAiChat();
    const autoBtn = document.getElementById("btn-g-ai-auto");
    if (autoBtn) autoBtn.addEventListener("click", () => askGrammarAi("", true));
    const sendBtn = document.getElementById("btn-g-ai-send");
    const input = document.getElementById("g-ai-input");
    const send = () => {
      if (!input) return;
      const q = input.value.trim();
      if (!q) return;
      input.value = "";
      askGrammarAi(q, false);
    };
    if (sendBtn) sendBtn.addEventListener("click", send);
    if (input) {
      input.addEventListener("keydown", (ev) => {
        if (ev.key === "Enter") {
          ev.preventDefault();
          send();
        }
      });
    }
  }


  // 快速连点词条时，慢的旧响应会覆盖新页面，并让 AI 上下文指向另一个词。
  // 用单调递增的 token 丢弃过期响应，aiSeq 只在确认渲染时才切换。
  let detailToken = 0;

  async function openDetail(seq) {
    const token = ++detailToken;
    show("detail");
    el.detailBox.innerHTML = "<p class='hint'>加载中…</p>";
    try {
      const res = await fetch(`/api/word/${encodeURIComponent(seq)}`);
      if (token !== detailToken) return;
      if (!res.ok) {
        el.detailBox.innerHTML = "<p class='hint'>未找到该词条</p>";
        return;
      }
      const data = await res.json();
      if (token !== detailToken) return;
      aiSeq = Number(seq);
      aiHistory = [];
      renderDetail(data);
    } catch (err) {
      if (token !== detailToken) return;
      el.detailBox.innerHTML = "<p class='hint'>加载失败</p>";
      console.error(err);
    }
  }

  function collectPosZh(senses) {
    const seen = new Set();
    const out = [];
    for (const s of senses || []) {
      for (const p of s.pos_zh || []) {
        if (!seen.has(p)) {
          seen.add(p);
          out.push(p);
        }
      }
    }
    return out;
  }

  function renderConjugations(conj) {
    if (!conj || typeof conj !== "object") return "";
    const keys = Object.keys(conj);
    if (!keys.length) return "";
    const ordered = [];
    for (const k of CONJ_PREF) {
      if (conj[k]) ordered.push(k);
    }
    for (const k of keys) {
      if (!ordered.includes(k) && conj[k]) ordered.push(k);
    }
    const items = ordered
      .map(
        (k) => `
      <div class="conj-item">
        <div class="label">${escapeHtml(k)}</div>
        <div class="form">${escapeHtml(conj[k])}</div>
      </div>`
      )
      .join("");
    return `<div class="conj-grid">${items}</div>`;
  }

  function renderExamples(examples) {
    if (!examples || !examples.length) {
      return `<p class="ld-empty">暂无例句</p>`;
    }
    return examples
      .map(
        (ex) => `
      <div class="example">
        <div class="jp">${escapeHtml(ex.jpn || "")}</div>
        <div class="cn">${escapeHtml(ex.cmn || "")}</div>
      </div>`
      )
      .join("");
  }

  function renderEnglishSenses(senses) {
    let senseNum = 0;
    let sensesHtml = "";
    (senses || []).forEach((s) => {
      const glosses = s.gloss || [];
      if (!glosses.length) return;
      const glossText = glosses.map(escapeHtml).join("；");
      senseNum += 1;
      sensesHtml += `
        <div class="sense">
          <span class="num">${senseNum}</span>
          <div>
            <span class="gloss">${glossText}</span>
          </div>
        </div>
      `;
    });
    return sensesHtml;
  }

  function extractPatternKana(pattern) {
    const s = String(pattern || "");
    const runs = s.match(/[\u3040-\u309F\u30A0-\u30FFー]+/g);
    if (!runs || !runs.length) return "";
    // prefer longest hiragana/katakana run as reading hint
    runs.sort((a, b) => b.length - a.length);
    return runs[0];
  }

  function renderDetail(data) {
    const hasKanji = data.kanji && data.kanji.length > 0;
    const spell = hasKanji ? data.kanji[0] : (data.kana && data.kana[0]) || String(data.seq);
    const kana = (data.kana && data.kana[0]) || "";
    const romaji = data.romaji || "";
    const accent = (data.accent || "").trim();
    const level = (data.level || "").trim();
    const glossZh = (data.gloss_zh || "").trim();

    let headWordHtml;
    if (hasKanji && kana) {
      headWordHtml = `<ruby>${escapeHtml(spell)}<rt>${escapeHtml(kana)}</rt></ruby>`;
    } else {
      headWordHtml = escapeHtml(spell);
    }

    const posTags = collectPosZh(data.senses)
      .map((t) => `<span class="tag pos">${escapeHtml(t)}</span>`)
      .join("");
    const jlptTag = level ? `<span class="tag jlpt">${escapeHtml(level)}</span>` : "";
    const tags = posTags + jlptTag;

    const enSenses = renderEnglishSenses(data.senses);
    let meaningInner = "";
    if (glossZh) {
      meaningInner = `
        <div class="sense">
          <span class="num zh">中</span>
          <div><span class="gloss gloss-zh">${escapeHtml(glossZh)}</span></div>
        </div>
        ${enSenses ? `<div class="ld-sub">英文补充</div>${enSenses}` : ""}
      `;
    } else {
      meaningInner = `
        <p class="ld-empty">暂无中文词义（本地日中词典未收录）</p>
        ${enSenses ? `<div class="ld-sub">英文补充</div>${enSenses}` : `<p class="ld-empty">无释义</p>`}
      `;
    }

    const otherWritings = [...(data.kanji || []), ...(data.kana || [])].filter(
      (v, i, a) => a.indexOf(v) === i && v !== spell
    );
    const variantsHtml = otherWritings.length
      ? otherWritings
          .map((w, i) => (i === 0 ? `<b>${escapeHtml(w)}</b>` : escapeHtml(w)))
          .join(" / ")
      : "";

    const favOn = isFav(data.seq);
    const conjHtml = renderConjugations(data.conjugations);
    const exHtml = renderExamples(data.examples);

    el.detailBox.innerHTML = `
      <div class="learn-detail">
        <header class="ld-head">
          <div class="ld-word">${headWordHtml}</div>
          ${
            kana
              ? `<div class="ld-kana"><span class="ld-kana-label">平假名</span><span class="ld-kana-text">${escapeHtml(kana)}</span></div>`
              : ""
          }
          ${
            romaji || accent
              ? `<div class="ld-meta">
            ${romaji ? `<span class="roma">${escapeHtml(romaji)}</span>` : ""}
            ${accent ? `<span class="accent" title="音调">${escapeHtml(accent)}</span>` : ""}
          </div>`
              : ""
          }
          ${tags ? `<div class="tags">${tags}</div>` : ""}
        </header>

        <section class="ld-section">
          <h2 class="ld-section-title">意思</h2>
          <div class="ld-section-body">${meaningInner}</div>
        </section>

        <section class="ld-section">
          <h2 class="ld-section-title">例句</h2>
          <div class="ld-section-body">${exHtml}</div>
        </section>

        <section class="ld-section ld-ai">
          <h2 class="ld-section-title">AI</h2>
          <div class="ai-wrap">
            <div class="ai-head">
              <span class="ai-head-title">本地讲解</span>
              <button type="button" class="ai-btn ghost" id="btn-ai-auto">本地讲解</button>
            </div>
            <div id="ai-chat" class="ai-chat" aria-live="polite"></div>
            <div class="ai-input-row">
              <input id="ai-input" type="text" placeholder="问关于这个词的问题…" maxlength="400" autocomplete="off" />
              <button type="button" class="ai-send" id="btn-ai-send">发送</button>
            </div>
          </div>
        </section>

        ${
          conjHtml
            ? `<section class="ld-section ld-extra">
                <h2 class="ld-section-title">活用</h2>
                <div class="ld-section-body">${conjHtml}</div>
              </section>`
            : ""
        }
        ${
          variantsHtml
            ? `<section class="ld-section ld-extra">
                <h2 class="ld-section-title">其他写法</h2>
                <div class="ld-section-body"><div class="variants">${variantsHtml}</div></div>
              </section>`
            : ""
        }
        <button type="button" class="fav ${favOn ? "on" : ""}" id="btn-fav">
          ${favOn ? "★ 已收藏" : "☆ 收藏"}
        </button>
      </div>
    `;

    const btn = document.getElementById("btn-fav");
    btn.addEventListener("click", () => {
      const on = toggleFav(data.seq);
      btn.classList.toggle("on", on);
      btn.textContent = on ? "★ 已收藏" : "☆ 收藏";
    });

    bindWordAiControls();
  }

  async function renderFavorites() {
    const favs = getFavs();
    el.favList.innerHTML = "";
    if (!favs.length) {
      el.favEmpty.classList.remove("hidden");
      el.favWrap.hidden = true;
      return;
    }
    el.favEmpty.classList.add("hidden");
    const items = [];
    for (const seq of favs) {
      try {
        const res = await fetch(`/api/word/${seq}`);
        if (!res.ok) continue;
        items.push(cardFromWord(await res.json()));
      } catch {
        /* skip */
      }
    }
    renderResults(items, el.favList, el.favWrap);
  }

  el.q.addEventListener("input", () => {
    syncClearBtn();
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(() => doSearch(el.q.value), 200);
  });

  if (el.clear) {
    el.clear.addEventListener("click", () => {
      el.q.value = "";
      syncClearBtn();
      doSearch("");
      el.q.focus();
    });
  }

  el.hot.addEventListener("click", (e) => {
    const btn = e.target.closest("button[data-q]");
    if (!btn) return;
    const q = btn.getAttribute("data-q");
    el.q.value = q;
    syncClearBtn();
    doSearch(q);
  });

  el.back.addEventListener("click", () => {
    if (window.history.length > 1) history.back();
    else location.hash = "#/";
  });

  if (el.btnDailyGen) el.btnDailyGen.addEventListener("click", () => generateDailyPlan());
  if (el.btnDailyStart) el.btnDailyStart.addEventListener("click", () => startDailySession());

  if (el.btnReviewStart) {
    el.btnReviewStart.addEventListener("click", () => startReviewSession());
  }

  if (el.studySources) {
    el.studySources.addEventListener("click", (e) => {
      const btn = e.target.closest(".study-source");
      if (!btn) return;
      selectedSource = btn.getAttribute("data-source");
      el.studySources.querySelectorAll(".study-source").forEach((b) => {
        b.classList.toggle("selected", b === btn);
      });
      updateStartButton();
    });
  }

  if (el.btnStudyStart) {
    el.btnStudyStart.addEventListener("click", () => {
      if (!selectedSource) return;
      startSession(selectedSource);
    });
  }

  if (el.flashcard) {
    el.flashcard.addEventListener("click", () => flipCard());
  }
  if (el.btnKnown) el.btnKnown.addEventListener("click", () => answer(true));
  if (el.btnUnknown) el.btnUnknown.addEventListener("click", () => answer(false));

  if (el.btnStudyAgain) {
    el.btnStudyAgain.addEventListener("click", () => {
      if (lastSource === "daily") {
        startDailySession();
        return;
      }
      if (lastSource === "review") {
        startReviewSession();
        return;
      }
      const src = lastSource || selectedSource;
      if (src) startSession(src);
      else {
        location.hash = "#/study";
        showStudyPane("home");
        refreshStudyHome();
      }
    });
  }
  if (el.btnStudyHome) {
    el.btnStudyHome.addEventListener("click", () => {
      location.hash = "#/study";
      showStudyPane("home");
      refreshStudyHome();
    });
  }

  // ============ 语法学习 ============
  function grammarLevelLabel(level) {
    if (!level) return "未分级";
    const u = String(level).toUpperCase();
    if (["N5", "N4", "N3", "N2", "N1"].includes(u)) return u;
    return "未分级";
  }

  function grammarLevelParam() {
    if (!grammarLevel || grammarLevel === "all") return "";
    return `&level=${encodeURIComponent(grammarLevel)}`;
  }

  function syncGrammarLevelChips() {
    if (!el.grammarLevelChips) return;
    el.grammarLevelChips.querySelectorAll(".grammar-level-chip").forEach((btn) => {
      btn.classList.toggle("selected", btn.dataset.level === grammarLevel);
    });
  }

  function showGrammarPane(pane) {
    if (!el.grammarHome) return;
    // Grammar list lives in view-grammar; detail is a separate top-level view.
    el.grammarHome.classList.toggle("hidden", pane !== "home");
  }

  function syncGrammarClearBtn() {
    if (!el.btnGrammarClear || !el.grammarQ) return;
    el.btnGrammarClear.hidden = !el.grammarQ.value;
  }

  function resetGrammarBrowse() {
    grammarOffset = 0;
    grammarTotal = 0;
    grammarQuery = (el.grammarQ && el.grammarQ.value.trim()) || "";
    if (el.grammarBrowseList) el.grammarBrowseList.innerHTML = "";
    if (el.btnGrammarMore) el.btnGrammarMore.hidden = true;
    if (el.grammarBrowseEmpty) el.grammarBrowseEmpty.classList.add("hidden");
    syncGrammarLevelChips();
    loadGrammarPage(false);
  }

  function appendGrammarItems(items) {
    if (!el.grammarBrowseList) return;
    for (const item of items) {
      const li = document.createElement("li");
      li.className = "cand grammar browse";
      const pattern = item.pattern || "";
      const explain = item.explain || "";
      const gid = item.id;
      const lvl = grammarLevelLabel(item.level);
      const lvlClass = item.level ? "tag jlpt" : "tag jlpt unknown";
      li.innerHTML = `
        <span class="w">${escapeHtml(pattern)}</span>
        <span class="k"><span class="${lvlClass}">${escapeHtml(lvl)}</span></span>
        <span class="g">${escapeHtml(shortExplain(explain, 36))}</span>
      `;
      li.addEventListener("click", () => {
        if (gid != null) location.hash = `#/grammar/${gid}`;
      });
      el.grammarBrowseList.appendChild(li);
    }
  }

  async function loadGrammarPage(append) {
    if (grammarLoading) return;
    grammarLoading = true;
    if (el.btnGrammarMore) el.btnGrammarMore.disabled = true;
    try {
      const q = grammarQuery;
      const levelQs = grammarLevelParam();
      const levelNote =
        !grammarLevel || grammarLevel === "all"
          ? "全部"
          : grammarLevel === "unknown"
            ? "未分级"
            : grammarLevel;
      let items = [];
      if (q) {
        const res = await fetch(
          `/api/grammar?q=${encodeURIComponent(q)}&limit=50${levelQs}`
        );
        items = res.ok ? await res.json() : [];
        if (!Array.isArray(items)) items = [];
        grammarTotal = items.length;
        if (!append) {
          if (el.grammarBrowseList) el.grammarBrowseList.innerHTML = "";
          appendGrammarItems(items);
        }
        grammarOffset = items.length;
        if (el.btnGrammarMore) el.btnGrammarMore.hidden = true;
        if (el.grammarListMeta) {
          el.grammarListMeta.textContent = items.length
            ? `搜索「${q}」· ${levelNote} · ${items.length} 条`
            : `搜索「${q}」· ${levelNote} · 无结果`;
        }
      } else {
        const res = await fetch(
          `/api/grammar/list?limit=${GRAMMAR_PAGE}&offset=${append ? grammarOffset : 0}${levelQs}`
        );
        if (!res.ok) throw new Error("list failed");
        const data = await res.json();
        grammarTotal = Number(data.total) || 0;
        items = Array.isArray(data.items) ? data.items : [];
        if (!append && el.grammarBrowseList) el.grammarBrowseList.innerHTML = "";
        appendGrammarItems(items);
        grammarOffset = (append ? grammarOffset : 0) + items.length;
        if (el.grammarListMeta) {
          el.grammarListMeta.textContent = `${levelNote} · 共 ${grammarTotal} 条 · 已显示 ${grammarOffset}`;
        }
        if (el.btnGrammarMore) {
          el.btnGrammarMore.hidden = grammarOffset >= grammarTotal;
        }
      }
      if (el.grammarBrowseEmpty) {
        const empty = !(el.grammarBrowseList && el.grammarBrowseList.children.length);
        el.grammarBrowseEmpty.classList.toggle("hidden", !empty);
      }
    } catch (err) {
      console.error(err);
      if (el.grammarListMeta) el.grammarListMeta.textContent = "加载失败";
    } finally {
      grammarLoading = false;
      if (el.btnGrammarMore) el.btnGrammarMore.disabled = false;
    }
  }

  function renderGrammarDetail(data) {
    if (!el.grammarDetail) return;
    const pattern = data.pattern || "";
    const explain = data.explain || "";
    const connection = (data.connection || "").trim();
    const lvl = grammarLevelLabel(data.level);
    const lvlClass = data.level ? "tag jlpt" : "tag jlpt unknown";
    const kanaHint = extractPatternKana(pattern);

    el.grammarDetail.innerHTML = `
      <div class="learn-detail">
        <header class="ld-head">
          <div class="ld-word grammar-pattern">${escapeHtml(pattern)}</div>
          ${
            kanaHint
              ? `<div class="ld-kana"><span class="ld-kana-label">平假名</span><span class="ld-kana-text">${escapeHtml(kanaHint)}</span></div>`
              : ""
          }
          <div class="tags"><span class="tag pos">语法</span><span class="${lvlClass}">${escapeHtml(lvl)}</span></div>
        </header>

        <section class="ld-section">
          <h2 class="ld-section-title">接续</h2>
          <div class="ld-section-body">
            ${
              connection
                ? `<div class="grammar-connection-body">${escapeHtml(connection).replace(/\n/g, "<br>")}</div>`
                : `<p class="ld-empty">暂无接续</p>`
            }
          </div>
        </section>

        <section class="ld-section">
          <h2 class="ld-section-title">意思</h2>
          <div class="ld-section-body">
            <div class="grammar-explain-body">${escapeHtml(explain).replace(/\n/g, "<br>") || '<p class="ld-empty">暂无说明</p>'}</div>
          </div>
        </section>

        <section class="ld-section">
          <h2 class="ld-section-title">例句</h2>
          <div class="ld-section-body">
            <p class="ld-empty">暂无固定例句，可问 AI 要例句</p>
          </div>
        </section>

        <section class="ld-section ld-ai">
          <h2 class="ld-section-title">AI</h2>
          <div class="ai-wrap">
            <div class="ai-head">
              <span class="ai-head-title">本地讲解</span>
              <button type="button" class="ai-btn ghost" id="btn-g-ai-auto">本地讲解</button>
            </div>
            <div id="g-ai-chat" class="ai-chat" aria-live="polite"></div>
            <div class="ai-input-row">
              <input id="g-ai-input" type="text" placeholder="问关于这个语法的问题…" maxlength="400" autocomplete="off" />
              <button type="button" class="ai-send" id="btn-g-ai-send">发送</button>
            </div>
          </div>
        </section>

      </div>
    `;
    bindGrammarAiControls();
  }

  async function openGrammarDetail(gid) {
    gAiId = Number(gid);
    gAiHistory = [];
    if (el.grammarDetail) el.grammarDetail.innerHTML = "<p class='hint'>加载中…</p>";
    try {
      const res = await fetch(`/api/grammar/${encodeURIComponent(gid)}`);
      if (!res.ok) {
        if (el.grammarDetail) el.grammarDetail.innerHTML = "<p class='hint'>未找到该语法</p>";
        return;
      }
      const data = await res.json();
      renderGrammarDetail(data);
    } catch (err) {
      console.error(err);
      if (el.grammarDetail) el.grammarDetail.innerHTML = "<p class='hint'>加载失败</p>";
    }
  }

  // ============ 模考练习 ============

  function showExamPane(pane) {
    if (!el.examHome) return;
    el.examHome.classList.toggle("hidden", pane !== "home");
    el.examSession.classList.toggle("hidden", pane !== "session");
    el.examResult.classList.toggle("hidden", pane !== "result");
    if (pane === "home") renderExamHistory();
  }

  async function readError(res) {
    try {
      const data = await res.json();
      if (data && data.detail) return data.detail;
    } catch {
      /* ignore */
    }
    return `${res.status} ${res.statusText}`;
  }

  function stripHtmlSnippet(html, maxLen) {
    const raw = String(html || "")
      .replace(/<[^>]+>/g, " ")
      .replace(/&nbsp;/gi, " ")
      .replace(/&lt;/gi, "<")
      .replace(/&gt;/gi, ">")
      .replace(/&amp;/gi, "&")
      .replace(/\s+/g, " ")
      .trim();
    const lim = maxLen || 200;
    return raw.length > lim ? raw.slice(0, lim) + "…" : raw;
  }

  function formatDuration(totalSec) {
    const s = Math.max(0, Math.round(Number(totalSec) || 0));
    const m = Math.floor(s / 60);
    const r = s % 60;
    return `${m}:${String(r).padStart(2, "0")}`;
  }

  function accumulateExamQuestionTime() {
    if (examQuestionEnteredAt == null || !examData) return;
    const idx = examIndex;
    if (idx < 0 || idx >= examSeconds.length) {
      examQuestionEnteredAt = null;
      return;
    }
    const delta = (Date.now() - examQuestionEnteredAt) / 1000;
    examSeconds[idx] = (examSeconds[idx] || 0) + Math.max(0, delta);
    examQuestionEnteredAt = null;
  }

  function enterExamQuestionClock() {
    examQuestionEnteredAt = Date.now();
  }

  function getExamLogsLocal() {
    try {
      const raw = localStorage.getItem(EXAM_LOG_KEY);
      const arr = raw ? JSON.parse(raw) : [];
      return Array.isArray(arr) ? arr : [];
    } catch {
      return [];
    }
  }

  function saveExamLogLocal(entry) {
    const list = getExamLogsLocal();
    list.unshift(entry);
    localStorage.setItem(EXAM_LOG_KEY, JSON.stringify(list.slice(0, EXAM_LOG_CAP)));
  }

  async function persistExamLog(entry) {
    try {
      saveExamLogLocal(entry);
    } catch (e) {
      console.warn("exam log local save failed", e);
    }
    try {
      const res = await fetch("/api/exam/log", {
        method: "POST",
        headers: { "Content-Type": "application/json; charset=utf-8" },
        body: JSON.stringify(entry),
      });
      if (!res.ok) {
        console.warn("exam log save failed", await readError(res));
      }
    } catch (e) {
      console.warn("exam log save network error", e);
    }
  }

  function renderExamHistory() {
    if (!el.examHistoryList) return;
    const list = getExamLogsLocal().slice(0, 8);
    el.examHistoryList.innerHTML = "";
    if (el.examHistoryEmpty) {
      el.examHistoryEmpty.classList.toggle("hidden", list.length > 0);
    }
    list.forEach((log) => {
      const li = document.createElement("li");
      li.className = "exam-history-item";
      const title = log.title || log.examId || "练习";
      const score = `${log.correct ?? "?"}/${log.total ?? "?"}`;
      const time = formatDuration(log.totalSeconds);
      let when = "";
      try {
        const d = new Date(log.finishedAt || log.savedAt);
        if (!Number.isNaN(d.getTime())) {
          when = `${d.getMonth() + 1}/${d.getDate()} ${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
        }
      } catch {
        /* ignore */
      }
      const mode = log.modeLabel || (log.subjectFilter ? EXAM_SUBJECT_LABEL[log.subjectFilter] || log.subjectFilter : "整卷");
      li.innerHTML =
        `<span class="eh-title">${escapeHtml(title)}</span>` +
        `<span class="eh-meta">${escapeHtml(mode)}</span>` +
        `<span class="eh-meta">${escapeHtml(score)}</span>` +
        `<span class="eh-meta">${escapeHtml(time)}</span>` +
        (when ? `<span class="eh-meta">${escapeHtml(when)}</span>` : "");
      el.examHistoryList.appendChild(li);
    });
  }

  // ---- 导入本地题库 ----------------------------------------------------
  // 导入的卷子会写到 web/cache/imported_exams/（git 忽略），只在本次机器生效。
  function initExamImport() {
    const btn = document.getElementById("btn-exam-import");
    const input = document.getElementById("exam-import-file");
    const hint = document.getElementById("exam-import-hint");
    const view = document.getElementById("view-exam");
    if (!btn || !input || !hint) return;

    const setHint = (text, ok) => {
      hint.textContent = text;
      hint.classList.toggle("bad", ok === false);
      hint.classList.toggle("good", ok === true);
    };

    async function uploadOne(file) {
      const text = await file.text();
      const res = await fetch(
        `/api/exam/import?filename=${encodeURIComponent(file.name)}`,
        { method: "POST", headers: { "Content-Type": "application/json" }, body: text }
      );
      if (!res.ok) throw new Error(await readError(res));
      return res.json();
    }

    async function handleFiles(fileList) {
      const picked = Array.from(fileList || []).filter((f) => /\.json$/i.test(f.name));
      if (!picked.length) {
        setHint("只支持 .json 文件", false);
        return;
      }
      setHint(`正在导入 ${picked.length} 个文件…`);
      const ok = [];
      const bad = [];
      for (const f of picked) {
        try {
          const r = await uploadOne(f);
          ok.push(`${r.title}（${r.questionCount} 题 · ${r.tag}）`);
        } catch (e) {
          bad.push(`${f.name} — ${e && e.message ? e.message : e}`);
        }
      }
      if (ok.length) setHint(`已导入 ${ok.length} 套：${ok.join("；")}`, true);
      if (bad.length) setHint(`失败 ${bad.length} 个：${bad.join("；")}`, false);
      if (ok.length) loadExamList();
    }

    btn.addEventListener("click", () => input.click());
    input.addEventListener("change", () => {
      const files = input.files;
      input.value = "";
      handleFiles(files);
    });

    if (view) {
      ["dragenter", "dragover"].forEach((ev) =>
        view.addEventListener(ev, (e) => {
          const types = e.dataTransfer && e.dataTransfer.types;
          if (!types || !Array.from(types).includes("Files")) return;
          e.preventDefault();
          view.classList.add("exam-dragging");
        })
      );
      ["dragleave", "drop"].forEach((ev) =>
        view.addEventListener(ev, (e) => {
          e.preventDefault();
          view.classList.remove("exam-dragging");
        })
      );
      view.addEventListener("drop", (e) => {
        handleFiles(e.dataTransfer ? e.dataTransfer.files : null);
      });
    }
  }

  async function loadExamList() {
    if (!el.examList) return;
    el.examList.innerHTML = "";
    el.examEmpty.classList.add("hidden");
    renderExamHistory();
    try {
      const res = await fetch(`/api/exam/list?level=${encodeURIComponent(examLevel)}`);
      if (!res.ok) throw new Error(await readError(res));
      const data = await res.json();
      const list = Array.isArray(data.list) ? data.list : [];
      if (!list.length) {
        el.examEmpty.textContent = "该等级暂无卷子。";
        el.examEmpty.classList.remove("hidden");
        return;
      }
      list.forEach((p) => {
        const li = document.createElement("li");
        li.className = "exam-item";
        const free = p.isFree === true ? '<span class="exam-item-free">免费</span>' : "";
        const imported = p.imported
          ? '<span class="exam-item-imported" title="本地导入，只存在这台机器">本地</span>'
          : "";
        const del = p.imported
          ? '<button type="button" class="exam-item-del" title="删除这套导入的卷子">×</button>'
          : "";
        li.innerHTML =
          `<span class="exam-item-title">${escapeHtml(p.title || p.objectId)}</span>` +
          `<span class="exam-item-tag">${escapeHtml(p.tag || "")}</span>${imported}${free}${del}`;
        li.addEventListener("click", (ev) => {
          if (ev.target.closest(".exam-item-del")) return; // 删除按钮自己处理
          const subj = examDrillSubject;
          location.hash = subj
            ? `#/exam/${p.objectId}/${subj}`
            : `#/exam/${p.objectId}`;
        });
        const delBtn = li.querySelector(".exam-item-del");
        if (delBtn) {
          delBtn.addEventListener("click", async (ev) => {
            ev.stopPropagation();
            if (!confirm(`删除「${p.title || p.objectId}」？只删本地文件，不影响其它卷。`)) return;
            try {
              const r = await fetch(`/api/exam/import/${encodeURIComponent(p.objectId)}`, {
                method: "DELETE",
              });
              if (!r.ok) throw new Error(await readError(r));
              loadExamList();
            } catch (e) {
              alert("删除失败：" + (e && e.message ? e.message : e));
            }
          });
        }
        el.examList.appendChild(li);
      });
    } catch (e) {
      el.examEmpty.textContent = "加载失败：" + (e && e.message ? e.message : "网络错误");
      el.examEmpty.classList.remove("hidden");
    }
  }

  function syncExamDrillChips() {
    const chips = document.getElementById("exam-drill-chips");
    if (!chips) return;    chips.querySelectorAll(".exam-drill-chip").forEach((btn) => {
      const s = btn.getAttribute("data-subject") || "";
      const active = examDrillSubject ? s === examDrillSubject : s === "";
      btn.classList.toggle("selected", active);
    });
  }

  function resetExamTiming(n) {
    examStartedAt = new Date().toISOString();
    examSeconds = new Array(n).fill(0);
    examQuestionEnteredAt = null;
  }

  async function startExam(examId, drillSubject) {
    if (examLoading) return;
    examLoading = true;
    const drill = drillSubject || null;
    examActiveSubject = drill;
    accumulateExamQuestionTime();
    showExamPane("session");
    el.examTitle.textContent = "加载中…";
    el.examProgressText.textContent = "";
    el.examBar.style.width = "0%";
    el.examSubject.textContent = "";
    el.examQuestion.innerHTML = "";
    el.examOptions.innerHTML = "";
    el.examPassage.hidden = true;
    examStartedAt = null;
    examSeconds = [];
    examQuestionEnteredAt = null;
    try {
      const res = await fetch(`/api/exam/${encodeURIComponent(examId)}`);
      if (!res.ok) throw new Error(await readError(res));
      const data = await res.json();
      const allQs = Array.isArray(data.questions) ? data.questions : [];
      if (!allQs.length) {
        throw new Error(data.incomplete ? "题目加载不完整，请重试" : "没有题目");
      }
      let questions = allQs;
      let title = data.title || "";
      if (data.incomplete) title = `${title}（部分题目未加载，重新进入可重试）`;
      if (drill) {
        questions = allQs.filter((q) => q.subject === drill);
        const label = EXAM_SUBJECT_LABEL[drill] || drill;
        title = `${title} · ${label}专项`;
      }
      if (!questions.length) {
        const label = EXAM_SUBJECT_LABEL[drill] || drill || "该科";
        examData = { ...data, questions: [], title };
        examIndex = 0;
        examAnswers = [];
        examSeconds = [];
        examStartedAt = null;
        el.examTitle.textContent = title;
        el.examProgressText.textContent = "0/0";
        el.examBar.style.width = "0%";
        el.examSubject.textContent = "";
        el.examPassage.hidden = true;
        el.examPassage.innerHTML = "";
        el.examQuestion.textContent = `该卷没有${label}题`;
        el.examOptions.innerHTML = "";
        if (el.btnExamPrev) el.btnExamPrev.disabled = true;
        if (el.btnExamNext) el.btnExamNext.disabled = true;
        return;
      }
      examData = { ...data, questions, title };
      examIndex = 0;
      examAnswers = new Array(questions.length).fill(null);
      resetExamTiming(questions.length);
      renderExamQuestion();
    } catch (e) {
      el.examTitle.textContent = "加载失败";
      el.examQuestion.textContent = e && e.message ? e.message : "网络错误";
    } finally {
      examLoading = false;
    }
  }

  function renderExamQuestion() {
    if (!examData) return;
    const q = examData.questions[examIndex];
    if (!q) return;
    el.examTitle.textContent = examData.title || "";
    el.examProgressText.textContent = `${examIndex + 1}/${examData.questions.length}`;
    el.examBar.style.width = `${(((examIndex + 1) / examData.questions.length) * 100).toFixed(1)}%`;
    const subj = EXAM_SUBJECT_LABEL[q.subject] || q.subject || "";
    el.examSubject.textContent = subj + (q.sectionTitle ? " · " + q.sectionTitle : "");

    // 听力：音频 + 原文/翻译
    if (q.audioUrl) {
      if (el.examMedia) {
        el.examMedia.hidden = false;
        if (el.examAudio) {
          el.examAudio.src = q.audioUrl;
          el.examAudio.load();
        }
      }
      if (el.examTranscript) {
        el.examTranscript.hidden = false;
        if (el.examSubtitle) el.examSubtitle.innerHTML = sanitizeExamHtml(q.subtitle);
        if (el.examTranslation) el.examTranslation.innerHTML = sanitizeExamHtml(q.translation);
      }
    } else {
      if (el.examMedia) el.examMedia.hidden = true;
      if (el.examTranscript) el.examTranscript.hidden = true;
      if (el.examAudio) {
        el.examAudio.pause();
        el.examAudio.removeAttribute("src");
      }
    }

    if (q.passage) {
      el.examPassage.innerHTML = sanitizeExamHtml(q.passage);
      el.examPassage.hidden = false;
    } else {
      el.examPassage.hidden = true;
      el.examPassage.innerHTML = "";
    }
    el.examQuestion.innerHTML = sanitizeExamHtml(q.title);

    el.examOptions.innerHTML = "";
    const selected = examAnswers[examIndex];
    const opts = Array.isArray(q.options) ? q.options : [];
    opts.forEach((opt, i) => {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "exam-option" + (i === selected ? " selected" : "");
      btn.innerHTML = `<span class="opt-idx">${i + 1}</span><span class="opt-text">${escapeHtml(opt)}</span>`;
      btn.addEventListener("click", () => selectExamOption(i));
      el.examOptions.appendChild(btn);
    });

    if (el.btnExamPrev) el.btnExamPrev.disabled = examIndex === 0;
    if (el.btnExamNext) el.btnExamNext.disabled = examIndex >= examData.questions.length - 1;
    enterExamQuestionClock();
  }

  function selectExamOption(i) {
    if (!examData) return;
    examAnswers[examIndex] = i;
    [...el.examOptions.children].forEach((btn, idx) => {
      btn.classList.toggle("selected", idx === i);
    });
  }

  function examNav(delta) {
    if (!examData) return;
    const next = examIndex + delta;
    if (next < 0 || next >= examData.questions.length) return;
    accumulateExamQuestionTime();
    examIndex = next;
    renderExamQuestion();
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  function buildExamLogEntry(stats) {
    const finishedAt = new Date().toISOString();
    const subjectFilter = examActiveSubject || null;
    const modeLabel = subjectFilter
      ? (EXAM_SUBJECT_LABEL[subjectFilter] || subjectFilter) + "专项"
      : "整卷";
    const questions = examData.questions.map((q, i) => {
      const sel = examAnswers[i];
      const sec = Math.round((examSeconds[i] || 0) * 10) / 10;
      return {
        index: i,
        subject: q.subject || null,
        sectionTitle: q.sectionTitle ? String(q.sectionTitle).slice(0, 80) : null,
        selected: sel == null ? null : sel,
        answer: q.answer,
        correct: sel === q.answer,
        seconds: sec,
        questionTitle: stripHtmlSnippet(q.title, 200),
      };
    });
    const stamp = finishedAt.replace(/[-:]/g, "").replace("T", "-").slice(0, 15);
    const id = `${stamp}_${examData.objectId || "exam"}_${subjectFilter || "full"}`;
    return {
      id,
      savedAt: finishedAt,
      examId: examData.objectId || "",
      title: examData.title || "",
      level: examLevel,
      tag: examData.tag || null,
      subjectFilter,
      modeLabel,
      total: stats.total,
      correct: stats.correct,
      blank: stats.blank,
      accuracy: stats.total ? Math.round((stats.correct / stats.total) * 1000) / 10 : 0,
      startedAt: examStartedAt || finishedAt,
      finishedAt,
      totalSeconds: stats.totalSeconds,
      questions,
    };
  }

  function renderExamResultTiming(stats) {
    if (!el.examResultTiming) return;
    const avg = stats.total ? stats.totalSeconds / stats.total : 0;
    const ranked = examSeconds
      .map((s, i) => ({ i, s: s || 0 }))
      .sort((a, b) => b.s - a.s)
      .slice(0, 3)
      .filter((x) => x.s > 0);
    let slowHtml = "";
    if (ranked.length) {
      slowHtml =
        `<div class="timing-slow">最慢：` +
        ranked
          .map((x) => `第${x.i + 1}题 ${formatDuration(x.s)}`)
          .join(" · ") +
        `</div>`;
    }
    el.examResultTiming.hidden = false;
    el.examResultTiming.innerHTML =
      `<div class="timing-row">` +
      `<span>总用时 <strong>${formatDuration(stats.totalSeconds)}</strong></span>` +
      `<span>平均每题 <strong>${avg.toFixed(1)}s</strong></span>` +
      `</div>${slowHtml}`;
  }

  function submitExam() {
    if (!examData || !examData.questions.length) return;
    const total = examData.questions.length;
    const answered = examAnswers.filter((a) => a !== null && a !== undefined).length;
    let correct = 0;
    examData.questions.forEach((q, i) => {
      if (examAnswers[i] === q.answer) correct++;
    });
    const blank = total - answered;
    if (blank > 0 && !confirm(`还有 ${blank} 题未作答，确定交卷吗？`)) return;
    accumulateExamQuestionTime();
    const totalSeconds = Math.round(
      examSeconds.reduce((sum, s) => sum + (s || 0), 0)
    );
    const stats = { total, correct, blank, totalSeconds };
    // 先建日志并落盘，再渲染：renderExamReview 一旦抛异常，不能把成绩/复查/日志一起带走
    try {
      persistExamLog(buildExamLogEntry(stats));
    } catch (err) {
      console.error("exam log build failed", err);
    }
    el.examResultStats.textContent = `答对 ${correct} / ${total} · 未答 ${blank}`;
    try {
      renderExamResultTiming(stats);
    } catch (err) {
      console.error("timing render failed", err);
    }
    try {
      renderExamReview();
    } catch (err) {
      console.error("review render failed", err);
      if (el.examReview) {
        el.examReview.innerHTML =
          `<div class="rv-empty">复查渲染失败：${escapeHtml(err && err.message ? err.message : err)}</div>`;
      }
    }
    showExamPane("result");
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  function renderExamReview() {
    if (!examData) return;
    el.examReview.innerHTML = "";
    examData.questions.forEach((q, i) => {
      const sel = examAnswers[i];
      const ok = sel === q.answer;
      const subj = EXAM_SUBJECT_LABEL[q.subject] || q.subject || "";
      const sec = Math.round((examSeconds[i] || 0) * 10) / 10;
      const div = document.createElement("div");
      div.className = "exam-review-item " + (ok ? "ok" : "bad");
      let html = `<div class="rv-head"><span class="rv-no">第 ${i + 1} 题</span><span class="rv-subj">${escapeHtml(subj)}</span><span class="rv-mark">${ok ? "✓ 答对" : sel == null ? "— 未答" : "✗ 答错"}</span><span class="eh-meta">${sec}s</span></div>`;
      if (q.passage) html += `<div class="rv-passage">${sanitizeExamHtml(q.passage)}</div>`;
      if (q.audioUrl) {
        html += `<div class="rv-audio"><audio controls preload="none" src="${escapeHtml(q.audioUrl)}"></audio></div>`;
      }
      html += `<div class="rv-question">${sanitizeExamHtml(q.title)}</div>`;
      html +=
        `<div class="rv-options">` +
        (Array.isArray(q.options) ? q.options : [])
          .map((opt, oi) => {
            let cls = "";
            if (oi === q.answer) cls = "correct";
            else if (oi === sel) cls = "wrong";
            return `<div class="rv-opt ${cls}"><span class="opt-idx">${oi + 1}</span><span class="opt-text">${escapeHtml(opt)}</span></div>`;
          })
          .join("") +
        `</div>`;
      if (q.subtitle) {
        html += `<div class="rv-transcript"><strong>原文</strong>${sanitizeExamHtml(q.subtitle)}</div>`;
      }
      if (q.translation) {
        html += `<div class="rv-transcript"><strong>翻译</strong>${sanitizeExamHtml(q.translation)}</div>`;
      }
      if (q.analysis) {
        html += `<div class="rv-analysis"><strong>解析</strong>${escapeHtml(q.analysis).replace(/\n/g, "<br>")}</div>`;
      }
      div.innerHTML = html;
      el.examReview.appendChild(div);
    });
  }

  const examDrillChips = document.getElementById("exam-drill-chips");
  if (examDrillChips) {
    examDrillChips.addEventListener("click", (e) => {
      const btn = e.target.closest(".exam-drill-chip");
      if (!btn) return;
      const s = btn.getAttribute("data-subject") || "";
      examDrillSubject = s || null;
      syncExamDrillChips();
    });
  }
  if (el.examLevel) {
    el.examLevel.addEventListener("change", () => {
      examLevel = el.examLevel.value;
      loadExamList();
    });
  }
  if (el.btnExamBack) {
    el.btnExamBack.addEventListener("click", () => {
      accumulateExamQuestionTime();
      location.hash = "#/exam";
    });
  }
  if (el.btnExamPrev) el.btnExamPrev.addEventListener("click", () => examNav(-1));
  if (el.btnExamNext) el.btnExamNext.addEventListener("click", () => examNav(1));
  if (el.btnExamSubmit) el.btnExamSubmit.addEventListener("click", submitExam);
  if (el.btnExamHome) el.btnExamHome.addEventListener("click", () => { location.hash = "#/exam"; });

  if (el.grammarLevelChips) {
    el.grammarLevelChips.addEventListener("click", (ev) => {
      const btn = ev.target.closest(".grammar-level-chip");
      if (!btn || !btn.dataset.level) return;
      grammarLevel = btn.dataset.level;
      syncGrammarLevelChips();
      if ((location.hash || "").startsWith("#/grammar") && !location.hash.startsWith("#/grammar/")) {
        resetGrammarBrowse();
      }
    });
  }

  let grammarSearchTimer = null;
  if (el.grammarQ) {
    el.grammarQ.addEventListener("input", () => {
      syncGrammarClearBtn();
      clearTimeout(grammarSearchTimer);
      grammarSearchTimer = setTimeout(() => {
        if ((location.hash || "").startsWith("#/grammar") && !location.hash.startsWith("#/grammar/")) {
          resetGrammarBrowse();
        }
      }, 280);
    });
  }
  if (el.btnGrammarClear) {
    el.btnGrammarClear.addEventListener("click", () => {
      if (el.grammarQ) el.grammarQ.value = "";
      syncGrammarClearBtn();
      if ((location.hash || "").startsWith("#/grammar") && !location.hash.startsWith("#/grammar/")) {
        resetGrammarBrowse();
      }
    });
  }
  if (el.btnGrammarMore) {
    el.btnGrammarMore.addEventListener("click", () => loadGrammarPage(true));
  }
  if (el.btnGrammarBack) {
    el.btnGrammarBack.addEventListener("click", () => {
      if (window.history.length > 1) history.back();
      else location.hash = "#/grammar";
    });
  }

  window.addEventListener("hashchange", route);
  initExamImport();
  syncClearBtn();
  refreshDailyUI();
  if (el.btnWeaknessRefresh) {
    el.btnWeaknessRefresh.addEventListener("click", () => refreshWeakness());
  }
  refreshWeakness();
  route();
})();
