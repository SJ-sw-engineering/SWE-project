CREATE DATABASE IF NOT EXISTS recruitment_db;
USE recruitment_db;

-- 외래키 종속성을 고려하여 자식 테이블부터 삭제
DROP TABLE IF EXISTS AttendanceRecords, AttendanceSessions, ApprovedMembers, Devices, Applications, Posts, Users;

-- 1. Users 테이블 (username을 PRIMARY KEY로 변경)
CREATE TABLE IF NOT EXISTS Users (
    username VARCHAR(20) PRIMARY KEY COMMENT '학번 (로그인 ID)',
    password VARCHAR(255) NOT NULL COMMENT '비밀번호 (생년월일 8자리)',
    name VARCHAR(50) NOT NULL COMMENT '사용자 이름',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO Users (username, password, name) VALUES
('20191001', '20000115', '학생1'),
('20191002', '19991123', '학생2'),
('20191003', '20000305', '학생3'),
('20191004', '20000712', '학생4'),
('20191005', '19990530', '학생5'),
('20201006', '20010214', '학생6'),
('20201007', '20010822', '학생7'),
('20201008', '20011201', '학생8'),
('20201009', '20010915', '학생9'),
('20201010', '20010418', '학생10'),
('20201011', '20010625', '학생11'),
('20201012', '20011030', '학생12'),
('20201013', '20010105', '학생13'),
('20201014', '20010321', '학생14'),
('20201015', '20011111', '학생15'),
('20211016', '20020505', '학생16'),
('20211017', '20020707', '학생17'),
('20211018', '20020909', '학생18'),
('20211019', '20021225', '학생19'),
('20211020', '20020228', '학생20'),
('20211021', '20020815', '학생21'),
('20211022', '20021003', '학생22'),
('20211023', '20020404', '학생23'),
('20211024', '20020606', '학생24'),
('20211025', '20021111', '학생25'),
('20211026', '20020120', '학생26'),
('20211027', '20020315', '학생27'),
('20211028', '20020522', '학생28'),
('20211029', '20020730', '학생29'),
('20211030', '20020912', '학생30'),
('20221031', '20030101', '학생31'),
('20221032', '20030214', '학생32'),
('20221033', '20030303', '학생33'),
('20221034', '20030405', '학생34'),
('20221035', '20030518', '학생35'),
('20221036', '20030620', '학생36'),
('20221037', '20030725', '학생37'),
('20221038', '20030810', '학생38'),
('20221039', '20030915', '학생39'),
('20221040', '20031022', '학생40'),
('20221041', '20031130', '학생41'),
('20221042', '20031225', '학생42'),
('20221043', '20030115', '학생43'),
('20221044', '20030228', '학생44'),
('20221045', '20030410', '학생45'),
('20231046', '20040505', '학생46'),
('20231047', '20040612', '학생47'),
('20231048', '20040718', '학생48'),
('20231049', '20040825', '학생49'),
('20231050', '20040909', '학생50'),
('20231051', '20041003', '학생51'),
('20231052', '20041111', '학생52'),
('20231053', '20041220', '학생53'),
('20231054', '20040130', '학생54'),
('20231055', '20040215', '학생55'),
('20231056', '20040322', '학생56'),
('20231057', '20040404', '학생57'),
('20231058', '20040518', '학생58'),
('20231059', '20040625', '학생59'),
('20231060', '20040731', '학생60'),
('20241061', '20050101', '학생61'),
('20241062', '20050214', '학생62'),
('20241063', '20050301', '학생63'),
('20241064', '20050415', '학생64'),
('20241065', '20050505', '학생65'),
('20241066', '20050610', '학생66'),
('20241067', '20050720', '학생67'),
('20241068', '20050815', '학생68'),
('20241069', '20050922', '학생69'),
('20241070', '20051030', '학생70');

-- 2. Posts 테이블 (author_id를 VARCHAR(20)으로 변경)
CREATE TABLE IF NOT EXISTS Posts (
    id INT AUTO_INCREMENT PRIMARY KEY,
    author_id VARCHAR(20) NOT NULL COMMENT '작성자 학번 (Users 테이블 참조)',
    title VARCHAR(255) NOT NULL COMMENT '모집글 제목',
    content TEXT NOT NULL COMMENT '모집글 내용',
    category VARCHAR(100) NOT NULL COMMENT '카테고리 및 모집 분야',
    target_size INT NOT NULL COMMENT '목표 모집 인원',
    current_size INT DEFAULT 1 COMMENT '현재 모집된 인원 (작성자 포함 기본 1명)',
    status ENUM('RECRUITING', 'CLOSED') DEFAULT 'RECRUITING' COMMENT '모집 상태',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (author_id) REFERENCES Users(username) ON DELETE CASCADE
);

-- author_id를 기존 숫자 ID에 해당하는 학번으로 수정
INSERT INTO Posts (author_id, title, content, category, target_size, current_size, status) VALUES
('20191001', '웹 프론트엔드 프로젝트 팀원 구합니다', '리액트를 활용한 교내 프로젝트 같이 하실 분 구합니다.', 'Web/Frontend', 4, 1, 'RECRUITING'),
('20191005', '파이썬 데이터 분석 스터디원 모집', '기초부터 함께 공부할 데이터 분석 스터디입니다.', 'Data/AI', 5, 2, 'RECRUITING'),
('20201012', '안드로이드 앱 공모전 백엔드 구해요', '코틀린 앱과 연동할 스프링 백엔드 개발자 1명 찾습니다.', 'App/Backend', 3, 3, 'CLOSED'),
('20211020', '알고리즘 코딩테스트 스터디 (C++)', '매주 백준 골드 문제 3개씩 푸는 스터디입니다.', 'Study/Algorithm', 4, 1, 'RECRUITING'),
('20221035', '게임 잼 참가할 유니티 개발자 찾습니다', '이번 주말 해커톤 같이 참가하실 분!', 'Game/Unity', 2, 1, 'RECRUITING');

-- 3. Applications 테이블 (applicant_id를 VARCHAR(20)으로 변경)
CREATE TABLE IF NOT EXISTS Applications (
    id INT AUTO_INCREMENT PRIMARY KEY,
    post_id INT NOT NULL COMMENT '지원하려는 모집글 ID (Posts 테이블 참조)',
    applicant_id VARCHAR(20) NOT NULL COMMENT '지원자 학번 (Users 테이블 참조)',
    message TEXT NOT NULL COMMENT '지원 동기 또는 메시지',
    status ENUM('PENDING', 'APPROVED', 'REJECTED') DEFAULT 'PENDING' COMMENT '지원 상태',
    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (post_id) REFERENCES Posts(id) ON DELETE CASCADE,
    FOREIGN KEY (applicant_id) REFERENCES Users(username) ON DELETE CASCADE
);

-- applicant_id를 기존 숫자 ID에 해당하는 학번으로 수정
INSERT INTO Applications (post_id, applicant_id, message, status) VALUES
(1, '20191002', '리액트 프론트엔드 개발 경험이 있습니다. 열심히 참여하겠습니다!', 'PENDING'),
(1, '20191003', 'UI/UX 디자인과 프론트엔드 연동에 관심이 많습니다.', 'APPROVED'),
(2, '20201006', '파이썬 기초 문법을 끝내고 데이터 분석을 막 시작했습니다.', 'PENDING'),
(4, '20201008', '백준 플래티넘 달성이 목표입니다. 매주 꾸준히 참여하겠습니다.', 'REJECTED'),
(5, '20201015', '유니티 엔진으로 캐주얼 게임을 2회 출시한 경험이 있습니다.', 'APPROVED');


-- ==========================================
-- 출석 및 하드웨어 연동을 위한 추가 테이블
-- ==========================================

-- 4. 기기 정보 (Devices)
CREATE TABLE IF NOT EXISTS Devices (
    id INT AUTO_INCREMENT PRIMARY KEY,
    post_id INT NOT NULL COMMENT '연결된 팀(모집글) ID',
    device_credential VARCHAR(255) NOT NULL COMMENT '기기 인증 정보 참조',
    last_ack TIMESTAMP NULL COMMENT '마지막 디스플레이 확인/하트비트',
    FOREIGN KEY (post_id) REFERENCES Posts(id) ON DELETE CASCADE
);

-- 5. 승인된 팀원 목록 (ApprovedMembers)
CREATE TABLE IF NOT EXISTS ApprovedMembers (
    id INT AUTO_INCREMENT PRIMARY KEY,
    post_id INT NOT NULL COMMENT '팀(모집글) ID',
    member_id VARCHAR(20) NOT NULL COMMENT '승인된 팀원 학번 (Users 테이블 참조)',
    application_id INT NOT NULL COMMENT '승인된 지원서 ID',
    FOREIGN KEY (post_id) REFERENCES Posts(id) ON DELETE CASCADE,
    FOREIGN KEY (member_id) REFERENCES Users(username) ON DELETE CASCADE,
    FOREIGN KEY (application_id) REFERENCES Applications(id) ON DELETE CASCADE
);

-- 6. 출석 세션 (AttendanceSessions)
CREATE TABLE IF NOT EXISTS AttendanceSessions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    post_id INT NOT NULL COMMENT '팀(모집글) ID',
    device_id INT NOT NULL COMMENT '기기 ID',
    leader_id VARCHAR(20) NOT NULL COMMENT '팀장 학번 (Users 테이블 참조)',
    code VARCHAR(6) NOT NULL COMMENT '6자리 출석 코드',
    status ENUM('OPEN', 'CLOSED') DEFAULT 'OPEN' COMMENT '세션 상태 (OPEN/CLOSED)',
    display_ack BOOLEAN DEFAULT FALSE COMMENT '디스플레이 확인 여부',
    start_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '시작 시간',
    expiry_time TIMESTAMP NOT NULL COMMENT '만료 시간',
    FOREIGN KEY (post_id) REFERENCES Posts(id) ON DELETE CASCADE,
    FOREIGN KEY (device_id) REFERENCES Devices(id) ON DELETE CASCADE,
    FOREIGN KEY (leader_id) REFERENCES Users(username) ON DELETE CASCADE
);

-- 7. 출석 기록 (AttendanceRecords)
CREATE TABLE IF NOT EXISTS AttendanceRecords (
    id INT AUTO_INCREMENT PRIMARY KEY,
    session_id INT NOT NULL COMMENT '출석 세션 ID',
    member_id VARCHAR(20) NOT NULL COMMENT '팀원 학번 (Users 테이블 참조)',
    is_present TINYINT(1) DEFAULT 1 COMMENT '0: 결석, 1: 출석 (기본값 출석)',
    checked_in_at TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP COMMENT '출석 체크된 시간',
    FOREIGN KEY (session_id) REFERENCES AttendanceSessions(id) ON DELETE CASCADE,
    FOREIGN KEY (member_id) REFERENCES Users(username) ON DELETE CASCADE,
    UNIQUE (session_id, member_id) COMMENT '한 세션과 멤버의 쌍은 유일해야 함'
);