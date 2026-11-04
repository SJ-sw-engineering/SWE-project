/* Public FastAPI adapter. Local writes remain isolated in explicit demo mode. */
(function (root) {
  'use strict';
  const local = root.StudyMate;
  const BASE = 'https://swe-project-u3f0.onrender.com';
  const MODE_KEY = 'studymate.source';
  const AUTH_KEY = 'studymate.server.auth';
  let renewal = null;
  let capabilityRequest;
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
      if (value.expires_at <= Date.now() && (!value.refresh_token || value.refresh_expires_at <= Date.now())) { clearAuth(true); return null; }
      return value;
    } catch { clearAuth(); return null; }
  }
  function apiError(message, status) { return Object.assign(new Error(message), { status }); }
  function storeLogin(result) {
    if (!result || typeof result.access_token !== 'string' || !result.access_token || result.token_type !== 'bearer' || !Number.isInteger(result.expires_in) || result.expires_in <= 0 || !validUser(result.user)) throw apiError('로그인 응답 형식이 올바르지 않습니다.');
    const identity = { token: result.access_token, expires_at: Date.now() + result.expires_in * 1000, user: { username: result.user.username, name: result.user.name, created_at: result.user.created_at ?? null } };
    if (typeof result.refresh_token === 'string' && Number.isInteger(result.refresh_expires_in) && result.refresh_expires_in > 0) Object.assign(identity, { refresh_token: result.refresh_token, refresh_expires_at: Date.now() + result.refresh_expires_in * 1000 });
    sessionStorage.setItem(AUTH_KEY, JSON.stringify(identity));
    return identity;
  }
  async function renew() {
    if (renewal) return renewal;
    const previous = auth();
    if (!previous?.refresh_token) { clearAuth(true); throw apiError('로그인이 만료되었습니다. 다시 로그인해 주세요.', 401); }
    renewal = (async () => {
      try {
        const result = await request('/api/auth/refresh', undefined, { method: 'POST', body: { refresh_token: previous.refresh_token } });
        if (auth()?.token !== previous.token) throw apiError('로그인 상태가 변경되었습니다. 다시 로그인해 주세요.');
        if (typeof result.refresh_token !== 'string' || !result.refresh_token || !Number.isInteger(result.refresh_expires_in) || result.refresh_expires_in <= 0) throw apiError('갱신 응답을 확인할 수 없습니다. 다시 로그인해 주세요.');
        return storeLogin(result);
      } catch (error) { if (auth()?.token === previous.token) clearAuth(true); throw error; }
      finally { renewal = null; }
    })();
    return renewal;
  }
  async function request(path, signal, options = {}) {
    let identity = options.authenticated ? auth() : null;
    if (options.authenticated && !identity) throw apiError('로그인이 필요합니다.', 401);
    if (identity && identity.expires_at <= Date.now() && !options.retried) identity = await renew();
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
          if (identity && !options.retried && identity.refresh_token) {
            // A concurrent request may already have rotated this access token.
            if (auth()?.token === identity.token) await renew();
            return request(path, signal, { ...options, retried: true });
          }
          if (identity && auth()?.token === identity.token) clearAuth(true);
          throw apiError(identity ? '로그인이 만료되었거나 인증 정보가 유효하지 않습니다. 다시 로그인해 주세요.' : '아이디 또는 비밀번호가 올바르지 않습니다.', 401);
        }
        const messages = { 400: '입력한 코드가 올바르지 않습니다.', 403: '이 작업을 수행할 권한이 없습니다.', 404: '요청한 항목을 찾을 수 없습니다.', 409: '이미 처리되었거나 현재 상태에서 진행할 수 없습니다.', 422: '입력 형식이나 검색 조건을 확인해 주세요.', 429: '요청이 너무 많습니다. 1분 후 다시 시도해 주세요.' };
        if ([400, 403, 404, 409, 422, 429].includes(response.status)) {
          let body; try { body = await response.json(); } catch {}
          const detail = typeof body?.detail === 'string' ? body.detail.slice(0, 500) : '';
          throw apiError(detail || messages[response.status], response.status);
        }
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
    async logout() {
      if (renewal) { try { await renewal; } catch {} }
      const identity = auth();
      if (!identity) { clearAuth(); return; }
      try {
        await request('/api/auth/logout', undefined, identity.refresh_token ? { method: 'POST', body: { refresh_token: identity.refresh_token } } : { method: 'POST', authenticated: true, retried: true });
      } catch (error) { if (error.status !== 401) throw error; }
      if (auth()?.token === identity.token) clearAuth();
    },
    async signup(input) { return request('/api/auth/signup', undefined, { method: 'POST', body: { username: String(input.username).trim(), name: String(input.name).trim(), password: input.password } }); },
    async capabilities() {
      if (!capabilityRequest) capabilityRequest = request('/openapi.json').then(spec => ({ applications: !!spec.paths?.['/api/users/me/teams'], attendance: !!spec.paths?.['/api/attendance-sessions/{session_id}/check-in'], version: spec.info?.version || '알 수 없음' })).catch(error => { capabilityRequest = null; throw error; });
      return capabilityRequest;
    },
    async savePost(input, id) {
      const body = { title: input.title.trim(), content: input.content.trim(), category: input.category.trim(), target_size: Number(input.target_size) };
      if (!Number.isInteger(body.target_size) || body.target_size < 2 || body.target_size > 100) throw apiError('팀 정원은 팀장 포함 2~100명입니다.');
      const result = await request(id == null ? '/api/posts' : '/api/posts/' + Number(id), undefined, { method: id == null ? 'POST' : 'PATCH', body, authenticated: true });
      return normalize(result).id;
    },
    async deletePost(id) { return request('/api/posts/' + Number(id), undefined, { method: 'DELETE', authenticated: true }); },
    async closePost(id) { return request('/api/posts/' + Number(id) + '/close', undefined, { method: 'POST', authenticated: true }); },
    async apply(id, message) { return request('/api/posts/' + Number(id) + '/applications', undefined, { method: 'POST', body: { message: message.trim() }, authenticated: true }); },
    async applicants(id) { return array(await request('/api/posts/' + Number(id) + '/applications', undefined, { authenticated: true })); },
    async decide(id, status) { return request('/api/applications/' + Number(id), undefined, { method: 'PATCH', body: { status }, authenticated: true }); },
    async myApplications() { return array(await request('/api/users/me/applications', undefined, { authenticated: true })); },
    async myTeams() { return array(await request('/api/users/me/teams', undefined, { authenticated: true })); },
    async devices(id) {
      return array(await request('/api/posts/' + Number(id) + '/devices', undefined, { authenticated: true })).map(({ device_credential, ...device }) => device);
    },
    async registerDevice(id) { return request('/api/posts/' + Number(id) + '/devices', undefined, { method: 'POST', authenticated: true }); },
    async startAttendance(id, deviceId) {
      return sessionMetadata(await request('/api/posts/' + Number(id) + '/attendance-sessions', undefined, { method: 'POST', body: { device_id: Number(deviceId) }, authenticated: true }));
    },
    async sessions(id) { return array(await request('/api/posts/' + Number(id) + '/attendance-sessions', undefined, { authenticated: true })).map(sessionMetadata); },
    async closeAttendance(id) { return sessionMetadata(await request('/api/attendance-sessions/' + Number(id) + '/close', undefined, { method: 'POST', authenticated: true })); },
    async roster(id) { return array(await request('/api/attendance-sessions/' + Number(id) + '/records', undefined, { authenticated: true })); },
    async checkIn(id, code) {
      if (!/^\d{6}$/.test(String(code))) throw apiError('숫자 6자리를 입력해 주세요.');
      return request('/api/attendance-sessions/' + Number(id) + '/check-in', undefined, { method: 'POST', body: { code: String(code) }, authenticated: true });
    },
    async login(username, password) {
      const input = { username: String(username || '').trim(), password: String(password || '') };
      if (!input.username || input.username.length > 20 || /\s/.test(input.username) || !input.password || input.password.length > 128) throw apiError('아이디는 공백 없이 1~20자, 비밀번호는 1~128자로 입력해 주세요.');
      const result = await request('/api/auth/login', undefined, { method: 'POST', body: input });
      const identity = storeLogin(result);
      try { return await server.refreshMe(); }
      catch (error) { if (auth()?.token === identity.token) clearAuth(); throw error; }
    },
    async refreshMe() {
      const identity = auth();
      if (!identity) return null;
      const user = await request('/api/users/me', undefined, { authenticated: true });
      if (!validUser(user)) throw apiError('사용자 정보 응답 형식이 올바르지 않습니다.');
      const current = auth();
      if (!current || current.user.username !== identity.user.username) return null;
      const safeUser = { username: user.username, name: user.name, created_at: user.created_at ?? null };
      sessionStorage.setItem(AUTH_KEY, JSON.stringify({ ...current, user: safeUser }));
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
      if (server.me()) {
        const context = await request('/api/posts/' + p.id + '/context', signal, { authenticated: true });
        if (typeof context?.is_owner !== 'boolean') throw apiError('모집글 권한 응답 형식이 올바르지 않습니다.');
        return { ...p, is_owner: context.is_owner, my_application: context.my_application || null };
      }
      return { ...p, is_owner: false, my_application: null };
    }
  };
  function array(value) { if (!Array.isArray(value)) throw apiError('목록 응답 형식이 올바르지 않습니다.'); return value; }
  function sessionMetadata(value) {
    if (!value || !Number.isInteger(value.id) || !['OPEN', 'CLOSED'].includes(value.status) || !Number.isFinite(Date.parse(value.expiry_time))) throw apiError('출석 회차 응답 형식이 올바르지 않습니다.');
    const { code, ...metadata } = value;
    return metadata;
  }
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
