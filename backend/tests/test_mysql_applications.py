"""Opt-in local MySQL checks. Never use the project's .env or TiDB endpoint."""

from concurrent.futures import ThreadPoolExecutor
import os
from pathlib import Path
from threading import Barrier
from uuid import uuid4

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import MetaData, URL, UniqueConstraint, create_engine, event, inspect, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.main import create_app
from app.models import Application, ApprovedMember, Post, User
from app.security import hash_password

MIGRATIONS = Path(__file__).resolve().parents[1] / "migrations"
UNIQUE_NAMES = {"uq_applications_post_applicant", "uq_approved_post_member", "uq_approved_application"}


def statements(filename, database):
    source = (MIGRATIONS / filename).read_text(encoding="utf-8")
    source = "\n".join(line for line in source.splitlines() if not line.lstrip().startswith("--"))
    return [part.strip().replace("USE recruitment_db", "USE `" + database + "`")
            for part in source.split(";") if part.strip()]


@pytest.fixture
def mysql_engine():
    port = os.environ.get("RECRUITMENT_MYSQL_TEST_PORT")
    if not port:
        pytest.skip("Set RECRUITMENT_MYSQL_TEST_PORT for a disposable local MySQL instance")
    password = os.environ["RECRUITMENT_MYSQL_TEST_PASSWORD"]
    # Deliberately hard-code loopback. There is no option to point this at TiDB.
    url = URL.create("mysql+pymysql", username="root", password=password,
                     host="127.0.0.1", port=int(port))
    admin = create_engine(url, isolation_level="AUTOCOMMIT")
    database = "recruitment_api_test_" + uuid4().hex
    with admin.connect() as connection:
        connection.exec_driver_sql(f"CREATE DATABASE `{database}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
    engine = create_engine(url.set(database=database), connect_args={"init_command": "SET time_zone = '+00:00'"})
    try:
        # Reconstruct the original four relevant tables, before the new uniques.
        legacy = MetaData()
        for model in [User, Post, Application, ApprovedMember]:
            table = model.__table__.to_metadata(legacy)
            for constraint in list(table.constraints):
                if isinstance(constraint, UniqueConstraint) and constraint.name in UNIQUE_NAMES:
                    table.constraints.remove(constraint)
        legacy.create_all(engine)
        with Session(engine) as db:
            hashed = hash_password("local-test-password")
            db.add_all([User(username=name, name=name, password=hashed)
                        for name in ["mysql_leader", "mysql_member_a", "mysql_member_b"]])
            db.flush()
            db.add_all([Post(id=i, author_id="mysql_leader", title="테스트", content="테스트", category="Web",
                             target_size=2, current_size=999 if i == 1 else 1, status="RECRUITING") for i in [1, 2, 3]])
            db.flush()
            db.add_all([
                Application(id=1, post_id=1, applicant_id="mysql_member_a", message="기존 승인", status="APPROVED"),
                Application(id=2, post_id=2, applicant_id="mysql_member_a", message="지원A", status="PENDING"),
                Application(id=3, post_id=2, applicant_id="mysql_member_b", message="지원B", status="PENDING"),
            ])
            db.flush()
            db.add(ApprovedMember(post_id=1, member_id="mysql_member_a", application_id=1))
            db.commit()
        with engine.connect() as connection:
            for statement in statements("002_applications_precheck.sql", database):
                result = connection.exec_driver_sql(statement)
                if result.returns_rows:
                    assert result.all() == []
            for filename in ["001_auth_sessions.sql", "002_applications_unique.sql"]:
                for statement in statements(filename, database):
                    connection.exec_driver_sql(statement)
            connection.commit()
        yield engine
    finally:
        engine.dispose()
        # The only dropped DB is the randomly named DB created above on loopback.
        assert database.startswith("recruitment_api_test_") and len(database) == 53
        with admin.connect() as connection:
            connection.exec_driver_sql(f"DROP DATABASE `{database}`")
        admin.dispose()


@pytest.fixture
def mysql_app(mysql_engine, settings):
    app = create_app()
    def sessions():
        with Session(mysql_engine) as db:
            yield db
    app.dependency_overrides[get_db] = sessions
    app.dependency_overrides[get_settings] = lambda: settings
    return app


def headers(app, username="mysql_leader"):
    with TestClient(app) as client:
        response = client.post("/api/auth/login", json={"username": username, "password": "local-test-password"})
        assert response.status_code == 200
        return {"Authorization": "Bearer " + response.json()["access_token"]}


def test_mysql_additive_migration_and_unique_constraints(mysql_engine):
    names = {item["name"] for table in ["Applications", "ApprovedMembers"]
             for item in inspect(mysql_engine).get_unique_constraints(table)}
    assert UNIQUE_NAMES <= names
    with Session(mysql_engine) as db:
        post = db.get(Post, 1)
        assert (post.current_size, post.status) == (2, "CLOSED")
        db.add(Application(post_id=1, applicant_id="mysql_member_a", message="중복", status="PENDING"))
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()
        db.add(ApprovedMember(post_id=1, member_id="mysql_member_a", application_id=3))
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()
        db.add(ApprovedMember(post_id=2, member_id="mysql_member_b", application_id=1))
        with pytest.raises(IntegrityError):
            db.commit()
    with mysql_engine.connect() as connection:
        results = [connection.exec_driver_sql(query).all()
                   for query in statements("002_applications_verify.sql", mysql_engine.url.database)
                   if not query.startswith("USE")]
        assert len(results[0]) == 5
        assert all(result == [] for result in results[1:])


def test_mysql_concurrent_last_place_approval(mysql_app, mysql_engine):
    auth = headers(mysql_app)
    barrier = Barrier(2)
    def decide(application_id):
        with TestClient(mysql_app) as client:
            barrier.wait(timeout=10)
            return client.patch(f"/api/applications/{application_id}", headers=auth,
                                json={"status": "APPROVED"}).status_code
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(decide, [2, 3]))
    assert sorted(results) == [200, 409]
    with Session(mysql_engine) as db:
        assert (db.get(Post, 2).current_size, db.get(Post, 2).status) == (2, "CLOSED")
        assert sorted(db.scalars(select(Application.status).where(Application.post_id == 2))) == ["APPROVED", "PENDING"]
        assert len(db.scalars(select(ApprovedMember).where(ApprovedMember.post_id == 2)).all()) == 1


