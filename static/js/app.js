/* 法警特考考古題系統 — 前端 JS v2 */
'use strict';

// ── Constants ──
const SUBJECT_COLORS = {
  '行政法概要': '#3b82f6', '刑法概要': '#ef4444',
  '刑事訴訟法概要': '#f97316', '法院組織法': '#8b5cf6',
  '法學知識與英文': '#10b981', '國文': '#f59e0b',
};
const MCQ_SUBJECTS = ['行政法概要', '刑法概要', '法學知識與英文'];
const ALL_SUBJECTS = ['行政法概要', '刑法概要', '刑事訴訟法概要', '法院組織法', '法學知識與英文', '國文'];
const PAGE_SIZE = 20;

// ── State ──
let stats = null;
let practiceQuestions = [];
let practiceIndex = 0;
let practiceCorrect = 0;
let practiceWrong = 0;
let browseOffset = 0;
let browseTotalCount = 0;

// ── Init ──
document.addEventListener('DOMContentLoaded', async () => {
  initDarkMode();
  initTabs();
  initEventListeners();
  await Promise.all([loadStats(), loadYears()]);
  populateSubjectSelects();
});

// ═══════════════════════════════════════════
// Dark Mode
// ═══════════════════════════════════════════
function initDarkMode() {
  if (localStorage.getItem('dark') === 'true') {
    document.documentElement.classList.add('dark');
    document.body.style.background = '#111827';
  }
}

function toggleDark() {
  const isDark = document.documentElement.classList.toggle('dark');
  document.body.style.background = isDark ? '#111827' : '#f8fafc';
  localStorage.setItem('dark', isDark);
}

// ═══════════════════════════════════════════
// Tab Navigation (data-tab event delegation)
// ═══════════════════════════════════════════
function initTabs() {
  document.querySelectorAll('[data-tab]').forEach(btn => {
    btn.addEventListener('click', () => showTab(btn.dataset.tab));
  });
}

function showTab(name) {
  // Hide all tab content
  document.querySelectorAll('.tab-content').forEach(el => el.classList.add('hidden'));
  // Deactivate all tab buttons
  document.querySelectorAll('[data-tab]').forEach(btn => {
    btn.classList.remove('active');
    if (btn.dataset.tab === name) btn.classList.add('active');
  });
  // Show target
  const target = document.getElementById('tab-' + name);
  if (target) {
    target.classList.remove('hidden');
    target.classList.add('tab-animate');
  }
  // Lazy load browse
  if (name === 'browse') loadBrowse(1);
}

// ═══════════════════════════════════════════
// Event Listeners
// ═══════════════════════════════════════════
function initEventListeners() {
  document.getElementById('btn-start-practice')?.addEventListener('click', startPractice);
  document.getElementById('btn-end-practice')?.addEventListener('click', endPractice);
  document.getElementById('btn-retry')?.addEventListener('click', startPractice);
  document.getElementById('btn-back-setup')?.addEventListener('click', endPractice);
  document.getElementById('browse-subject')?.addEventListener('change', () => loadBrowse(1));
  document.getElementById('browse-year')?.addEventListener('change', () => loadBrowse(1));
  document.getElementById('browse-type')?.addEventListener('change', () => loadBrowse(1));
  document.getElementById('browse-prev')?.addEventListener('click', () => browsePage(-1));
  document.getElementById('browse-next')?.addEventListener('click', () => browsePage(1));

  // Keyword search with debounce
  let keywordTimer;
  document.getElementById('browse-keyword')?.addEventListener('input', () => {
    clearTimeout(keywordTimer);
    keywordTimer = setTimeout(() => loadBrowse(1), 400);
  });
}

// ═══════════════════════════════════════════
// Populate Subject Selects
// ═══════════════════════════════════════════
function populateSubjectSelects() {
  const subjects = stats ? Object.keys(stats.subjects) : ALL_SUBJECTS;
  ['practice-subject', 'browse-subject'].forEach(id => {
    const sel = document.getElementById(id);
    if (!sel) return;
    // Clear existing options except first
    while (sel.options.length > 1) sel.remove(1);
    subjects.forEach(s => {
      const opt = document.createElement('option');
      opt.value = s;
      const isMCQ = MCQ_SUBJECTS.includes(s);
      opt.textContent = s + (isMCQ ? '' : '（申論）');
      sel.appendChild(opt);
    });
  });
}

