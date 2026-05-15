from django.shortcuts import render


def privacy_policy_view(request):
    return render(request, "frontend/privacy_policy.html")

def personal_data_consent_view(request):
    return render(request, "frontend/personal_data_consent.html")
