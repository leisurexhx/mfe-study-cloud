from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy.orm import Session, sessionmaker

from mfe_study_cloud.db.models import Document
from mfe_study_cloud.db.repositories import TenantPrincipal
from mfe_study_cloud.services.auth import AuthService
from mfe_study_cloud.services.errors import (
    AuthenticationError,
    ConflictError,
    NotFoundError,
)
from mfe_study_cloud.services.study import StudyService
from mfe_study_cloud.storage import InMemoryObjectStore

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "anonymous-demo.pdf"


def _services(
    sessions: sessionmaker[Session],
) -> tuple[AuthService, StudyService, InMemoryObjectStore]:
    objects = InMemoryObjectStore()
    return (
        AuthService(sessions),
        StudyService(
            sessions,
            objects,
            max_upload_bytes=1_000_000,
            max_document_pages=10,
        ),
        objects,
    )


def test_registration_authentication_and_duplicate_email(
    sessions: sessionmaker[Session],
) -> None:
    auth, _, _ = _services(sessions)
    registered = auth.register(
        email="OWNER@example.test",
        display_name="Owner",
        password="correct horse battery staple",
    )

    authenticated = auth.authenticate(
        email="owner@example.test",
        password="correct horse battery staple",
    )
    assert authenticated == registered
    assert auth.resolve_principal(
        user_id=registered.user_id,
        tenant_id=registered.tenant_id,
    ) == registered

    with pytest.raises(AuthenticationError):
        auth.authenticate(email="owner@example.test", password="wrong password")
    with pytest.raises(ConflictError):
        auth.register(
            email="owner@example.test",
            display_name="Another",
            password="another valid password",
        )


def test_tenants_cannot_read_or_attach_to_each_others_records(
    sessions: sessionmaker[Session],
) -> None:
    auth, study, objects = _services(sessions)
    alice = auth.register(
        email="alice@example.test", display_name="Alice", password="alice secure password"
    )
    bob = auth.register(
        email="bob@example.test", display_name="Bob", password="bob secure password"
    )
    alice_course = study.create_course(alice, code="MFE-101", name="Market Foundations")
    alice_chapter = study.create_chapter(
        alice,
        course_id=alice_course.id,
        number="1",
        title="Anonymous inputs",
    )
    alice_document = study.upload_document(
        alice,
        course_id=alice_course.id,
        chapter_id=alice_chapter.id,
        filename="../../private-name.pdf",
        data=FIXTURE.read_bytes(),
    )

    assert study.list_courses(alice)[0].id == alice_course.id
    assert study.list_courses(bob) == []
    assert alice_document.original_filename == "private-name.pdf"
    assert str(alice.tenant_id) in alice_document.object_key
    assert alice_document.object_key in objects.objects

    with pytest.raises(NotFoundError):
        study.document_bytes(bob, alice_document.id)
    with pytest.raises(NotFoundError):
        study.create_chapter(
            bob,
            course_id=alice_course.id,
            number="stolen",
            title="Cross-tenant attempt",
        )
    with pytest.raises(NotFoundError):
        study.add_note(
            bob,
            course_id=alice_course.id,
            document_id=alice_document.id,
            content="Must not attach",
        )


def test_same_pdf_is_deduplicated_per_tenant_not_globally(
    sessions: sessionmaker[Session],
) -> None:
    auth, study, objects = _services(sessions)
    first = auth.register(
        email="first@example.test", display_name="First", password="first secure password"
    )
    second = auth.register(
        email="second@example.test", display_name="Second", password="second secure password"
    )
    raw = FIXTURE.read_bytes()

    def upload_for(principal: TenantPrincipal, code: str) -> Document:
        course = study.create_course(principal, code=code, name=code)
        chapter = study.create_chapter(
            principal, course_id=course.id, number="1", title="Chapter"
        )
        return study.upload_document(
            principal,
            course_id=course.id,
            chapter_id=chapter.id,
            filename="demo.pdf",
            data=raw,
        )

    first_document = upload_for(first, "FIRST")
    second_document = upload_for(second, "SECOND")
    assert first_document.object_key != second_document.object_key
    assert len(objects.objects) == 2

    with pytest.raises(ConflictError):
        first_course = study.list_courses(first)[0]
        first_chapter = study.create_chapter(
            first,
            course_id=first_course.id,
            number="2",
            title="Duplicate target",
        )
        study.upload_document(
            first,
            course_id=first_course.id,
            chapter_id=first_chapter.id,
            filename="duplicate.pdf",
            data=raw,
        )


def test_notes_search_and_progress_remain_tenant_scoped(
    sessions: sessionmaker[Session],
) -> None:
    auth, study, _ = _services(sessions)
    alice = auth.register(
        email="reader-a@example.test", display_name="Reader A", password="reader a password"
    )
    bob = auth.register(
        email="reader-b@example.test", display_name="Reader B", password="reader b password"
    )
    course = study.create_course(alice, code="SEARCH", name="Search")
    chapter = study.create_chapter(alice, course_id=course.id, number="1", title="One")
    document = study.upload_document(
        alice,
        course_id=course.id,
        chapter_id=chapter.id,
        filename="search.pdf",
        data=FIXTURE.read_bytes(),
    )
    study.add_note(
        alice,
        course_id=course.id,
        chapter_id=chapter.id,
        document_id=document.id,
        page_number=2,
        note_type="insight",
        content="tenant-only-duration-insight",
    )

    assert [hit.source for hit in study.search(alice, "duration-insight")] == ["note"]
    assert study.search(bob, "duration-insight") == []
    progress = study.update_progress(
        alice, document_id=document.id, page_number=2, seconds_delta=65
    )
    assert progress.last_page == 2
    assert progress.is_completed is True
    assert progress.total_seconds == 65
    with pytest.raises(NotFoundError):
        study.update_progress(bob, document_id=document.id, page_number=1)