// ═══════════════════════════════════════════
// Load Stats
// ═══════════════════════════════════════════
async function loadStats() {
  try {
    const r = await fetch('/api/stats');
    stats = await r.json();
    const mcqCount = (stats.types['選擇題'] || 0);
    // Update header
    document.getElementById('header-sub').textContent =
      `題庫：${stats.total} 題 ｜ ${stats.years_range[0]}–${stats.years_range[1]} 年度`;

    renderStatCards(mcqCount);
    renderCharts();
    renderSubjectShortcuts();
  } catch (e) {
    console.error('載入統計失敗', e);
    document.getElementById('header-sub').textContent = '載入失敗';
  }
}

async function loadYears() {
  try {
    const r = await fetch('/api/years');
    const years = await r.json();
    ['practice-year', 'browse-year'].forEach(id => {
      const sel = document.getElementById(id);
      if (!sel) return;
      years.forEach(({ roc_year }) => {
        const opt = document.createElement('option');
        opt.value = roc_year;
        opt.textContent = roc_year + ' 年';
        sel.appendChild(opt);
      });
    });
  } catch (e) {
    console.error('載入年度失敗', e);
  }
}

// ═══════════════════════════════════════════
// Stat Cards
// ═══════════════════════════════════════════
function renderStatCards(mcqCount) {
  // Count questions with answers
  const ansCount = stats._answerCount || 0;  // We'll get this from the API or compute

  const cards = [
    { label: '總題數', value: stats.total, color: '#1a365d' },
    { label: '選擇題', value: mcqCount, color: '#2563eb' },
    { label: '申論題', value: stats.types['申論題'] || 0, color: '#7c3aed' },
    { label: '年度數', value: Object.keys(stats.years).length, color: '#059669' },
  ];
  document.getElementById('stat-cards').innerHTML = cards.map(c => `
    <div class="stat-card">
      <div class="stat-number" style="color:${c.color}">${c.value}</div>
      <div class="stat-label">${c.label}</div>
    </div>`).join('');
}

// ═══════════════════════════════════════════
// Charts
// ═══════════════════════════════════════════
function renderCharts() {
  const subjects = Object.entries(stats.subjects);

  // Doughnut
  new Chart(document.getElementById('chart-subjects'), {
    type: 'doughnut',
    data: {
      labels: subjects.map(([s]) => s),
      datasets: [{
        data: subjects.map(([, n]) => n),
        backgroundColor: subjects.map(([s]) => SUBJECT_COLORS[s] || '#9ca3af'),
        borderWidth: 2,
        borderColor: '#fff',
      }]
    },
    options: {
      plugins: {
        legend: { position: 'bottom', labels: { font: { size: 11, family: 'Noto Sans TC' }, padding: 12 } }
      }
    }
  });

  // Stacked bar trend
  const trend = stats.trend;
  const years = Object.keys(trend).sort();
  const subjectList = subjects.map(([s]) => s);
  new Chart(document.getElementById('chart-trend'), {
    type: 'bar',
    data: {
      labels: years.map(y => y + '年'),
      datasets: subjectList.map(s => ({
        label: s, stack: 'stack',
        data: years.map(y => trend[y]?.[s] || 0),
        backgroundColor: SUBJECT_COLORS[s] || '#9ca3af',
        borderRadius: 2,
      }))
    },
    options: {
      plugins: { legend: { position: 'bottom', labels: { font: { size: 10, family: 'Noto Sans TC' }, padding: 8 } } },
      scales: { x: { stacked: true }, y: { stacked: true, beginAtZero: true } }
    }
  });
}

