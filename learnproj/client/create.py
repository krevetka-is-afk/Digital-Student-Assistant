import requests

endpoint = "http://localhost:8001/base/products/"

headers = {"Authorization": "Bearer 3e236df4bd5474938b488fea98a946107f4e5b68"}

data = {
    "title": "field from Create",
    "price": 32.99,
}

get_response = requests.post(endpoint, data=data, headers=headers)
print(get_response.json())