def test_mysql_concurrent_duplicate_application(mysql_app, mysql_engine):
    auth = headers(mysql_app, "mysql_member_a")
    barrier = Barrier(2)
    def apply(_):
        with TestClient(mysql_app) as client:
            barrier.wait(timeout=10)
            return client.post("/api/posts/3/applications", headers=auth, json={"message": "동시 지원"}).status_code
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(apply, range(2)))
    assert sorted(results) == [201, 409]
    with Session(mysql_engine) as db:
        assert len(db.scalars(select(Application).where(Application.post_id == 3)).all()) == 1


def test_mysql_failed_membership_insert_rolls_back_decision(mysql_app, mysql_engine):
    auth = headers(mysql_app)
    def fail_insert(_connection, _cursor, statement, parameters, _context, _many):
        if statement.lstrip().startswith("INSERT INTO") and "ApprovedMembers" in statement:
            raise IntegrityError("injected membership insert failure", None, Exception("test only"))
    event.listen(mysql_engine, "before_cursor_execute", fail_insert)
    try:
        with TestClient(mysql_app) as client:
            assert client.patch("/api/applications/2", headers=auth, json={"status": "APPROVED"}).status_code == 409
    finally:
        event.remove(mysql_engine, "before_cursor_execute", fail_insert)
    with Session(mysql_engine) as db:
        assert db.get(Application, 2).status == "PENDING"
        assert (db.get(Post, 2).current_size, db.get(Post, 2).status) == (1, "RECRUITING")
        assert db.scalars(select(ApprovedMember).where(ApprovedMember.post_id == 2)).all() == []