// ═══════════════════════════════════════════
// Subject Shortcuts
// ═══════════════════════════════════════════
function renderSubjectShortcuts() {
  const el = document.getElementById('subject-shortcuts');
  el.innerHTML = Object.entries(stats.subjects).map(([s, n]) => {
    const isMCQ = MCQ_SUBJECTS.includes(s);
    return `
    <button class="study-domain-card" onclick="quickPractice('${s}')">
      <div class="domain-name" style="color:${SUBJECT_COLORS[s] || '#1a365d'}">${s}</div>
      <div class="domain-count">${n} 題 · ${isMCQ ? '選擇題' : '申論題'}</div>
      <div class="domain-bar"><div class="domain-bar-fill" style="width:${Math.round(n / stats.total * 100)}%;background:${SUBJECT_COLORS[s]}"></div></div>
    </button>`;
  }).join('');
}

function quickPractice(subject) {
  showTab('practice');
  document.getElementById('practice-subject').value = subject;
  document.getElementById('practice-type').value = MCQ_SUBJECTS.includes(subject) ? 'mcq' : 'essay';
  startPractice();
}

// ═══════════════════════════════════════════
// Practice Mode
// ═══════════════════════════════════════════
async function startPractice() {
  const subject = document.getElementById('practice-subject').value;
  const year = document.getElementById('practice-year').value;
  const type = document.getElementById('practice-type').value;
  const count = parseInt(document.getElementById('practice-count').value) || 20;

  const params = new URLSearchParams({ count, q_type: type });
  if (subject) params.set('subject', subject);
  if (year) params.set('year', year);

  try {
    const r = await fetch('/api/practice/session?' + params, { method: 'POST' });
    const data = await r.json();
    if (!r.ok || !data.questions?.length) {
      alert(data.detail || '無符合條件的題目');
      return;
    }

    practiceQuestions = data.questions;
    practiceIndex = 0;
    practiceCorrect = 0;
    practiceWrong = 0;

    document.getElementById('practice-setup').classList.add('hidden');
    document.getElementById('practice-area').classList.remove('hidden');
    document.getElementById('result-banner').classList.add('hidden');
    document.getElementById('question-container').classList.remove('hidden');
    document.getElementById('q-total').textContent = practiceQuestions.length;

    // Build progress bar segments
    const bar = document.getElementById('practice-progress-bar');
    bar.innerHTML = practiceQuestions.map((_, i) =>
      `<div class="progress-segment ${i === 0 ? 'current' : 'unanswered'}" data-idx="${i}"></div>`
    ).join('');

    renderQuestion();
  } catch (e) {
    alert('載入失敗：' + e.message);
  }
}

function renderQuestion() {
  const q = practiceQuestions[practiceIndex];
  if (!q) { showResult(); return; }

  // Update counters
  document.getElementById('q-current').textContent = practiceIndex + 1;
  document.getElementById('q-correct').textContent = practiceCorrect;
  document.getElementById('q-wrong').textContent = practiceWrong;

  // Update progress segments
  document.querySelectorAll('.progress-segment').forEach((seg, i) => {
    seg.classList.remove('current');
    if (i === practiceIndex) seg.classList.add('current');
  });

  const container = document.getElementById('question-container');
  const color = SUBJECT_COLORS[q.subject] || '#6b7280';

  // Essay question
  if (q.type === 'essay') {
    container.innerHTML = `
      <div class="question-card">
        <div class="question-meta">
          <span class="badge" style="background:${color};color:#fff;">${q.subject}</span>
          <span class="badge badge-year">${q.roc_year} 年 · 申論題</span>
        </div>
        <div class="question-stem">${escapeHtml(q.stem)}</div>
        <button class="btn-primary" onclick="nextQuestion()">
          ${practiceIndex + 1 < practiceQuestions.length ? '下一題 →' : '完成練習'}
        </button>
      </div>`;
    return;
  }

  // MCQ question
  const opts = Object.entries(q.options || {});
  container.innerHTML = `
    <div class="question-card" id="q-card">
      <div class="question-meta">
        <span class="badge" style="background:${color};color:#fff;">${q.subject}</span>
        <span class="badge badge-year">${q.roc_year} 年</span>
      </div>
      <div class="question-stem">${practiceIndex + 1}. ${escapeHtml(q.stem)}</div>
      <ul class="option-list" id="options-container">
        ${opts.map(([k, v]) => `
          <li class="option-item option-clickable" data-key="${k}" onclick="submitAnswer('${q.id}','${k}',this)">
            <span style="font-weight:600;margin-right:0.5rem;min-width:1.5rem;">${k}.</span>${escapeHtml(v)}
          </li>`).join('')}
      </ul>
      <div id="answer-feedback" class="hidden" style="margin-top:1rem;padding:0.75rem;border-radius:0.5rem;font-size:0.875rem;"></div>
    </div>`;
}

