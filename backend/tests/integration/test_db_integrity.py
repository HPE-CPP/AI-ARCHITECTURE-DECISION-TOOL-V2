"""
PHASE 4 — DATABASE INTEGRITY + CONCURRENCY TESTS
Tests: cascade deletes, unique constraints, transaction rollback,
       result upsert, signal persistence, concurrent writes.
"""
import uuid
import pytest
import threading
from datetime import datetime, timezone
from sqlalchemy.exc import IntegrityError


@pytest.mark.integration
class TestDatabaseCascadeDeletes:

    def test_delete_session_cascades_signals(self, db_session, seed_session, complete_signals):
        """Deleting a Session must cascade-delete its Signal rows."""
        from app.db.models import Signal
        # Persist some signals
        for name, data in complete_signals.items():
            db_session.add(Signal(
                session_id=seed_session.id,
                signal_name=name,
                value=data["value"],
                confidence=data["confidence"],
                source_text=data["source_text"],
                page_number=data["page_number"],
            ))
        db_session.commit()

        count_before = db_session.query(Signal).filter(Signal.session_id == seed_session.id).count()
        assert count_before == len(complete_signals)

        db_session.delete(seed_session)
        db_session.commit()

        count_after = db_session.query(Signal).filter(Signal.session_id == seed_session.id).count()
        assert count_after == 0, "Signals must be cascade-deleted when Session is deleted"

    def test_delete_session_cascades_result(self, db_session, seed_result, seed_session):
        """Deleting a Session must cascade-delete its Result row."""
        from app.db.models import Result
        result_count = db_session.query(Result).filter(Result.session_id == seed_session.id).count()
        assert result_count == 1

        db_session.delete(seed_session)
        db_session.commit()

        result_count_after = db_session.query(Result).filter(Result.session_id == seed_session.id).count()
        assert result_count_after == 0, "Result must be cascade-deleted when Session is deleted"

    def test_delete_project_sets_session_project_id_null(self, db_session, seed_session, seed_project):
        """Deleting a Project must SET NULL on sessions (ondelete=SET NULL)."""
        from app.db.models import Session as SessionModel
        session_id = seed_session.id

        db_session.delete(seed_project)
        db_session.commit()

        session = db_session.query(SessionModel).filter(SessionModel.id == session_id).first()
        # Session still exists (not deleted), but project_id is now NULL
        assert session is not None
        assert session.project_id is None


