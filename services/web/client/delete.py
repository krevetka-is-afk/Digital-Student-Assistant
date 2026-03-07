import requests

project_id = input("what is the project ID u want to use?\n")
try:
    project_id = int(project_id)
except BaseException:
    print(f"{project_id} not a valid ID")
    project_id = None

if project_id:
    endpoint = f"http://localhost:8001/base/projects/{project_id}/delete/"

    get_response = requests.delete(endpoint)
    print(get_response.status_code, get_response.status_code == 204)