async function submitAnswer(qId, answer, el) {
  // Disable all options
  document.querySelectorAll('.option-clickable').forEach(b => {
    b.style.pointerEvents = 'none';
    b.classList.remove('option-clickable');
  });

  try {
    const r = await fetch(`/api/practice/check?q_id=${encodeURIComponent(qId)}&answer=${answer}`, { method: 'POST' });
    const result = await r.json();
    const fb = document.getElementById('answer-feedback');
    fb.classList.remove('hidden');

    const seg = document.querySelectorAll('.progress-segment')[practiceIndex];

    if (result.is_correct === null) {
      el.style.background = '#fef9c3';
      el.style.borderColor = '#ca8a04';
      fb.style.background = '#fef9c3';
      fb.style.color = '#78350f';
      fb.innerHTML = `⚠️ 此題答案尚未收錄`;
      if (seg) { seg.classList.remove('current'); seg.style.background = '#fbbf24'; }
    } else if (result.is_correct) {
      el.classList.add('selected', 'correct');
      fb.style.background = '#dcfce7';
      fb.style.color = '#166534';
      fb.innerHTML = `✅ 正確！`;
      if (result.explanation) fb.innerHTML += `<div style="margin-top:0.5rem;font-size:0.8rem;opacity:0.8;">${escapeHtml(result.explanation)}</div>`;
      practiceCorrect++;
      if (seg) { seg.classList.remove('current'); seg.classList.add('correct'); }
    } else {
      el.classList.add('selected', 'wrong');
      // Highlight correct answer
      document.querySelectorAll('#options-container .option-item').forEach(b => {
        if (b.dataset.key === result.correct) b.classList.add('reveal-correct');
      });
      fb.style.background = '#fee2e2';
      fb.style.color = '#991b1b';
      fb.innerHTML = `❌ 正確答案：<strong>${result.correct}</strong>`;
      if (result.explanation) fb.innerHTML += `<div style="margin-top:0.5rem;font-size:0.8rem;opacity:0.8;">${escapeHtml(result.explanation)}</div>`;
      practiceWrong++;
      if (seg) { seg.classList.remove('current'); seg.classList.add('wrong'); }
    }

    // Add next button
    const nextBtn = document.createElement('button');
    nextBtn.textContent = practiceIndex + 1 < practiceQuestions.length ? '下一題 →' : '查看結果';
    nextBtn.className = 'btn-primary';
    nextBtn.style.marginTop = '1rem';
    nextBtn.style.display = 'block';
    nextBtn.onclick = nextQuestion;
    document.getElementById('q-card').appendChild(nextBtn);
  } catch (e) {
    nextQuestion();
  }
}

function nextQuestion() {
  practiceIndex++;
  if (practiceIndex >= practiceQuestions.length) showResult();
  else renderQuestion();
}

function showResult() {
  document.getElementById('question-container').classList.add('hidden');
  document.getElementById('result-banner').classList.remove('hidden');
  const mcqTotal = practiceQuestions.filter(q => q.type === 'mcq').length;
  const pct = mcqTotal > 0 ? Math.round((practiceCorrect / mcqTotal) * 100) : 0;
  document.getElementById('result-emoji').textContent = pct >= 80 ? '🏆' : pct >= 60 ? '👍' : '💪';
  document.getElementById('result-title').textContent =
    mcqTotal > 0 ? `答對 ${practiceCorrect} / ${mcqTotal} 題（${pct}%）` : `閱讀完成 ${practiceQuestions.length} 題`;
  document.getElementById('result-subtitle').textContent =
    pct >= 80 ? '表現優異！繼續保持 🎉' : pct >= 60 ? '不錯！繼續加油 💪' : mcqTotal > 0 ? '多練幾遍，熟能生巧 📚' : '';
}

