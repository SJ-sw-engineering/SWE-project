CREATE DATABASE IF NOT EXISTS recruitment_db;
USE recruitment_db;

DROP TABLE IF EXISTS AttendanceRecords, AttendanceSessions, ApprovedMembers, Devices, Applications, Posts, Users;

CREATE TABLE IF NOT EXISTS Users (
    username VARCHAR(20) PRIMARY KEY,
    password VARCHAR(255) NOT NULL,
    name VARCHAR(50) NOT NULL,
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

CREATE TABLE IF NOT EXISTS Posts (
    id INT AUTO_INCREMENT PRIMARY KEY,
    author_id VARCHAR(20) NOT NULL,
    title VARCHAR(255) NOT NULL,
    content TEXT NOT NULL,
    category VARCHAR(100) NOT NULL,
    target_size INT NOT NULL,
    current_size INT DEFAULT 1,
    status ENUM('RECRUITING', 'CLOSED') DEFAULT 'RECRUITING',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (author_id) REFERENCES Users(username) ON DELETE CASCADE
);

INSERT INTO Posts (author_id, title, content, category, target_size, current_size, status) VALUES
('20191001', '웹 프론트엔드 프로젝트 팀원 구합니다', '리액트를 활용한 교내 프로젝트 같이 하실 분 구합니다.', 'Web/Frontend', 4, 1, 'RECRUITING'),
('20191005', '파이썬 데이터 분석 스터디원 모집', '기초부터 함께 공부할 데이터 분석 스터디입니다.', 'Data/AI', 5, 2, 'RECRUITING'),
('20201012', '안드로이드 앱 공모전 백엔드 구해요', '코틀린 앱과 연동할 스프링 백엔드 개발자 1명 찾습니다.', 'App/Backend', 3, 3, 'CLOSED'),
('20211020', '알고리즘 코딩테스트 스터디 (C++)', '매주 백준 골드 문제 3개씩 푸는 스터디입니다.', 'Study/Algorithm', 4, 1, 'RECRUITING'),
('20221035', '게임 잼 참가할 유니티 개발자 찾습니다', '이번 주말 해커톤 같이 참가하실 분!', 'Game/Unity', 2, 1, 'RECRUITING');

CREATE TABLE IF NOT EXISTS Applications (
    id INT AUTO_INCREMENT PRIMARY KEY,
    post_id INT NOT NULL,
    applicant_id VARCHAR(20) NOT NULL,
    message TEXT NOT NULL,
    status ENUM('PENDING', 'APPROVED', 'REJECTED') DEFAULT 'PENDING',
    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (post_id) REFERENCES Posts(id) ON DELETE CASCADE,
    FOREIGN KEY (applicant_id) REFERENCES Users(username) ON DELETE CASCADE
);

INSERT INTO Applications (post_id, applicant_id, message, status) VALUES
(1, '20191002', '리액트 프론트엔드 개발 경험이 있습니다. 열심히 참여하겠습니다!', 'PENDING'),
(1, '20191003', 'UI/UX 디자인과 프론트엔드 연동에 관심이 많습니다.', 'APPROVED'),
(2, '20201006', '파이썬 기초 문법을 끝내고 데이터 분석을 막 시작했습니다.', 'PENDING'),
(4, '20201008', '백준 플래티넘 달성이 목표입니다. 매주 꾸준히 참여하겠습니다.', 'REJECTED'),
(5, '20201015', '유니티 엔진으로 캐주얼 게임을 2회 출시한 경험이 있습니다.', 'APPROVED');

CREATE TABLE IF NOT EXISTS Devices (
    id INT AUTO_INCREMENT PRIMARY KEY,
    post_id INT NOT NULL,
    device_credential VARCHAR(255) NOT NULL,
    last_ack TIMESTAMP NULL,
    FOREIGN KEY (post_id) REFERENCES Posts(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS ApprovedMembers (
    id INT AUTO_INCREMENT PRIMARY KEY,
    post_id INT NOT NULL,
    member_id VARCHAR(20) NOT NULL,
    application_id INT NOT NULL,
    FOREIGN KEY (post_id) REFERENCES Posts(id) ON DELETE CASCADE,
    FOREIGN KEY (member_id) REFERENCES Users(username) ON DELETE CASCADE,
    FOREIGN KEY (application_id) REFERENCES Applications(id) ON DELETE CASCADE
);

INSERT INTO ApprovedMembers (post_id, member_id, application_id) VALUES
(1, '20191003', 2),
(5, '20201015', 5);

CREATE TABLE IF NOT EXISTS AttendanceSessions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    post_id INT NOT NULL,
    device_id INT NOT NULL,
    leader_id VARCHAR(20) NOT NULL,
    code VARCHAR(6) NOT NULL,
    status ENUM('OPEN', 'CLOSED') DEFAULT 'OPEN',
    display_ack BOOLEAN DEFAULT FALSE,
    start_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expiry_time TIMESTAMP NOT NULL,
    FOREIGN KEY (post_id) REFERENCES Posts(id) ON DELETE CASCADE,
    FOREIGN KEY (device_id) REFERENCES Devices(id) ON DELETE CASCADE,
    FOREIGN KEY (leader_id) REFERENCES Users(username) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS AttendanceRecords (
    id INT AUTO_INCREMENT PRIMARY KEY,
    session_id INT NOT NULL,
    member_id VARCHAR(20) NOT NULL,
    is_present TINYINT(1) DEFAULT 1,
    checked_in_at TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES AttendanceSessions(id) ON DELETE CASCADE,
    FOREIGN KEY (member_id) REFERENCES Users(username) ON DELETE CASCADE,
    UNIQUE (session_id, member_id)
);

UPDATE Posts p
SET current_size = 1 + (
    SELECT COUNT(*)
    FROM ApprovedMembers am
    WHERE am.post_id = p.id
);
