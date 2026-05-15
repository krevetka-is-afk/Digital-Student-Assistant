from uuid import uuid4

import pytest
from apps.users.models import ExternalAccessRequest, UserProfile, UserRole
from django.contrib.auth import get_user_model
from django.test import Client
from django.urls import reverse

User = get_user_model()

pytestmark = pytest.mark.django_db


def _uid():
    return uuid4().hex[:8]


def _make_student(*, email=None, password="pass"):
    uid = _uid()
    user = User.objects.create_user(
        username=f"stu-{uid}",
        email=email or f"stu-{uid}@edu.hse.ru",
        password=password,
        is_active=True,
    )
    UserProfile.objects.create(user=user, role=UserRole.STUDENT)
    return user


def _register_payload(**overrides):
    uid = _uid()
    payload = {
        "tab": "register",
        "email": f"valid-{uid}@edu.hse.ru",
        "password": "ValidPass1!",
        "password2": "ValidPass1!",
        "role": UserRole.STUDENT,
        "personal_data_consent": "1",
    }
    payload.update(overrides)
    return payload


def test_auth_get_renders_for_anonymous():
    response = Client().get(reverse("frontend:auth"))
    assert response.status_code == 200


def test_auth_get_redirects_authenticated_to_project_list():
    student = _make_student()
    client = Client()
    client.force_login(student)
    response = client.get(reverse("frontend:auth"))
    assert response.status_code == 302
    assert response["Location"] == reverse("frontend:project_list")


def test_login_success_redirects_to_project_list():
    uid = _uid()
    email = f"ok-{uid}@edu.hse.ru"
    _make_student(email=email, password="GoodPass1!")
    client = Client()
    response = client.post(
        reverse("frontend:auth"),
        {"tab": "login", "email": email, "password": "GoodPass1!"},
    )
    assert response.status_code == 302
    assert response["Location"] == reverse("frontend:project_list")


def test_login_wrong_password_rerenders_form():
    uid = _uid()
    email = f"err-{uid}@edu.hse.ru"
    _make_student(email=email, password="CorrectPass1!")
    client = Client()
    response = client.post(
        reverse("frontend:auth"),
        {"tab": "login", "email": email, "password": "wrong"},
    )
    assert response.status_code == 200
    assert response.context["login_form"].errors


def test_login_rejects_invalid_email_format():
    response = Client().post(
        reverse("frontend:auth"),
        {"tab": "login", "email": "notanemail", "password": "anything"},
    )
    assert response.status_code == 200
    assert "Enter a valid email address" in response.content.decode()


def test_auth_login_ignores_external_next_redirect():
    uid = _uid()
    email = f"sec-{uid}@edu.hse.ru"
    _make_student(email=email, password="SafePass1!")
    user = User.objects.get(email=email)
    client = Client()

    response = client.post(
        f"{reverse('frontend:auth')}?next=https://evil.example/phish",
        data={
            "tab": "login",
            "email": user.email,
            "password": "SafePass1!",
            "next": "https://evil.example/phish",
        },
    )

    assert response.status_code == 302
    assert response["Location"] == reverse("frontend:project_list")


def test_register_rejects_invalid_email():
    response = Client().post(
        reverse("frontend:auth"),
        _register_payload(email="sdfsdf"),
    )
    assert response.status_code == 200
    assert "Enter a valid email address" in response.content.decode()
    assert not User.objects.filter(email="sdfsdf").exists()


def test_register_rejects_email_missing_domain():
    response = Client().post(
        reverse("frontend:auth"),
        _register_payload(email="user@"),
    )
    assert response.status_code == 200
    assert "Enter a valid email address" in response.content.decode()


def test_register_accepts_valid_email():
    uid = _uid()
    email = f"valid-{uid}@edu.hse.ru"
    response = Client().post(reverse("frontend:auth"), _register_payload(email=email))
    assert response.status_code == 302
    assert User.objects.filter(email=email).exists()


def test_register_rejects_short_password():
    response = Client().post(
        reverse("frontend:auth"),
        _register_payload(password="short", password2="short"),
    )
    assert response.status_code == 200
    assert "Password is too short" in response.content.decode()


def test_register_rejects_duplicate_email():
    uid = _uid()
    email = f"dup-{uid}@edu.hse.ru"
    User.objects.create_user(username=f"existing-{uid}", email=email, password="SomePass1!")
    response = Client().post(reverse("frontend:auth"), _register_payload(email=email))
    assert response.status_code == 200
    assert "A user with this email already exists" in response.content.decode()


def test_register_mismatched_passwords():
    response = Client().post(
        reverse("frontend:auth"),
        _register_payload(password="ValidPass1!", password2="Different1!"),
    )
    assert response.status_code == 200
    assert "Passwords do not match" in response.content.decode()
    assert not User.objects.filter(email=_register_payload()["email"]).exists()


def test_register_without_consent():
    uid = _uid()
    response = Client().post(
        reverse("frontend:auth"),
        _register_payload(email=f"noconsent-{uid}@edu.hse.ru", personal_data_consent=""),
    )
    assert response.status_code == 200
    assert not User.objects.filter(email=f"noconsent-{uid}@edu.hse.ru").exists()


def test_register_external_customer_creates_access_request():
    uid = _uid()
    external_email = f"external-{uid}@gmail.com"
    response = Client().post(
        reverse("frontend:auth"),
        _register_payload(email=external_email, role=UserRole.CUSTOMER),
    )
    assert response.status_code == 302
    assert not User.objects.filter(email=external_email).exists()
    assert ExternalAccessRequest.objects.filter(email=external_email).exists()


def test_logout_redirects_to_auth():
    student = _make_student()
    client = Client()
    client.force_login(student)
    response = client.post(reverse("frontend:logout"))
    assert response.status_code == 302
    assert "/auth/" in response["Location"]


def test_logout_ends_session():
    student = _make_student()
    client = Client()
    client.force_login(student)
    client.post(reverse("frontend:logout"))
    response = client.get(reverse("frontend:project_list"))
    assert response.status_code == 302
    assert "/auth/" in response["Location"]
