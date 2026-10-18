/* Public FastAPI adapter. Local writes remain isolated in explicit demo mode. */
(function (root) {
  'use strict';
  const local = root.StudyMate;
  const BASE = 'https://swe-project-u3f0.onrender.com';
  const MODE_KEY = 'studymate.source';
  const AUTH_KEY = 'studymate.server.auth';
  const mode = () => sessionStorage.getItem(MODE_KEY) === 'local' ? 'local' : 'server';
  function expired() {
    if (root.dispatchEvent && root.Event) root.dispatchEvent(new root.Event('studymate:auth-expired'));
  }
  function clearAuth(notify = false) { sessionStorage.removeItem(AUTH_KEY); if (notify) expired(); }
  function validUser(user) { return user && typeof user.username === 'string' && user.username.length > 0 && typeof user.name === 'string'; }
  function auth() {
    const raw = sessionStorage.getItem(AUTH_KEY);
    if (!raw) return null;
    try {
      const value = JSON.parse(raw);
      if (!value || typeof value.token !== 'string' || !value.token || !Number.isFinite(value.expires_at) || !validUser(value.user)) throw new Error();
      if (value.expires_at <= Date.now()) { clearAuth(true); return null; }
      return value;
    } catch { clearAuth(); return null; }
  }
  function apiError(message, status) { return Object.assign(new Error(message), { status }); }
  async function request(path, signal, options = {}) {
    const identity = options.authenticated ? auth() : null;
    if (options.authenticated && !identity) throw apiError('로그인이 필요합니다.', 401);
    const timeout = new AbortController();
    const abort = () => timeout.abort();
    const timer = setTimeout(abort, 60000);
    if (signal?.aborted) abort();
    signal?.addEventListener('abort', abort, { once: true });
    try {
      const headers = { Accept: 'application/json' };
      if (options.body) headers['Content-Type'] = 'application/json';
      if (identity) headers.Authorization = 'Bearer ' + identity.token;
      const response = await fetch(BASE + path, { method: options.method || 'GET', signal: timeout.signal, credentials: 'omit', cache: 'no-store', headers, ...(options.body ? { body: JSON.stringify(options.body) } : {}) });
      if (!response.ok) {
        if (response.status === 401) {
          if (identity && auth()?.token === identity.token) clearAuth(true);
          throw apiError(identity ? '로그인이 만료되었거나 인증 정보가 유효하지 않습니다. 다시 로그인해 주세요.' : '아이디 또는 비밀번호가 올바르지 않습니다.', 401);
        }
        const messages = { 404: '모집글을 찾을 수 없습니다. 삭제되었을 수 있습니다.', 422: '검색 조건이 올바르지 않습니다.', 429: '요청이 너무 많습니다. 잠시 후 다시 시도해 주세요.' };
        if (response.status === 422 && options.body) throw apiError('입력 형식이 올바르지 않습니다. 아이디와 비밀번호를 확인해 주세요.', 422);
        throw apiError(messages[response.status] || `서버 요청에 실패했습니다. (HTTP ${response.status})`, response.status);
      }
      try { return await response.json(); }
      catch { throw apiError('서버 응답을 읽을 수 없습니다. 잠시 후 다시 시도해 주세요.'); }
    } catch (error) {
      if (signal?.aborted) throw error;
      if (timeout.signal.aborted) throw apiError('서버 응답 시간이 초과되었습니다. 서버가 시작 중일 수 있으니 다시 시도해 주세요.');
      if (error instanceof TypeError) throw apiError('서버에 연결할 수 없습니다. 인터넷 연결과 서버의 CORS 허용 설정을 확인해 주세요.');
      throw error;
    } finally { clearTimeout(timer); signal?.removeEventListener('abort', abort); }
  }
  function normalize(p) {
    if (!p || !Number.isInteger(p.id) || p.id < 1 || typeof p.title !== 'string') throw apiError('모집글 응답 형식이 올바르지 않습니다.');
    return { ...p, author_name: p.author_name || '작성자 정보 없음', category: p.category || '분야 미지정', status: ['RECRUITING', 'CLOSED'].includes(p.status) ? p.status : 'UNKNOWN', current_size: p.current_size ?? null, created_at: p.created_at ?? null };
  }
  const server = {
    me: () => auth()?.user || null,
    logout() { clearAuth(); },
    async login(username, password) {
      const input = { username: String(username || '').trim(), password: String(password || '') };
      if (!input.username || input.username.length > 20 || /\s/.test(input.username) || !input.password || input.password.length > 128) throw apiError('아이디는 공백 없이 1~20자, 비밀번호는 1~128자로 입력해 주세요.');
      const result = await request('/api/auth/login', undefined, { method: 'POST', body: input });
      if (typeof result.access_token !== 'string' || !result.access_token || result.token_type !== 'bearer' || !Number.isInteger(result.expires_in) || result.expires_in <= 0 || !validUser(result.user)) throw apiError('로그인 응답 형식이 올바르지 않습니다.');
      const identity = { token: result.access_token, expires_at: Date.now() + result.expires_in * 1000, user: { username: result.user.username, name: result.user.name, created_at: result.user.created_at ?? null } };
      sessionStorage.setItem(AUTH_KEY, JSON.stringify(identity));
      try { return await server.refreshMe(); }
      catch (error) { if (auth()?.token === identity.token) clearAuth(); throw error; }
    },
    async refreshMe() {
      const identity = auth();
      if (!identity) return null;
      const user = await request('/api/users/me', undefined, { authenticated: true });
      if (!validUser(user)) throw apiError('사용자 정보 응답 형식이 올바르지 않습니다.');
      if (auth()?.token !== identity.token) return null;
      const safeUser = { username: user.username, name: user.name, created_at: user.created_at ?? null };
      sessionStorage.setItem(AUTH_KEY, JSON.stringify({ ...identity, user: safeUser }));
      return safeUser;
    },
    async postsPage(filters = {}, signal) {
      const query = new URLSearchParams({ page: String(filters.page || 1), page_size: '6' });
      for (const key of ['keyword', 'category', 'status']) {
        const value = String(filters[key] || '').trim();
        if (value) query.set(key, value);
      }
      const body = await request('/api/posts?' + query, signal);
      if (!Array.isArray(body.items) || !Number.isInteger(body.total) || body.total < 0 || !Number.isInteger(body.page) || body.page < 1 || !Number.isInteger(body.page_size) || body.page_size < 1) throw apiError('모집글 목록 응답 형식이 올바르지 않습니다.');
      return { ...body, items: body.items.map(normalize) };
    },
    async getPost(id, signal) {
      if (!/^[1-9]\d*$/.test(String(id))) throw apiError('올바른 모집글 번호가 아닙니다.');
      const p = normalize(await request('/api/posts/' + encodeURIComponent(id), signal));
      if (typeof p.content !== 'string') throw apiError('모집글 상세 응답 형식이 올바르지 않습니다.');
      return p;
    }
  };
  root.StudyMateSource = {
    mode,
    base: BASE,
    setMode(value) { if (!['local', 'server'].includes(value)) throw new Error('잘못된 모드입니다.'); sessionStorage.setItem(MODE_KEY, value); }
  };
  root.StudyMate = new Proxy({}, {
    get(_target, key) {
      if (mode() === 'local') return local[key];
      return server[key] || (async () => { throw new Error('이 기능의 서버 API는 아직 연결되지 않았습니다. 로컬 데모에서 시험할 수 있습니다.'); });
    }
  });
})(globalThis);