function endPractice() {
  document.getElementById('practice-setup').classList.remove('hidden');
  document.getElementById('practice-area').classList.add('hidden');
}

// ═══════════════════════════════════════════
// Browse / Search
// ═══════════════════════════════════════════
async function loadBrowse(page) {
  if (page !== undefined) browseOffset = (page - 1) * PAGE_SIZE;

  const subject = document.getElementById('browse-subject')?.value || '';
  const year = document.getElementById('browse-year')?.value || '';
  const type = document.getElementById('browse-type')?.value || '';
  const keyword = document.getElementById('browse-keyword')?.value?.trim() || '';

  const params = new URLSearchParams({ limit: PAGE_SIZE, offset: browseOffset });
  if (subject) params.set('subject', subject);
  if (year) params.set('year', year);
  if (type) params.set('type', type);
  if (keyword) params.set('keyword', keyword);

  try {
    const r = await fetch('/api/questions?' + params);
    const data = await r.json();
    browseTotalCount = data.total;
    const curPage = Math.floor(browseOffset / PAGE_SIZE) + 1;
    const totalPages = Math.ceil(data.total / PAGE_SIZE) || 1;

    document.getElementById('browse-count').textContent = `共 ${data.total} 題`;
    document.getElementById('browse-page-info').textContent = `第 ${curPage} / ${totalPages} 頁`;
    document.getElementById('browse-prev').disabled = curPage <= 1;
    document.getElementById('browse-next').disabled = curPage >= totalPages;

    const list = document.getElementById('browse-list');
    if (!data.questions.length) {
      list.innerHTML = '<div class="empty-state">無符合條件的題目</div>';
      return;
    }

    list.innerHTML = data.questions.map(q => {
      const color = SUBJECT_COLORS[q.subject] || '#6b7280';
      const hasAnswer = q.answer != null;
      return `
      <div class="question-card">
        <div class="question-meta">
          <span class="badge" style="background:${color};color:#fff;">${q.subject}</span>
          <span class="badge badge-year">${q.roc_year} 年</span>
          <span class="badge" style="background:${q.type === 'mcq' ? '#e0f2fe' : '#fce7f3'};color:${q.type === 'mcq' ? '#0369a1' : '#9d174d'};">${q.type === 'mcq' ? '選擇題' : '申論題'}</span>
          ${hasAnswer ? '<span class="ans-badge has-ans">有答案</span>' : '<span class="ans-badge no-ans">待補</span>'}
        </div>
        <div class="question-stem">${q.question_number}. ${escapeHtml(q.stem)}</div>
        ${q.options && Object.keys(q.options).length ? `
          <ul class="option-list" style="margin-top:0.5rem;">
            ${Object.entries(q.options).map(([k, v]) => `
              <li class="option-item" style="padding:0.4rem 0.6rem;font-size:0.85rem;${hasAnswer && q.answer === k ? 'background:#dcfce7;color:#166534;font-weight:600;border-radius:0.375rem;' : ''}">
                <span style="font-weight:600;margin-right:0.375rem;">${k}.</span>${escapeHtml(v)}
              </li>`).join('')}
          </ul>` : ''}
        ${hasAnswer ? `<div style="margin-top:0.5rem;font-size:0.8rem;color:#16a34a;font-weight:600;">答案：${q.answer}</div>` : ''}
      </div>`;
    }).join('');
  } catch (e) {
    document.getElementById('browse-list').innerHTML = '<div class="empty-state" style="color:#ef4444;">載入失敗</div>';
  }
}

function browsePage(dir) {
  const cur = Math.floor(browseOffset / PAGE_SIZE) + 1;
  const total = Math.ceil(browseTotalCount / PAGE_SIZE);
  const next = cur + dir;
  if (next < 1 || next > total) return;
  browseOffset = (next - 1) * PAGE_SIZE;
  loadBrowse();
}

// ═══════════════════════════════════════════
// Utilities
// ═══════════════════════════════════════════
function escapeHtml(str) {
  if (!str) return '';
  return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;').replace(/'/g, '&#039;');
}
