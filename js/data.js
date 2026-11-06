/* DB-shaped local adapter. Replace this public API with FastAPI calls later. */
(function (root) {
  'use strict';
  const KEY = 'studymate.db.v2';
  const AUTH = 'studymate.auth.v2';
  const duration = 5 * 60 * 1000;
  const empty = () => ({ version: 2, users: [], posts: [], applications: [], approved_members: [], devices: [], attendance_sessions: [], attendance_records: [], attempts: [], next: {} });
  function read() {
    try {
      const raw = localStorage.getItem(KEY);
      if (!raw) return empty();
      const db = JSON.parse(raw);
      if (db.version !== 2 || !['users', 'posts', 'applications', 'approved_members', 'devices', 'attendance_sessions', 'attendance_records', 'attempts'].every(k => Array.isArray(db[k])) || !db.next) throw new Error();
      return db;
    } catch { throw new Error('저장된 데이터를 읽을 수 없습니다. 브라우저 저장 공간을 확인해 주세요.'); }
  }
  function write(db) {
    try { localStorage.setItem(KEY, JSON.stringify(db)); }
    catch { throw new Error('저장에 실패했습니다. 브라우저 저장 공간을 확인해 주세요.'); }
  }
  async function mutate(action) {
    const run = () => { const db = read(); const value = action(db); write(db); return value; };
    if (root.navigator?.locks) return navigator.locks.request(KEY, run);
    return run();
  }
  function next(db, table) { db.next[table] = (db.next[table] || 0) + 1; return db.next[table]; }
  function now() { return new Date().toISOString(); }
  function text(value, label, max) {
    const v = String(value ?? '').trim();
    if (!v || v.length > max) throw new Error(`${label}: 1~${max}자로 입력해 주세요.`);
    return v;
  }
  function me(db = read()) {
    const username = sessionStorage.getItem(AUTH);
    const user = db.users.find(u => u.username === username);
    return user ? { username: user.username, name: user.name } : null;
  }
  function requireUser(db) { const u = me(db); if (!u) throw new Error('로그인이 필요합니다.'); return u; }
  function post(db, id) { const p = db.posts.find(p => p.id === Number(id)); if (!p) throw new Error('존재하지 않는 모집글입니다.'); return p; }
  function owner(db, id) { const p = post(db, id); if (p.author_id !== requireUser(db).username) throw new Error('팀장만 사용할 수 있습니다.'); return p; }
  function eligible(db, p, username) { return p.author_id === username || db.approved_members.some(m => m.post_id === p.id && m.member_id === username); }
  function count(db, p) { return 1 + db.approved_members.filter(m => m.post_id === p.id).length; }
  function publicPost(db, p) { return { ...p, current_size: count(db, p), author_name: db.users.find(u => u.username === p.author_id)?.name || p.author_id, applicant_count: db.applications.filter(a => a.post_id === p.id).length }; }
  function session(db, id) { const s = db.attendance_sessions.find(s => s.id === Number(id)); if (!s) throw new Error('출석 회차를 찾을 수 없습니다.'); return s; }
  function open(s) { return s.status === 'OPEN' && Date.parse(s.expiry_time) > Date.now(); }
  function publicSession(s) { const { code, ...metadata } = s; return { ...metadata, status: open(s) ? 'OPEN' : 'CLOSED' }; }
  function bytesToHex(bytes) { return Array.from(bytes, b => b.toString(16).padStart(2, '0')).join(''); }
  async function passwordHash(password, salt) {
    if (!root.crypto?.subtle) throw new Error('회원가입·로그인은 localhost 또는 HTTPS 환경에서 실행해 주세요.');
    const key = await crypto.subtle.importKey('raw', new TextEncoder().encode(password), 'PBKDF2', false, ['deriveBits']);
    const bits = await crypto.subtle.deriveBits({ name: 'PBKDF2', salt: new TextEncoder().encode(salt), iterations: 100000, hash: 'SHA-256' }, key, 256);
    return bytesToHex(new Uint8Array(bits));
  }
  const api = {
    me,
    async signup(input) {
      const username = text(input.username, '아이디', 20);
      if (!/^[A-Za-z0-9_-]{4,20}$/.test(username)) throw new Error('아이디는 영문·숫자·밑줄·하이픈 4~20자입니다.');
      const name = text(input.name, '이름', 50);
      const password = String(input.password || '');
      if (password.length < 8 || password.length > 128) throw new Error('비밀번호는 8~128자로 입력해 주세요.');
      const salt = bytesToHex(crypto.getRandomValues(new Uint8Array(16)));
      const hash = await passwordHash(password, salt);
      return mutate(db => {
        if (db.users.some(u => u.username === username)) throw new Error('이미 사용 중인 아이디입니다.');
        db.users.push({ username, name, password_hash: hash, password_salt: salt, created_at: now() });
        return { username, name };
      });
    },
    async login(username, password) {
      const u = read().users.find(u => u.username === String(username).trim());
      if (!u || await passwordHash(String(password), u.password_salt) !== u.password_hash) throw new Error('아이디 또는 비밀번호가 올바르지 않습니다.');
      sessionStorage.setItem(AUTH, u.username);
      return me();
    },
    logout() { sessionStorage.removeItem(AUTH); },
    async posts() { const db = read(); return db.posts.map(p => publicPost(db, p)).sort((a, b) => b.id - a.id); },
    async getPost(id) { const db = read(); const p = post(db, id); const u = me(db); return { ...publicPost(db, p), my_application: u ? db.applications.find(a => a.post_id === p.id && a.applicant_id === u.username) || null : null }; },
    async savePost(input, id) {
      return mutate(db => {
        const u = requireUser(db);
        const old = id == null ? null : owner(db, id);
        const target_size = Number(input.target_size);
        if (!Number.isInteger(target_size) || target_size < 2 || target_size > 100) throw new Error('팀 정원은 팀장 포함 2~100명입니다.');
        if (old && target_size < count(db, old)) throw new Error('팀 정원은 현재 인원보다 작을 수 없습니다.');
        const fields = { title: text(input.title, '제목', 255), content: text(input.content, '모집 내용', 10000), category: text(input.category, '분야', 100), target_size };
        if (old) {
          Object.assign(old, fields, { current_size: count(db, old) });
          if (old.current_size >= target_size) old.status = 'CLOSED';
          return old.id;
        }
        const newId = next(db, 'posts');
        db.posts.push({ id: newId, author_id: u.username, ...fields, current_size: 1, status: 'RECRUITING', created_at: now() });
        return newId;
      });
    },
    async deletePost(id) {
      return mutate(db => {
        const p = owner(db, id);
        const sessions = db.attendance_sessions.filter(s => s.post_id === p.id).map(s => s.id);
        db.attendance_records = db.attendance_records.filter(r => !sessions.includes(r.session_id));
        db.attempts = db.attempts.filter(r => !sessions.includes(r.session_id));
        for (const key of ['applications', 'approved_members', 'devices', 'attendance_sessions']) db[key] = db[key].filter(r => r.post_id !== p.id);
        db.posts = db.posts.filter(r => r.id !== p.id);
      });
    },
    async closePost(id) { return mutate(db => { owner(db, id).status = 'CLOSED'; }); },
    async apply(id, message) {
      return mutate(db => {
        const p = post(db, id); const u = requireUser(db);
        if (p.author_id === u.username) throw new Error('자신의 모집글에는 지원할 수 없습니다.');
        if (p.status !== 'RECRUITING' || count(db, p) >= p.target_size) throw new Error('모집이 마감되었습니다.');
        if (db.applications.some(a => a.post_id === p.id && a.applicant_id === u.username)) throw new Error('이미 지원한 모집글입니다.');
        db.applications.push({ id: next(db, 'applications'), post_id: p.id, applicant_id: u.username, message: text(message, '지원 동기', 5000), status: 'PENDING', applied_at: now() });
      });
    },
    async applicants(id) {
      const db = read(); const p = owner(db, id);
      return db.applications.filter(a => a.post_id === p.id).map(a => ({ ...a, name: db.users.find(u => u.username === a.applicant_id)?.name || a.applicant_id }));
    },
    async decide(applicationId, status) {
      return mutate(db => {
        const a = db.applications.find(a => a.id === Number(applicationId));
        if (!a) throw new Error('지원서를 찾을 수 없습니다.');
        const p = owner(db, a.post_id);
        if (!['APPROVED', 'REJECTED'].includes(status)) throw new Error('잘못된 지원 상태입니다.');
        if (a.status !== 'PENDING') throw new Error('이미 처리한 지원서입니다.');
        if (status === 'APPROVED') {
          if (count(db, p) >= p.target_size) throw new Error('팀 정원이 모두 찼습니다.');
          db.approved_members.push({ id: next(db, 'approved_members'), post_id: p.id, member_id: a.applicant_id, application_id: a.id });
        }
        a.status = status; p.current_size = count(db, p);
        if (p.current_size >= p.target_size) p.status = 'CLOSED';
      });
    },
    async myApplications() { const db = read(); const u = requireUser(db); return db.applications.filter(a => a.applicant_id === u.username).map(a => ({ ...a, post: publicPost(db, post(db, a.post_id)) })).sort((a, b) => b.id - a.id); },
    async myTeams() { const db = read(); const u = requireUser(db); return db.posts.filter(p => eligible(db, p, u.username)).map(p => ({ ...publicPost(db, p), role: p.author_id === u.username ? 'LEADER' : 'MEMBER' })); },
    async devices(id) { const db = read(); owner(db, id); return db.devices.filter(d => d.post_id === Number(id)).map(({ device_credential, ...d }) => d); },
    async addSimulator(id) {
      return mutate(db => {
        const p = owner(db, id);
        let d = db.devices.find(d => d.post_id === p.id);
        if (!d) { d = { id: next(db, 'devices'), post_id: p.id, last_ack: null }; db.devices.push(d); }
        return d.id;
      });
    },
    async startAttendance(id, deviceId) {
      return mutate(db => {
        const p = owner(db, id);
        const device = db.devices.find(d => d.id === Number(deviceId) && d.post_id === p.id);
        if (!device) throw new Error('팀에 연결된 장치를 선택해 주세요.');
        if (db.attendance_sessions.some(s => open(s) && (s.device_id === device.id || s.post_id === p.id))) throw new Error('이미 진행 중인 출석이 있습니다.');
        // Rejection sampling avoids modulo bias; preserve leading zeroes.
        let n; do { n = crypto.getRandomValues(new Uint32Array(1))[0]; } while (n >= 4294000000);
        const s = { id: next(db, 'attendance_sessions'), post_id: p.id, device_id: device.id, leader_id: p.author_id, code: String(n % 1000000).padStart(6, '0'), status: 'OPEN', display_ack: false, start_time: now(), expiry_time: new Date(Date.now() + duration).toISOString() };
        db.attendance_sessions.push(s);
        return publicSession(s);
      });
    },
    async closeAttendance(sessionId) { return mutate(db => { const s = session(db, sessionId); owner(db, s.post_id); s.status = 'CLOSED'; }); },
    async sessions(id) {
      const db = read(); const p = post(db, id); const u = requireUser(db);
      if (!eligible(db, p, u.username)) throw new Error('승인된 팀원만 출석 정보를 볼 수 있습니다.');
      return db.attendance_sessions.filter(s => s.post_id === p.id).map(s => ({ ...publicSession(s), my_record: db.attendance_records.find(r => r.session_id === s.id && r.member_id === u.username) || null })).sort((a, b) => b.id - a.id);
    },
    async roster(sessionId) {
      const db = read(); const s = session(db, sessionId); owner(db, s.post_id);
      return db.approved_members.filter(m => m.post_id === s.post_id).map(m => ({ member_id: m.member_id, name: db.users.find(u => u.username === m.member_id)?.name || m.member_id, record: db.attendance_records.find(r => r.session_id === s.id && r.member_id === m.member_id) || null }));
    },
    async simulator(id) {
      const db = read(); const p = owner(db, id);
      const s = db.attendance_sessions.find(s => s.post_id === p.id && open(s));
      return s ? { id: s.id, code: s.code, expiry_time: s.expiry_time } : null;
    },
    async acknowledge(sessionId) {
      return mutate(db => { const s = session(db, sessionId); owner(db, s.post_id); if (!open(s)) throw new Error('종료된 출석입니다.'); s.display_ack = true; db.devices.find(d => d.id === s.device_id).last_ack = now(); });
    },
    async checkIn(sessionId, code) {
      const result = await mutate(db => {
        const s = session(db, sessionId); const u = requireUser(db);
        if (!db.approved_members.some(m => m.post_id === s.post_id && m.member_id === u.username)) throw new Error('승인된 팀원만 출석 인증할 수 있습니다.');
        const existing = db.attendance_records.find(r => r.session_id === s.id && r.member_id === u.username);
        const attempts = db.attempts.filter(a => a.session_id === s.id && a.member_id === u.username && a.at > Date.now() - 60000);
        if (attempts.length >= 5) return { error: '시도가 너무 많습니다. 1분 후 다시 시도해 주세요.' };
        const fail = message => { db.attempts = db.attempts.filter(a => a.at > Date.now() - 60000); db.attempts.push({ session_id: s.id, member_id: u.username, at: Date.now() }); return { error: message }; };
        if (!open(s)) return fail('출석 시간이 만료되었거나 종료되었습니다.');
        if (!/^\d{6}$/.test(String(code))) return fail('숫자 6자리를 입력해 주세요.');
        if (String(code) !== s.code) return fail('출석 코드가 올바르지 않습니다.');
        if (existing) return { record: existing };
        const record = { id: next(db, 'attendance_records'), session_id: s.id, member_id: u.username, is_present: 1, checked_in_at: now() };
        db.attendance_records.push(record);
        return { record };
      });
      if (result.error) throw new Error(result.error);
      return result.record;
    }
  };
  root.StudyMate = api;
})(globalThis);
