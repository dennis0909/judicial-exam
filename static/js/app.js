/* 法警特考考古題系統 — 前端 JS v1 */
'use strict';

// ── State ──
let stats = null;
let practiceQuestions = [];
let practiceIndex = 0;
let practiceCorrect = 0;
let practiceWrong = 0;
let browseOffset = 0;
let browseTotalCount = 0;
const PAGE_SIZE = 20;

const SUBJECT_COLORS = {
  '行政法概要': '#3b82f6',
  '刑法概要': '#ef4444',
  '刑事訴訟法概要': '#f97316',
  '法院組織法': '#8b5cf6',
  '法學知識與英文': '#10b981',
  '國文': '#f59e0b',
};

// ── Init ──
document.addEventListener('DOMContentLoaded', async () => {
  await loadStats();
  await loadYears();
});

async function loadStats() {
  try {
    const r = await fetch('/api/stats');
    stats = await r.json();
    document.getElementById('header-sub').textContent =
      `題庫：${stats.total} 題 ｜ ${stats.years_range[0]}-${stats.years_range[1]} 年度`;
    renderStatCards();
    renderCharts();
    renderSubjectShortcuts();
  } catch (e) {
    console.error('載入統計失敗', e);
  }
}

async function loadYears() {
  try {
    const r = await fetch('/api/years');
    const years = await r.json();
    ['practice-year', 'browse-year'].forEach(id => {
      const sel = document.getElementById(id);
      years.forEach(({ roc_year }) => {
        const opt = document.createElement('option');
        opt.value = roc_year;
        opt.textContent = roc_year + ' 年';
        sel.appendChild(opt);
      });
    });
  } catch (e) {}
}

// ── Stat Cards ──
function renderStatCards() {
  const cards = [
    { label: '總題數', value: stats.total, color: '#1a3a5c' },
    { label: '選擇題', value: stats.types['選擇題'] || 0, color: '#2563eb' },
    { label: '申論題', value: stats.types['申論題'] || 0, color: '#7c3aed' },
    { label: '年度數', value: Object.keys(stats.years).length, color: '#059669' },
  ];
  document.getElementById('stat-cards').innerHTML = cards.map(c => `
    <div class="bg-white rounded-xl shadow-sm p-4 text-center">
      <div class="text-3xl font-bold" style="color:${c.color}">${c.value}</div>
      <div class="text-sm text-gray-500 mt-1">${c.label}</div>
    </div>`).join('');
}

// ── Charts ──
function renderCharts() {
  const subjects = Object.entries(stats.subjects);
  new Chart(document.getElementById('chart-subjects'), {
    type: 'doughnut',
    data: {
      labels: subjects.map(([s]) => s),
      datasets: [{ data: subjects.map(([, n]) => n), backgroundColor: subjects.map(([s]) => SUBJECT_COLORS[s] || '#9ca3af') }]
    },
    options: { plugins: { legend: { position: 'bottom', labels: { font: { size: 11 } } } } }
  });

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
      }))
    },
    options: {
      plugins: { legend: { position: 'bottom', labels: { font: { size: 10 } } } },
      scales: { x: { stacked: true }, y: { stacked: true, beginAtZero: true } }
    }
  });
}

// ── Shortcuts ──
function renderSubjectShortcuts() {
  document.getElementById('subject-shortcuts').innerHTML = Object.entries(stats.subjects).map(([s, n]) => `
    <button onclick="quickPractice('${s}')" class="rounded-xl p-4 text-left text-white hover:opacity-90 transition-opacity"
      style="background:${SUBJECT_COLORS[s] || '#6b7280'}">
      <div class="font-semibold text-sm">${s}</div>
      <div class="text-xs mt-1 opacity-80">${n} 題</div>
    </button>`).join('');
}

function quickPractice(subject) {
  showTab('practice');
  document.getElementById('practice-subject').value = subject;
  const mcq = ['行政法概要', '刑法概要'];
  document.getElementById('practice-type').value = mcq.includes(subject) ? 'mcq' : 'essay';
  startPractice();
}

