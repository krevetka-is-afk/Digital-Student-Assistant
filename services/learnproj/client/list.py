from getpass import getpass

import requests

auth_endpoint = "http://localhost:8001/base/auth/"
username = input("What is ur username?\n")
password = getpass("What is ur password?\n")

auth_response = requests.post(auth_endpoint, json={"username": username, "password": password})
print(auth_response.json())


if auth_response.status_code == 200:
    token = auth_response.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}
    endpoint = "http://localhost:8001/base/products/"

    get_response = requests.get(endpoint, headers=headers)
    print(get_response.json())
