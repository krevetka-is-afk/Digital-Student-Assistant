from typing import Any, cast

from apps.users.email_verification import (
    VERIFICATION_GENERIC_RESEND_MESSAGE,
    pending_email_verification_user_for_credentials,
    resend_signup_code,
    verify_signup_code,
)
from apps.users.models import UserRole
from apps.users.registration import register_user
from django.conf import settings
from django.contrib.auth import authenticate, get_user_model
from drf_spectacular.utils import extend_schema
from rest_framework import serializers, status
from rest_framework.authtoken.models import Token
from rest_framework.authtoken.views import ObtainAuthToken
from rest_framework.response import Response
from rest_framework.views import APIView

User = get_user_model()


class EmailAuthTokenSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(trim_whitespace=False)

    default_error_messages = {
        "invalid_credentials": "Unable to log in with provided credentials.",
    }

    def validate(self, attrs):
        email = attrs.get("email", "").strip().lower()
        password = attrs.get("password")

        user = User.objects.filter(email__iexact=email).first()
        if user is None:
            raise serializers.ValidationError(
                self.error_messages["invalid_credentials"],
                code="authorization",
            )

        authenticated = authenticate(
            request=self.context.get("request"),
            username=user.username,
            password=password,
        )
        if authenticated is None:
            raise serializers.ValidationError(
                self.error_messages["invalid_credentials"],
                code="authorization",
            )

        attrs["user"] = authenticated
        attrs["email"] = email
        return attrs


class EmailAuthTokenResponseSerializer(serializers.Serializer):
    token = serializers.CharField()


class RegisterRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(trim_whitespace=False)
    name = serializers.CharField(required=False, allow_blank=True, default="")
    role = serializers.ChoiceField(choices=[UserRole.STUDENT, UserRole.CUSTOMER])
    personal_data_consent = serializers.BooleanField()


class RegisterResponseSerializer(serializers.Serializer):
    status = serializers.CharField()
    detail = serializers.CharField()
    email = serializers.EmailField()
    username = serializers.CharField(required=False, allow_blank=True)
    role = serializers.ChoiceField(choices=[UserRole.STUDENT, UserRole.CUSTOMER])
    email_verification_required = serializers.BooleanField()


class VerifyEmailRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()
    code = serializers.CharField()


class VerifyEmailResponseSerializer(serializers.Serializer):
    status = serializers.CharField()
    detail = serializers.CharField()
    email = serializers.EmailField()
    username = serializers.CharField()
    role = serializers.CharField()
    email_verified = serializers.BooleanField()


class ResendVerificationRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()


class ResendVerificationResponseSerializer(serializers.Serializer):
    status = serializers.CharField()
    detail = serializers.CharField()
    retry_after_seconds = serializers.IntegerField(required=False, allow_null=True)


class ProviderAwareObtainAuthTokenView(ObtainAuthToken):
    """
    Keep local token issuance available only when local fallback is enabled.
    """

    serializer_class = EmailAuthTokenSerializer

    def post(self, request, *args, **kwargs):
        if not getattr(settings, "AUTH_ENABLE_LOCAL_TOKEN_FALLBACK", True):
            return Response(
                {"detail": "Local token auth is disabled in current auth mode."},
                status=status.HTTP_404_NOT_FOUND,
            )
        return super().post(request, *args, **kwargs)


class VerifiedObtainAuthTokenView(ProviderAwareObtainAuthTokenView):
    @extend_schema(
        tags=["Auth"],
        summary="Получить токен доступа",
        request=EmailAuthTokenSerializer,
        responses={200: EmailAuthTokenResponseSerializer},
    )
    def post(self, request, *args, **kwargs):
        if not getattr(settings, "AUTH_ENABLE_LOCAL_TOKEN_FALLBACK", True):
            return Response(
                {"detail": "Local token auth is disabled in current auth mode."},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = self.serializer_class(
            data=request.data,
            context={"request": request},
        )
        if serializer.is_valid():
            user = serializer.validated_data["user"]
            token_model = cast(Any, Token)
            token, _ = token_model.objects.get_or_create(user=user)
            return Response({"token": token.key})

        identifier = request.data.get("email") or ""
        password = request.data.get("password") or ""
        pending_user = pending_email_verification_user_for_credentials(identifier, password)
        if pending_user is not None:
            return Response(
                {
                    "detail": "Email verification is required before requesting an auth token.",
                    "code": "email_not_verified",
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class RegisterAPIView(APIView):
    permission_classes = []

    @extend_schema(
        tags=["Auth"],
        summary="Зарегистрировать нового пользователя",
        request=RegisterRequestSerializer,
        responses={201: RegisterResponseSerializer, 202: RegisterResponseSerializer},
    )
    def post(self, request):
        serializer = RegisterRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        result = register_user(
            email=serializer.validated_data["email"],
            password=serializer.validated_data["password"],
            full_name=serializer.validated_data.get("name", ""),
            role=serializer.validated_data["role"],
            personal_data_consent=serializer.validated_data["personal_data_consent"],
        )
        if not result.success:
            return Response(result.field_errors, status=status.HTTP_400_BAD_REQUEST)

        payload = {
            "status": result.status,
            "detail": result.message,
            "email": result.normalized_email,
            "username": result.username,
            "role": result.role,
            "email_verification_required": result.status == "verification_sent",
        }
        if result.status == "access_request_created":
            return Response(payload, status=status.HTTP_202_ACCEPTED)
        return Response(payload, status=status.HTTP_201_CREATED)


class VerifyEmailAPIView(APIView):
    permission_classes = []

    @extend_schema(
        tags=["Auth"],
        summary="Подтвердить email кодом",
        request=VerifyEmailRequestSerializer,
        responses={200: VerifyEmailResponseSerializer},
    )
    def post(self, request):
        serializer = VerifyEmailRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        result = verify_signup_code(
            email=serializer.validated_data["email"],
            code=serializer.validated_data["code"],
        )
        if not result.success or result.user is None:
            field_errors: dict[str, list[str]]
            if result.error_code == "missing_fields":
                field_errors = {}
                if not serializer.validated_data.get("email"):
                    field_errors["email"] = ["Введите email."]
                if not serializer.validated_data.get("code"):
                    field_errors["code"] = ["Введите код подтверждения."]
            else:
                field_errors = {"code": [result.message]}
            return Response(field_errors, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            {
                "status": result.reason,
                "detail": result.message,
                "email": result.user.email,
                "username": result.user.username,
                "role": result.user.profile.role,
                "email_verified": True,
            }
        )


class ResendVerificationAPIView(APIView):
    permission_classes = []

    @extend_schema(
        tags=["Auth"],
        summary="Переотправить код подтверждения email",
        request=ResendVerificationRequestSerializer,
        responses={
            200: ResendVerificationResponseSerializer,
            429: ResendVerificationResponseSerializer
            },
    )
    def post(self, request):
        serializer = ResendVerificationRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        result = resend_signup_code(serializer.validated_data["email"])
        payload = {
            "status": result.reason,
            "detail": result.message or VERIFICATION_GENERIC_RESEND_MESSAGE,
        }
        if result.retry_after_seconds is not None:
            payload["retry_after_seconds"] = result.retry_after_seconds
            return Response(payload, status=status.HTTP_429_TOO_MANY_REQUESTS)
        return Response(payload)