// ── Tabs ──
function showTab(name) {
  document.querySelectorAll('.tab-pane').forEach(el => el.classList.add('hidden'));
  document.querySelectorAll('.tab-btn').forEach(el => el.classList.remove('active'));
  document.getElementById('tab-' + name).classList.remove('hidden');
  document.querySelectorAll('.tab-btn').forEach(btn => {
    if (btn.getAttribute('onclick')?.includes("'" + name + "'")) btn.classList.add('active');
  });
  if (name === 'browse') loadBrowse(1);
}

// ── Practice ──
async function startPractice() {
  const subject = document.getElementById('practice-subject').value;
  const year = document.getElementById('practice-year').value;
  const type = document.getElementById('practice-type').value;
  const count = parseInt(document.getElementById('practice-count').value) || 20;

  const params = new URLSearchParams({ count, type, shuffle: true });
  if (subject) params.set('subject', subject);
  if (year) params.set('year', year);

  try {
    const r = await fetch('/api/practice/session?' + params);
    const data = await r.json();
    if (!data.questions?.length) { alert('無符合條件的題目'); return; }

    practiceQuestions = data.questions;
    practiceIndex = 0; practiceCorrect = 0; practiceWrong = 0;

    document.getElementById('practice-setup').classList.add('hidden');
    document.getElementById('practice-area').classList.remove('hidden');
    document.getElementById('result-banner').classList.add('hidden');
    document.getElementById('question-container').classList.remove('hidden');
    document.getElementById('q-total').textContent = practiceQuestions.length;
    renderQuestion();
  } catch (e) { alert('載入失敗：' + e.message); }
}

function renderQuestion() {
  const q = practiceQuestions[practiceIndex];
  if (!q) { showResult(); return; }

  document.getElementById('q-current').textContent = practiceIndex + 1;
  document.getElementById('q-correct').textContent = practiceCorrect;
  document.getElementById('q-wrong').textContent = practiceWrong;
  document.getElementById('progress-bar').style.width =
    Math.round((practiceIndex / practiceQuestions.length) * 100) + '%';

  const container = document.getElementById('question-container');
  const color = SUBJECT_COLORS[q.subject] || '#6b7280';

  if (q.type === 'essay') {
    container.innerHTML = `
      <div class="bg-white rounded-xl shadow-sm p-6 mb-4">
        <div class="flex gap-2 mb-3">
          <span class="text-xs px-2 py-0.5 rounded-full text-white" style="background:${color}">${q.subject}</span>
          <span class="text-xs text-gray-400">${q.roc_year} 年 · 申論題</span>
        </div>
        <div class="text-sm text-gray-700 leading-relaxed whitespace-pre-wrap mb-5">${q.stem}</div>
        <button onclick="nextQuestion()" class="text-white px-5 py-2 rounded-lg text-sm font-medium" style="background:#1a3a5c">
          ${practiceIndex + 1 < practiceQuestions.length ? '下一題 →' : '完成練習'}
        </button>
      </div>`;
    return;
  }

  const opts = Object.entries(q.options || {});
  container.innerHTML = `
    <div class="bg-white rounded-xl shadow-sm p-6 mb-4" id="q-card">
      <div class="flex gap-2 mb-3">
        <span class="text-xs px-2 py-0.5 rounded-full text-white" style="background:${color}">${q.subject}</span>
        <span class="text-xs text-gray-400">${q.roc_year} 年</span>
      </div>
      <p class="text-sm text-gray-800 leading-relaxed mb-5">${practiceIndex + 1}. ${q.stem}</p>
      <div id="options-container">
        ${opts.map(([k, v]) => `
          <button class="option-btn" onclick="submitAnswer('${q.id}','${k}',this)">
            <span class="font-semibold mr-2">${k}.</span>${v}
          </button>`).join('')}
      </div>
      <div id="answer-feedback" class="hidden mt-4 p-3 rounded-lg text-sm"></div>
    </div>`;
}