@pytest.mark.integration
class TestDatabaseUniqueConstraints:

    def test_result_unique_per_session(self, db_session, seed_session, complete_signals):
        """Result.session_id must be unique — inserting two must fail."""
        from app.db.models import Result
        from services.scoring_engine import ScoringEngine
        scoring = ScoringEngine()
        score = scoring.score(complete_signals)

        r1 = Result(
            session_id=seed_session.id,
            recommended_architecture=score["recommended"],
            confidence_score=score["confidence"],
            ranking=score["ranking"],
            scores=score["scores"],
            decision_breakdown=score["factor_breakdown"],
            why_not=score["why_not"],
            suitability=score["suitability"],
            followup_questions=[],
            sensitivity={},
            decision_trace=[],
            architecture_details=score["architecture_details"],
            created_at=datetime.now(timezone.utc),
        )
        db_session.add(r1)
        db_session.commit()

        r2 = Result(
            session_id=seed_session.id,  # Same session_id — must fail
            recommended_architecture="CAG",
            confidence_score=0.5,
            ranking=[],
            scores={},
            decision_breakdown={},
            why_not={},
            suitability={},
            followup_questions=[],
            sensitivity={},
            decision_trace=[],
            architecture_details={},
            created_at=datetime.now(timezone.utc),
        )
        db_session.add(r2)
        with pytest.raises(IntegrityError):
            db_session.flush()

    def test_user_email_must_be_unique(self, db_session, seed_user):
        """Two User rows with the same email must raise IntegrityError."""
        from app.db.models import User
        duplicate = User(
            id="different_uid_but_same_email",
            name="Duplicate",
            email=seed_user.email,  # Same email
            provider="google",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        db_session.add(duplicate)
        with pytest.raises(IntegrityError):
            db_session.flush()


@pytest.mark.integration
class TestResultUpsert:

    def test_score_and_persist_upserts_on_followup(self, db_session, seed_session, complete_signals):
        """Calling score_and_persist twice on same session must not duplicate Result rows."""
        from app.db.models import Result
        from app.services.recommendation_service import score_and_persist

        score_and_persist(db=db_session, session_id=str(seed_session.id), signals=complete_signals)
        score_and_persist(db=db_session, session_id=str(seed_session.id), signals=complete_signals)

        count = db_session.query(Result).filter(Result.session_id == seed_session.id).count()
        assert count == 1, f"Expected 1 Result, got {count} — upsert logic is broken"


@pytest.mark.integration
class TestSignalPersistence:

    def test_signals_persisted_to_db(self, db_session, seed_session, complete_signals):
        from app.db.models import Signal
        from app.services.signal_service import _signals_to_db
        _signals_to_db(db_session, str(seed_session.id), complete_signals)

        rows = db_session.query(Signal).filter(Signal.session_id == seed_session.id).all()
        assert len(rows) == len(complete_signals)

    def test_signal_confidence_stored_correctly(self, db_session, seed_session):
        from app.db.models import Signal
        sig = Signal(
            session_id=seed_session.id,
            signal_name="dataset_size",
            value="large",
            confidence=0.95,
            source_text="test",
            page_number=1,
        )
        db_session.add(sig)
        db_session.commit()

        row = db_session.query(Signal).filter(
            Signal.session_id == seed_session.id,
            Signal.signal_name == "dataset_size",
        ).first()
        assert row is not None
        assert abs(row.confidence - 0.95) < 0.0001

    def test_signal_source_text_truncated_to_2000(self, db_session, seed_session):
        """Source text longer than 2000 chars must be truncated on write."""
        from app.services.signal_service import _signals_to_db
        long_text = "A" * 5000
        _signals_to_db(db_session, str(seed_session.id), {
            "dataset_size": {"value": "large", "confidence": 0.9,
                             "source_text": long_text, "page_number": 1},
        })
        from app.db.models import Signal
        row = db_session.query(Signal).filter(
            Signal.session_id == seed_session.id,
            Signal.signal_name == "dataset_size",
        ).first()
        assert len(row.source_text) <= 2000

    def test_signal_reload_from_db_matches_original(self, db_session, seed_session, complete_signals):
        from app.services.signal_service import _signals_to_db, _signals_from_db
        _signals_to_db(db_session, str(seed_session.id), complete_signals)
        reloaded = _signals_from_db(db_session, str(seed_session.id))

        for key in complete_signals:
            assert key in reloaded
            assert reloaded[key]["value"] == complete_signals[key]["value"]


@pytest.mark.integration
class TestSessionStatusTransitions:

    def test_valid_status_values_stored(self, db_session):
        """All valid status enum values must be storable."""
        from app.db.models import Session as SessionModel
        for status in ["draft", "processing", "completed", "error"]:
            s = SessionModel(
                id=uuid.uuid4(),
                status=status,
                provider="ollama",
                filename="test.txt",
            )
            db_session.add(s)
        db_session.commit()  # Must not raise


import os  # noqa: E402

@pytest.mark.integration
@pytest.mark.skipif("sqlite" in os.environ.get("DATABASE_URL", ""), reason="SQLite does not handle concurrent writes well")
class TestConcurrentWrites:

    def test_concurrent_signal_inserts_for_different_sessions(self, engine):
        """Concurrent signal inserts for different sessions must not deadlock."""
        from sqlalchemy.orm import sessionmaker
        from app.db.models import Session as SessionModel, Signal
        SessionFactory = sessionmaker(bind=engine)

        errors = []

        def insert_signals(session_id: uuid.UUID):
            db = SessionFactory()
            try:
                s = SessionModel(id=session_id, status="processing", provider="ollama", filename="t.txt")
                db.add(s)
                db.commit()
                for i in range(5):
                    db.add(Signal(
                        session_id=session_id, signal_name=f"sig_{i}",
                        value="large", confidence=0.9, source_text="test", page_number=1,
                    ))
                db.commit()
            except Exception as e:
                errors.append(str(e))
            finally:
                db.close()

        threads = [threading.Thread(target=insert_signals, args=(uuid.uuid4(),)) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        assert not errors, f"Concurrent insert errors: {errors}"

    def test_concurrent_project_creation_same_user(self, engine):
        """Concurrent project creation for same user should not deadlock."""
        from sqlalchemy.orm import sessionmaker
        from app.db.models import Project
        SessionFactory = sessionmaker(bind=engine)
        errors = []

        def create_project(name: str):
            db = SessionFactory()
            try:
                p = Project(
                    id=uuid.uuid4(),
                    user_id="concurrent_test_user",
                    name=name,
                    status="empty",
                )
                db.add(p)
                db.commit()
            except Exception as e:
                errors.append(str(e))
            finally:
                db.close()

        threads = [threading.Thread(target=create_project, args=(f"Concurrent Project {i}",))
                   for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        # Expect no errors — only duplicate name errors are valid
        non_dup_errors = [e for e in errors if "unique" not in e.lower()]
        assert not non_dup_errors, f"Unexpected errors: {non_dup_errors}"
