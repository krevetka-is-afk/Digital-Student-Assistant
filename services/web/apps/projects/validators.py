from rest_framework import serializers
from rest_framework.validators import UniqueValidator

from .models import Project

# def validate_title(value):
#     qs = Project.objects.filter(title__iexact=value) # title__exact
#     if qs.exists():
#         raise serializers.ValidationError(f"{value} is already a project name.")
#     return value


def validate_title_no_hello(value):
    if "hello" in value.lower():
        raise serializers.ValidationError(f"{value} is not allowed.")
    return value


unique_project_title = UniqueValidator(queryset=Project.objects.all(), lookup="iexact")