async function submitAnswer(qId, answer, btn) {
  document.querySelectorAll('.option-btn').forEach(b => b.disabled = true);
  try {
    const r = await fetch(`/api/practice/check?q_id=${encodeURIComponent(qId)}&answer=${answer}`);
    const result = await r.json();
    const fb = document.getElementById('answer-feedback');
    fb.classList.remove('hidden');

    if (result.is_correct === null) {
      btn.style.background = '#fef9c3'; btn.style.borderColor = '#ca8a04';
      fb.className = 'mt-4 p-3 rounded-lg text-sm bg-yellow-50 text-yellow-800';
      fb.innerHTML = `⚠️ 答案尚未收錄`;
    } else if (result.is_correct) {
      btn.classList.add('correct');
      fb.className = 'mt-4 p-3 rounded-lg text-sm bg-green-50 text-green-800';
      fb.innerHTML = `✅ 正確！`;
      practiceCorrect++;
    } else {
      btn.classList.add('wrong');
      document.querySelectorAll('.option-btn').forEach(b => {
        if (b.textContent.trim().startsWith(result.correct + '.')) b.classList.add('correct');
      });
      fb.className = 'mt-4 p-3 rounded-lg text-sm bg-red-50 text-red-800';
      fb.innerHTML = `❌ 正確答案：<strong>${result.correct}</strong>`;
      practiceWrong++;
    }

    const nextBtn = document.createElement('button');
    nextBtn.textContent = practiceIndex + 1 < practiceQuestions.length ? '下一題 →' : '查看結果';
    nextBtn.className = 'mt-4 text-white px-5 py-2 rounded-lg text-sm font-medium block';
    nextBtn.style.background = '#1a3a5c';
    nextBtn.onclick = nextQuestion;
    document.getElementById('q-card').appendChild(nextBtn);
  } catch (e) { nextQuestion(); }
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
    pct >= 80 ? '表現優異！繼續保持' : pct >= 60 ? '不錯！繼續加油' : mcqTotal > 0 ? '多練幾遍，熟能生巧' : '';
}

function endPractice() {
  document.getElementById('practice-setup').classList.remove('hidden');
  document.getElementById('practice-area').classList.add('hidden');
}

// ── Browse ──
async function loadBrowse(page) {
  if (page !== undefined) browseOffset = (page - 1) * PAGE_SIZE;
  const subject = document.getElementById('browse-subject').value;
  const year = document.getElementById('browse-year').value;
  const type = document.getElementById('browse-type').value;
  const params = new URLSearchParams({ limit: PAGE_SIZE, offset: browseOffset });
  if (subject) params.set('subject', subject);
  if (year) params.set('year', year);
  if (type) params.set('type', type);
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
    if (!data.questions.length) { list.innerHTML = '<div class="text-center text-gray-400 py-12">無符合條件的題目</div>'; return; }
    list.innerHTML = data.questions.map(q => `
      <div class="bg-white rounded-xl shadow-sm border border-gray-100 p-5 mb-3">
        <div class="flex gap-2 mb-2">
          <span class="text-xs px-2 py-0.5 rounded-full text-white" style="background:${SUBJECT_COLORS[q.subject] || '#6b7280'}">${q.subject}</span>
          <span class="text-xs text-gray-400">${q.roc_year} 年 · ${q.type === 'mcq' ? '選擇題' : '申論題'}</span>
        </div>
        <p class="text-sm text-gray-800 leading-relaxed">${q.question_number}. ${q.stem}</p>
        ${q.options && Object.keys(q.options).length ? `
          <div class="mt-3 grid grid-cols-2 gap-1">
            ${Object.entries(q.options).map(([k,v]) => `<div class="text-xs text-gray-600 bg-gray-50 rounded px-2 py-1"><span class="font-semibold">${k}.</span> ${v}</div>`).join('')}
          </div>` : ''}
        ${q.answer ? `<div class="mt-2 text-xs bg-green-50 text-green-700 rounded px-2 py-1">答案：${q.answer}</div>` : ''}
      </div>`).join('');
  } catch (e) {
    document.getElementById('browse-list').innerHTML = '<div class="text-center text-red-400 py-8">載入失敗</div>';
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

function toggleDark() {
  document.documentElement.classList.toggle('dark');
}
