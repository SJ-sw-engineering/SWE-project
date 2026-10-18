(function () {
  'use strict';
  const api = window.StudyMate;
  const main = document.getElementById('app');
  const page = document.body.dataset.page;
  const params = new URLSearchParams(location.search);
  const id = params.get('id');
  const e = value => String(value ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const source = window.StudyMateSource;
  const isServer = () => source.mode() === 'server';
  const postStatus = value => ({ CLOSED: '모집 마감', RECRUITING: '모집 중' }[value] || '상태 정보 없음');
  const appStatus = value => ({ PENDING: '검토 중', APPROVED: '승인됨', REJECTED: '거절됨' }[value] || '알 수 없음');
  const date = value => value && !Number.isNaN(Date.parse(value)) ? new Date(value).toLocaleString('ko-KR', { timeZone: 'Asia/Seoul' }) : '등록일 정보 없음';
  const url = (file, postId) => `${file}?id=${encodeURIComponent(postId)}`;
  const badge = (value, label) => `<span class="badge ${e(value.toLowerCase())}">${e(label)}</span>`;
  const link = (label, file, postId, cls = 'secondary-button') => `<a class="${cls}" href="${e(postId == null ? file : url(file, postId))}">${e(label)}</a>`;
  let busy = false;
  let refreshTimer;
  let clockTimer;
  let refreshing = false;
  let renderEpoch = 0;
  function header() {
    const u = api.me();
    document.getElementById('site-header').innerHTML = `<div class="logo"><a href="index.html">StudyMate</a></div><nav aria-label="주 메뉴"><a href="index.html#recruitment">모집글</a>${u ? `<a href="my-applications.html">내 지원</a><a href="my-teams.html">내 팀</a><span class="nav-user">${e(u.name)} (${e(u.username)})</span><button type="button" class="nav-logout" id="logout">로그아웃</button>` : '<a href="login.html">로그인</a><a href="signup.html" class="signup-button">회원가입</a>'}</nav>`;
    if (isServer()) document.querySelector('nav').innerHTML = `<a href="index.html#recruitment">모집글</a>${u ? `<a href="profile.html">내 정보</a><span class="nav-user">${e(u.name)} (${e(u.username)})</span><button type="button" class="nav-logout" id="logout">로그아웃</button>` : '<a href="login.html">서버 로그인</a>'}`;
    document.getElementById('logout')?.addEventListener('click', () => { api.logout(); location.href = 'index.html'; });
    const banner = document.querySelector('.demo-banner');
    banner.innerHTML = `<span>${isServer() ? '서버 연결 모드 · 로그인·내 정보·모집글 조회를 제공합니다.' : '로컬 데모 · 실제 서버와 별개의 브라우저 데이터입니다.'}</span> <button type="button" id="switch-source">${isServer() ? '로컬 데모로 전환' : '서버 조회로 전환'}</button>`;
    document.getElementById('switch-source').addEventListener('click', () => { source.setMode(isServer() ? 'local' : 'server'); location.href = 'index.html'; });
  }
  function message(value, success = false) {
    const area = document.getElementById('feedback');
    area.textContent = value;
    area.className = `feedback ${success ? 'success' : 'error'}`;
    area.hidden = false;
  }
  function shell(title, description, content, wide = false) {
    main.className = 'form-page';
    main.innerHTML = `<section class="form-container ${wide ? 'wide' : ''}"><h1>${e(title)}</h1><p class="form-description">${e(description)}</p>${content}</section>`;
  }
  function empty(text) { return `<p class="empty-state">${e(text)}</p>`; }
  function input(label, name, type = 'text', value = '', attrs = '') {
    return `<div class="form-group"><label for="${name}">${e(label)}</label><input id="${name}" name="${name}" type="${type}" value="${e(value)}" ${attrs} required></div>`;
  }
  function textarea(label, name, value, max) { return `<div class="form-group"><label for="${name}">${e(label)}</label><textarea id="${name}" name="${name}" maxlength="${max}" required>${e(value)}</textarea></div>`; }
  function fieldValues(form) { return Object.fromEntries(new FormData(form)); }
  function needLogin() {
    if (api.me()) return true;
    const next = location.pathname.split('/').pop() + location.search;
    shell('로그인이 필요합니다', '로그인 후 이 기능을 사용할 수 있습니다.', link('로그인', `login.html?next=${encodeURIComponent(next)}`, null, 'main-button'));
    return false;
  }
  function requireOwner(p) { if (p.author_id !== api.me()?.username) throw new Error('팀장만 접근할 수 있는 페이지입니다.'); }
  async function action(button, work) {
    if (busy) return;
    busy = true;
    if (button) { button.disabled = true; button.setAttribute('aria-busy', 'true'); }
    document.getElementById('feedback').hidden = true;
    try { await work(); } catch (error) { message(error.message); }
    finally { busy = false; if (button?.isConnected) { button.disabled = false; button.removeAttribute('aria-busy'); } }
  }
  function submit(work) {
    document.querySelector('form').addEventListener('submit', event => { event.preventDefault(); action(event.currentTarget.querySelector('[type="submit"]'), () => work(fieldValues(event.target))); });
  }
  function bindClick(selector, work) { document.querySelector(selector)?.addEventListener('click', event => action(event.currentTarget, work)); }
  function postCard(p, extra = '') {
    return `<article class="recruitment-card"><div class="card-top"><span class="category">${e(p.category)}</span>${badge(p.status, postStatus(p.status))}</div><h2 class="card-title"><a href="${e(url('recruit-detail.html', p.id))}">${e(p.title)}</a></h2>${p.content == null ? '' : `<p class="card-summary">${e(p.content)}</p>`}<div class="card-info"><span>현재 ${e(p.current_size ?? '정보 없음')} / 정원 ${e(p.target_size)}명</span><span>팀장 ${e(p.author_name)}</span></div>${extra}</article>`;
  }
  function timer(expiry, expired) {
    clearInterval(clockTimer);
    const update = () => {
      const target = document.getElementById('remaining-time');
      if (!target) return;
      const seconds = Math.max(0, Math.ceil((Date.parse(expiry) - Date.now()) / 1000));
      target.textContent = seconds ? `남은 시간 ${Math.floor(seconds / 60)}분 ${String(seconds % 60).padStart(2, '0')}초` : '출석 시간이 만료되었습니다.';
      if (!seconds) { clearInterval(clockTimer); if (expired) expired(); }
    };
    if (Date.parse(expiry) <= Date.now()) { update(); return; }
    update(); clockTimer = setInterval(update, 1000);
  }
  function polling(work) {
    clearInterval(refreshTimer);
    refreshTimer = setInterval(async () => {
      if (busy || refreshing || document.hidden) return;
      refreshing = true;
      try { await work(); } catch (error) { message(error.message); }
      finally { refreshing = false; }
    }, 3000);
  }
  async function home() {
    if (isServer()) return serverHome();
    main.className = '';
    main.innerHTML = `<section class="hero"><div class="hero-content"><p class="hero-small">UNIVERSITY STUDY & PROJECT</p><h1>함께 공부하고<br>함께 프로젝트를 시작하세요.</h1><p class="hero-description">원하는 팀을 찾고, 지원부터 모임 출석까지 한곳에서 관리하세요.</p><a class="main-button" href="#recruitment">모집글 둘러보기</a></div></section><section class="recruitment-section" id="recruitment"><div class="section-title"><div><p class="section-small">RECRUITMENT</p><h2>스터디·프로젝트 모집</h2></div>${link('모집글 작성', 'recruit-write.html', null, 'write-button')}</div><form class="filter-bar" role="search"><label class="search-field">검색<input name="keyword" type="search" placeholder="제목·내용·분야 검색"></label><label>모집 상태<select name="status"><option value="">전체</option value="RECRUITING">모집 중</option><option value="CLOSED">모집 마감</option></select></label><button class="main-button" type="submit">검색</button></form><div class="recruitment-list" id="post-list"></div></section>`;
    const posts = await api.posts();
    function show(filters = {}) {
      const q = String(filters.keyword || '').trim().toLowerCase();
      const list = posts.filter(p => (!filters.status || p.status === filters.status) && `${p.title} ${p.content} ${p.category}`.toLowerCase().includes(q));
      document.getElementById('post-list').innerHTML = list.length ? list.map(p => postCard(p)).join('') : empty(posts.length ? '검색 결과가 없습니다.' : '아직 모집글이 없습니다. 첫 팀을 모집해 보세요.');
    }
    show();
    document.querySelector('form').addEventListener('submit', event => { event.preventDefault(); show(fieldValues(event.target)); });
  }
  async function serverHome() {
    main.className = '';
    main.innerHTML = `<section class="hero"><div class="hero-content"><p class="hero-small">UNIVERSITY STUDY & PROJECT</p><h1>함께 공부하고<br>함께 프로젝트를 시작하세요.</h1><p class="hero-description">실제 서버에 등록된 스터디와 프로젝트를 찾아보세요.</p><a class="main-button" href="#recruitment">모집글 둘러보기</a></div></section><section class="recruitment-section" id="recruitment"><div class="section-title"><div><p class="section-small">RECRUITMENT</p><h2>스터디·프로젝트 모집</h2></div></div><form class="filter-bar server-filters" role="search"><label class="search-field">검색<input name="keyword" type="search" maxlength="100" placeholder="키워드 입력"></label><label>모집 분야<input name="category" type="text" maxlength="100" placeholder="예: Web/Frontend"></label><label>모집 상태<select name="status"><option value="">전체</option><option value="RECRUITING">모집 중</option><option value="CLOSED">모집 마감</option></select></label><button class="main-button" type="submit">검색</button><button class="secondary-button" type="button" id="reset-search">초기화</button></form><p class="field-help">분야는 정확히 일치하는 값으로 검색합니다. 모집 상태는 서버 값을 표시합니다.</p><p id="list-summary" role="status" aria-live="polite"></p><div class="recruitment-list" id="post-list"></div><div class="pagination" id="pagination"></div></section>`;
    let filters = { keyword: params.get('keyword') || '', category: params.get('category') || '', status: ['RECRUITING', 'CLOSED'].includes(params.get('status')) ? params.get('status') : '' };
    let currentPage = /^[1-9]\d*$/.test(params.get('page') || '') ? Number(params.get('page')) : 1;
    let sequence = 0;
    let controller;
    const form = document.querySelector('form');
    for (const key of ['keyword', 'category', 'status']) form.elements[key].value = filters[key];
    async function load(nextPage) {
      const requestId = ++sequence;
      controller?.abort(); controller = new AbortController();
      currentPage = nextPage;
      const list = document.getElementById('post-list');
      list.setAttribute('aria-busy', 'true');
      list.innerHTML = empty('모집글을 불러오는 중입니다. 서버 시작에 시간이 걸릴 수 있습니다.');
      document.getElementById('pagination').innerHTML = '';
      document.getElementById('list-summary').textContent = '';
      document.getElementById('feedback').hidden = true;
      const query = new URLSearchParams();
      for (const [key, value] of Object.entries(filters)) if (value.trim()) query.set(key, value.trim());
      if (nextPage > 1) query.set('page', nextPage);
      window.history.replaceState(null, '', 'index.html' + (query.size ? '?' + query : '') + location.hash);
      try {
        const result = await api.postsPage({ ...filters, page: nextPage }, controller.signal);
        if (requestId !== sequence) return;
        const totalPages = Math.max(1, Math.ceil(result.total / result.page_size));
        document.getElementById('list-summary').textContent = `총 ${result.total}개 · ${result.page}페이지`;
        list.innerHTML = result.items.length ? result.items.map(p => postCard(p)).join('') : empty('검색 결과가 없습니다. 검색 조건을 바꾸거나 초기화해 주세요.');
        document.getElementById('pagination').innerHTML = `<button class="secondary-button" id="previous-page" ${result.page <= 1 ? 'disabled' : ''}>이전</button><span>${result.page} / ${totalPages}</span><button class="secondary-button" id="next-page" ${result.page >= totalPages ? 'disabled' : ''}>다음</button>`;
        document.getElementById('previous-page').addEventListener('click', () => load(Math.max(1, currentPage - 1)));
        document.getElementById('next-page').addEventListener('click', () => load(currentPage + 1));
      } catch (error) {
        if (requestId !== sequence) return;
        list.innerHTML = `${empty(error.message)}<button class="secondary-button" id="retry-posts">다시 시도</button>`;
        document.getElementById('retry-posts').addEventListener('click', () => load(currentPage));
      } finally { if (requestId === sequence) list.setAttribute('aria-busy', 'false'); }
    }
    form.addEventListener('submit', event => { event.preventDefault(); filters = fieldValues(form); load(1); });
    document.getElementById('reset-search').addEventListener('click', () => { form.reset(); filters = { keyword: '', category: '', status: '' }; load(1); });
    await load(currentPage);
  }
  async function serverDetail() {
    shell('모집글 상세', '서버에서 모집글을 불러오는 중입니다.', '<p class="empty-state" role="status">잠시 기다려 주세요.</p>', true);
    try {
      const p = await api.getPost(id);
      shell(p.title, `팀장 ${p.author_name} · ${date(p.created_at)}`, `<div class="detail-top"><span class="category">${e(p.category)}</span>${badge(p.status, postStatus(p.status))}</div><p class="pre-wrap">${e(p.content)}</p><div class="recruit-info"><div class="info-item"><span>팀 정원</span><strong>팀장 포함 ${e(p.target_size)}명</strong></div><div class="info-item"><span>현재 인원</span><strong>${e(p.current_size ?? '정보 없음')}${p.current_size == null ? '' : '명'}</strong></div></div><p class="identity-card">지원과 모집글 관리 기능은 백엔드 API가 준비되면 연결됩니다.</p><p class="form-link">${link('목록으로', 'index.html')}</p>`, true);
    } catch (error) {
      shell('모집글을 불러올 수 없습니다', error.message, '<button class="secondary-button" id="retry-detail">다시 시도</button> ' + link('목록으로', 'index.html'), true);
      bindClick('#retry-detail', serverDetail);
    }
  }
  async function signup() {
    shell('회원가입', '아이디 또는 학번으로 StudyMate 계정을 만드세요.', `<form>${input('아이디 / 학번', 'username', 'text', '', 'autocomplete="username" minlength="4" maxlength="20" pattern="[A-Za-z0-9_\\-]{4,20}" aria-describedby="username-help"')}<p class="field-help" id="username-help">영문·숫자·밑줄·하이픈 4~20자</p>${input('이름', 'name', 'text', '', 'autocomplete="name" maxlength="50"')}${input('비밀번호', 'password', 'password', '', 'autocomplete="new-password" minlength="8" maxlength="128"')}${input('비밀번호 확인', 'password_check', 'password', '', 'autocomplete="new-password" minlength="8" maxlength="128"')}<button class="form-button" type="submit">회원가입</button></form><p class="form-link"><a href="login.html">이미 계정이 있나요? 로그인</a></p>`);
    submit(async values => { if (values.password !== values.password_check) throw new Error('비밀번호가 일치하지 않습니다.'); await api.signup(values); location.href = 'login.html?registered=1'; });
  }
  async function login() {
    if (isServer() && api.me()) { await profile(); return; }
    shell(isServer() ? '서버 로그인' : '로컬 데모 로그인', isServer() ? '백엔드에 등록된 계정으로 로그인하세요. 로컬 데모 계정은 사용할 수 없습니다.' : '이 브라우저에서 가입한 데모 계정으로 로그인하세요.', `<form>${input('아이디 / 학번', 'username', 'text', '', 'autocomplete="username" maxlength="20"')}${input('비밀번호', 'password', 'password', '', 'autocomplete="current-password" maxlength="128"')}<button class="form-button" type="submit">로그인</button></form>${isServer() ? '<p class="field-help auth-help">서버 회원가입은 아직 제공되지 않습니다. 테스트 계정은 백엔드 담당자에게 확인하세요.</p>' : '<p class="form-link"><a href="signup.html">새 계정 만들기</a></p>'}`);
    if (params.has('registered')) message('회원가입이 완료되었습니다. 로그인해 주세요.', true);
    submit(async values => {
      await api.login(values.username, values.password);
      const next = params.get('next');
      // Restrict return targets to this application's known HTML pages.
      const allowed = isServer() ? /^(index|profile|recruit-detail)\.html(?:\?id=\d+)?$/ : /^(index|recruit-write|recruit-detail|apply|applicants|attendance|attendance-check|attendance-history|my-applications|my-teams|lcd-simulator)\.html(?:\?id=\d+)?$/;
      location.href = next && allowed.test(next) ? next : 'index.html';
    });
  }
  async function profile() {
    if (!needLogin()) return;
    const u = api.me();
    shell('내 정보', isServer() ? '서버에서 확인한 계정 정보입니다.' : '로컬 데모 계정 정보입니다.', `<dl class="profile-fields"><dt>아이디 / 학번</dt><dd>${e(u.username)}</dd><dt>이름</dt><dd>${e(u.name)}</dd>${isServer() ? `<dt>가입일 (한국 시간)</dt><dd>${e(date(u.created_at))}</dd>` : ''}</dl>${isServer() ? '<p class="field-help auth-help">로그인은 서버가 정한 유효시간 동안 이 탭에서 유지됩니다. 만료되면 다시 로그인해 주세요.</p><button class="secondary-button" id="refresh-profile">정보 새로고침</button>' : ''}<p class="form-link">${link('모집글 보기', 'index.html')}</p>`);
    bindClick('#refresh-profile', async () => { await api.refreshMe(); header(); await profile(); message('사용자 정보를 확인했습니다.', true); });
  }
  async function writePost() {
    if (!needLogin()) return;
    const p = id == null ? null : await api.getPost(id);
    if (p) requireOwner(p);
    shell(p ? '모집글 수정' : '모집글 작성', '팀 정원에는 팀장 1명이 포함됩니다.', `<form>${input('모집 분야', 'category', 'text', p?.category || '', 'maxlength="100" list="categories" placeholder="예: Web/Frontend"')}<datalist id="categories"><option value="Web/Frontend"><option value="Data/AI"><option value="App/Backend"><option value="Study/Algorithm"><option value="Game/Unity"></datalist>${input('모집글 제목', 'title', 'text', p?.title || '', 'maxlength="255"')}${input('팀 정원 (팀장 포함)', 'target_size', 'number', p?.target_size || 4, 'min="2" max="100" step="1"')}${textarea('모집 내용', 'content', p?.content || '', 10000)}<button class="form-button" type="submit">${p ? '수정 완료' : '모집글 등록'}</button></form><p class="form-link">${link('취소', p ? 'recruit-detail.html' : 'index.html', p?.id)}</p>`);
    submit(async values => { const postId = await api.savePost(values, p?.id); location.href = url('recruit-detail.html', postId); });
  }
  async function detail() {
    if (isServer()) return serverDetail();
    const p = await api.getPost(id); const u = api.me(); const leader = u?.username === p.author_id;
    let controls;
    if (leader) controls = `<div class="action-row">${link('수정', 'recruit-write.html', p.id)}${link('지원자 관리', 'applicants.html', p.id)}${link('출석 관리', 'attendance.html', p.id)}<button class="delete-button" id="delete-post">삭제</button>${p.status === 'RECRUITING' ? '<button class="secondary-button" id="close-post">모집 마감</button>' : ''}</div>`;
    else if (p.my_application) controls = `<p>내 지원 상태: ${badge(p.my_application.status, appStatus(p.my_application.status))}</p>${link('내 지원 현황', 'my-applications.html')}${p.my_application.status === 'APPROVED' ? link('출석 인증', 'attendance-check.html', p.id) : ''}`;
    else controls = p.status === 'RECRUITING' ? link('지원하기', 'apply.html', p.id, 'main-button') : '<button class="main-button" disabled>모집 마감</button>';
    shell(p.title, `팀장 ${p.author_name} (${p.author_id}) · ${date(p.created_at)}`, `<div class="detail-top"><span class="category">${e(p.category)}</span>${badge(p.status, postStatus(p.status))}</div><p class="pre-wrap">${e(p.content)}</p><div class="recruit-info"><div class="info-item"><span>팀 정원</span><strong>팀장 포함 ${p.target_size}명</strong></div><div class="info-item"><span>현재 인원</span><strong>${p.current_size}명</strong></div><div class="info-item"><span>전체 지원자</span><strong>${p.applicant_count}명</strong></div></div><div class="detail-actions">${controls}</div><p class="form-link">${link('목록으로', 'index.html')}</p>`, true);
    bindClick('#delete-post', async () => { if (!confirm('모집글과 관련 지원·출석 기록을 삭제하시겠습니까?')) return; await api.deletePost(p.id); location.href = 'index.html'; });
    bindClick('#close-post', async () => { if (!confirm('모집을 마감하시겠습니까? 출석 기능은 계속 사용할 수 있습니다.')) return; await api.closePost(p.id); await detail(); message('모집이 마감되었습니다.', true); });
  }
  async function apply() {
    if (!needLogin()) return;
    const p = await api.getPost(id); const u = api.me();
    if (p.author_id === u.username) throw new Error('자신의 모집글에는 지원할 수 없습니다.');
    if (p.my_application) { shell('이미 지원한 모집글입니다', appStatus(p.my_application.status), link('내 지원 현황', 'my-applications.html')); return; }
    if (p.status !== 'RECRUITING') throw new Error('모집이 마감되었습니다.');
    shell('모집글 지원', p.title, `<div class="identity-card"><strong>${e(u.name)}</strong><p>아이디: ${e(u.username)}</p></div><form>${textarea('자기소개와 지원 동기', 'message', '', 5000)}<button class="form-button" type="submit">지원하기</button></form><p class="form-link">${link('모집글로 돌아가기', 'recruit-detail.html', p.id)}</p>`);
    submit(async values => { await api.apply(p.id, values.message); location.href = 'my-applications.html'; });
  }
  async function applicants() {
    if (!needLogin()) return;
    const p = await api.getPost(id); requireOwner(p); const list = await api.applicants(p.id);
    shell('지원자 관리', p.title, `<div class="identity-card">현재 ${p.current_size} / 정원 ${p.target_size}명 (팀장 포함) ${badge(p.status, postStatus(p.status))}</div><p class="field-help">승인·거절한 지원서는 다시 변경할 수 없습니다. 정원 도달 시 자동으로 마감됩니다.</p><div class="applicant-list">${list.length ? list.map(a => `<article class="applicant-card"><div class="applicant-info"><h2>${e(a.name)} (${e(a.applicant_id)})</h2><p class="pre-wrap">${e(a.message)}</p><p>${e(date(a.applied_at))}</p>${badge(a.status, appStatus(a.status))}</div>${a.status === 'PENDING' ? `<div class="applicant-buttons"><button class="approve-button" data-application="${a.id}" data-status="APPROVED" ${p.current_size >= p.target_size ? 'disabled' : ''}>승인</button><button class="reject-button" data-application="${a.id}" data-status="REJECTED">거절</button></div>` : ''}</article>`).join('') : empty('아직 지원자가 없습니다.')}</div><p class="form-link">${link('모집글로 돌아가기', 'recruit-detail.html', p.id)}</p>`, true);
    document.querySelectorAll('[data-application]').forEach(button => button.addEventListener('click', () => action(button, async () => { await api.decide(button.dataset.application, button.dataset.status); await applicants(); message('지원서를 처리했습니다.', true); })));
  }
  async function myApplications() {
    if (!needLogin()) return;
    const list = await api.myApplications();
    shell('내 지원 현황', '내가 지원한 모집글과 처리 결과를 확인하세요.', `<div class="stack-list">${list.length ? list.map(a => `<article class="recruitment-card"><h2>${e(a.post.title)}</h2><p>${e(a.post.category)} · ${e(date(a.applied_at))}</p>${badge(a.status, appStatus(a.status))}<p class="pre-wrap">${e(a.message)}</p><div class="action-row">${link('모집글 보기', 'recruit-detail.html', a.post_id)}${a.status === 'APPROVED' ? link('출석 인증', 'attendance-check.html', a.post_id) : ''}</div></article>`).join('') : empty('아직 지원한 모집글이 없습니다.')}</div><p class="form-link">${link('모집글 찾기', 'index.html')}</p>`, true);
  }
  async function teams() {
    if (!needLogin()) return;
    const list = await api.myTeams();
    shell('내 팀', '모집이 마감된 팀에서도 출석과 이력을 관리할 수 있습니다.', `<div class="stack-list">${list.length ? list.map(p => postCard(p, `<p class="team-role">${p.role === 'LEADER' ? '내가 만든 팀 · 팀장' : '승인된 팀 · 팀원'}</p><div class="action-row">${p.role === 'LEADER' ? link('지원자 관리', 'applicants.html', p.id) + link('출석 관리', 'attendance.html', p.id) : link('출석 인증', 'attendance-check.html', p.id)}${link('출석 이력', 'attendance-history.html', p.id)}</div>`)).join('') : empty('참여 중인 팀이 없습니다. 팀을 만들거나 모집글에 지원해 보세요.')}</div>`, true);
  }
  async function attendance() {
    if (!needLogin()) return;
    const p = await api.getPost(id); requireOwner(p);
    const devices = await api.devices(p.id);
    shell('출석 관리', p.title, `<div class="attendance-card"><p class="attendance-label">현재 출석 상태</p><div id="session-area"></div><div id="start-area">${devices.length ? `<label for="device">연결된 장치</label><select id="device">${devices.map(d => `<option value="${d.id}">LCD 시뮬레이터 #${d.id}</option>`).join('')}</select><button class="main-button" id="start">출석 시작 (5분)</button>` : '<p>테스트용 장치를 먼저 연결해 주세요.</p><button class="secondary-button" id="add-device">LCD 시뮬레이터 연결</button>'}</div><div class="action-row">${link('LCD 시뮬레이터 열기', 'lcd-simulator.html', p.id)}${link('출석 이력', 'attendance-history.html', p.id)}</div></div><section class="attendance-roster"><h2>팀원 출석 현황</h2><div id="roster-list" class="roster-list"></div></section><p class="form-link">${link('내 팀으로', 'my-teams.html')}</p>`, true);
    bindClick('#add-device', async () => { await api.addSimulator(p.id); await attendance(); message('테스트용 LCD 장치를 연결했습니다.', true); });
    bindClick('#start', async () => { await api.startAttendance(p.id, document.getElementById('device').value); await update(); message('출석을 시작했습니다. LCD 시뮬레이터에서 표시를 확인하세요.', true); });
    let previousSignature = '';
    async function update() {
      const sessions = await api.sessions(p.id); const latest = sessions[0];
      const active = latest?.status === 'OPEN' ? latest : null;
      const signature = JSON.stringify([latest?.id, latest?.status, latest?.display_ack]);
      if (signature !== previousSignature || !document.getElementById('session-area').textContent) {
        previousSignature = signature;
        document.getElementById('start-area').hidden = !!active;
        document.getElementById('session-area').innerHTML = active ? `<p class="attendance-status active">출석 진행 중 · 회차 #${active.id}</p><p>${active.display_ack ? 'LCD 표시 확인됨' : 'LCD 표시 대기 중'}</p><p id="remaining-time" class="remaining-time"></p><button class="secondary-button" id="close-session">출석 종료</button>` : `<p class="attendance-status">${latest ? '출석 종료' : '출석 대기'}</p>`;
        if (active) { timer(active.expiry_time); bindClick('#close-session', async () => { await api.closeAttendance(active.id); await update(); message('출석을 종료했습니다.', true); }); }
        else clearInterval(clockTimer);
      }
      if (latest) await showRoster(latest.id, latest.status);
      else document.getElementById('roster-list').innerHTML = empty('출석을 시작하면 팀원별 현황이 표시됩니다.');
    }
    await update(); polling(update);
  }
  async function showRoster(sessionId, status) {
    const members = await api.roster(sessionId);
    document.getElementById('roster-list').innerHTML = members.length ? members.map(m => `<div class="roster-item"><div><strong>${e(m.name)} (${e(m.member_id)})</strong>${m.record ? `<p>${e(date(m.record.checked_in_at))}</p>` : ''}</div>${badge(m.record ? 'PRESENT' : 'ABSENT', m.record ? '출석' : status === 'OPEN' ? '미인증' : '결석')}</div>`).join('') : empty('승인된 팀원이 없습니다.');
  }
  async function check() {
    if (!needLogin()) return;
    const p = await api.getPost(id);
    if (p.author_id === api.me().username) { shell('팀장 출석 관리', '팀원의 출석 현황은 관리 화면에서 확인하세요.', link('출석 관리', 'attendance.html', p.id)); return; }
    shell('출석 인증', p.title, `<div id="check-session"></div><form id="check-form" hidden>${input('LCD에 표시된 숫자 6자리', 'code', 'text', '', 'inputmode="numeric" autocomplete="off" pattern="[0-9]{6}" minlength="6" maxlength="6" placeholder="예: 047281"')}<button type="submit" class="form-button">출석 인증</button></form><div class="action-row">${link('출석 이력', 'attendance-history.html', p.id)}${link('내 팀으로', 'my-teams.html')}</div>`);
    let current = null; let previous = '';
    async function update() {
      const sessions = await api.sessions(p.id);
      current = sessions.find(s => s.status === 'OPEN') || null;
      const signature = JSON.stringify([current?.id, current?.my_record?.id]);
      const target = document.getElementById('check-session');
      if (signature === previous && target.textContent) return;
      previous = signature;
      document.getElementById('check-form').hidden = !current || !!current.my_record;
      if (!current) { target.innerHTML = empty('현재 진행 중인 출석이 없습니다. 팀장이 출석을 시작하면 표시됩니다.'); clearInterval(clockTimer); }
      else if (current.my_record) { target.innerHTML = `<div class="identity-card">${badge('PRESENT', '출석 완료')}<p>${e(date(current.my_record.checked_in_at))}</p></div>`; clearInterval(clockTimer); }
      else { target.innerHTML = `<div class="identity-card"><p>회차 #${current.id} · 모임 장소의 LCD 코드를 입력하세요.</p><p id="remaining-time"></p></div>`; timer(current.expiry_time); }
    }
    submit(async values => { if (!current) throw new Error('현재 진행 중인 출석이 없습니다.'); await api.checkIn(current.id, values.code); await update(); document.getElementById('code').value = ''; message('출석 인증이 완료되었습니다.', true); });
    await update(); polling(update);
  }
  async function history() {
    if (!needLogin()) return;
    const p = await api.getPost(id); const leader = p.author_id === api.me().username;
    const sessions = await api.sessions(p.id);
    shell('출석 이력', `${p.title} · ${leader ? '팀 회차별 출석 현황' : '내 출석 기록'}`, `<div class="stack-list">${sessions.length ? sessions.map(s => `<article class="recruitment-card"><h2>출석 회차 #${s.id}</h2><p>${e(date(s.start_time))}</p>${badge(s.status, s.status === 'OPEN' ? '진행 중' : '종료')}${leader ? `<button class="secondary-button" data-session="${s.id}" data-state="${s.status}">팀원 명단 보기</button>` : `<p>${badge(s.my_record ? 'PRESENT' : 'ABSENT', s.my_record ? '출석' : s.status === 'OPEN' ? '미인증' : '결석')}${s.my_record ? ` · ${e(date(s.my_record.checked_in_at))}` : ''}</p>`}</article>`).join('') : empty('아직 출석 기록이 없습니다.')}</div>${leader ? '<section id="history-roster" hidden><h2 id="roster-title"></h2><div id="roster-list" class="roster-list"></div></section>' : ''}<p class="form-link">${link('내 팀으로', 'my-teams.html')}</p>`, true);
    document.querySelectorAll('[data-session]').forEach(button => button.addEventListener('click', () => action(button, async () => { await showRoster(button.dataset.session, button.dataset.state); document.getElementById('roster-title').textContent = `회차 #${button.dataset.session} 출석 명단`; document.getElementById('history-roster').hidden = false; })));
  }
  async function simulator() {
    if (!needLogin()) return;
    const p = await api.getPost(id); requireOwner(p);
    shell('LCD 시뮬레이터', '실제 ESP32가 연결되기 전 출석 흐름을 확인하는 테스트 화면입니다.', `<div class="lcd-display"><span>STUDYMATE LCD</span><strong id="lcd-code">IDLE</strong><p id="remaining-time"></p></div><p class="field-help">표시 확인 버튼은 장치의 ACK 응답을 모의합니다. 팀원 인증 화면에는 코드가 제공되지 않습니다.</p><button class="main-button" id="ack" disabled>LCD 표시 확인</button><p class="form-link">${link('출석 관리로', 'attendance.html', p.id)}</p>`);
    let current; let signature = '';
    async function update() {
      current = await api.simulator(p.id);
      const nextSignature = String(current?.id || '');
      if (nextSignature === signature && document.getElementById('lcd-code').textContent !== 'IDLE') return;
      signature = nextSignature;
      document.getElementById('lcd-code').textContent = current?.code || 'IDLE';
      document.getElementById('ack').disabled = !current;
      if (current) timer(current.expiry_time, () => { document.getElementById('lcd-code').textContent = 'IDLE'; document.getElementById('ack').disabled = true; current = null; });
      else { clearInterval(clockTimer); document.getElementById('remaining-time').textContent = '진행 중인 출석이 없습니다.'; }
    }
    bindClick('#ack', async () => { await update(); if (!current) throw new Error('진행 중인 출석이 없습니다.'); await api.acknowledge(current.id); message('LCD 표시 확인을 전달했습니다.', true); });
    await update(); polling(update);
  }
  const routes = { index: home, signup, login, profile, 'recruit-write': writePost, 'recruit-detail': detail, apply, applicants, attendance, 'my-applications': myApplications, 'my-teams': teams, 'attendance-check': check, 'attendance-history': history, 'lcd-simulator': simulator };
  async function boot() {
    const epoch = ++renderEpoch;
    clearInterval(refreshTimer); clearInterval(clockTimer);
    try {
      let authError;
      if (isServer()) {
        try { await api.refreshMe(); } catch (error) { authError = error.message; }
      }
      header();
      if (isServer() && !['index', 'recruit-detail', 'login', 'profile'].includes(page)) {
        shell('서버 연동 준비 중', '현재 서버 모드는 로그인·내 정보·모집글 조회와 검색을 제공합니다. 나머지 기능은 로컬 데모로 전환해 시험할 수 있습니다.', link('모집글 보기', 'index.html'));
        return;
      }
      const route = routes[page];
      if (!route) throw new Error('페이지를 찾을 수 없습니다.');
      await route();
      if (authError) message(authError);
    } catch (error) {
      if (epoch !== renderEpoch) return;
      shell('페이지를 열 수 없습니다', error.message, link('홈으로 돌아가기', 'index.html'));
      message(error.message);
    }
  }
  window.addEventListener('storage', event => { if (!isServer() && event.key === 'studymate.db.v2' && !document.querySelector('form') && !busy && !refreshing) boot(); });
  window.addEventListener('pagehide', () => { clearInterval(refreshTimer); clearInterval(clockTimer); });
  window.addEventListener('studymate:auth-expired', () => {
    if (!isServer()) return;
    header();
    if (page === 'profile' || document.querySelector('.profile-fields')) needLogin();
    message('로그인이 만료되었습니다. 다시 로그인해 주세요.');
  });
  // Only check the local deadline here; protected requests also enforce server 401.
  setInterval(() => { if (isServer()) api.me(); }, 1000);
  boot();
})();
