from apps.applications.models import Application


def test_application_unique_constraint_declared():
    unique_constraints = [
        constraint
        for constraint in Application._meta.constraints
        if getattr(constraint, "name", None) == "applications_unique_project_applicant"
    ]
    assert len(unique_constraints) == 1
    assert tuple(unique_constraints[0].fields) == ("project", "applicant")
