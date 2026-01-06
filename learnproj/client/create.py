import requests

endpoint = "http://localhost:8001/base/products/"

data = {
    "title": "field from Create",
    "price": 32.99,
}

get_response = requests.post(endpoint, data=data)
print(get_response.json())
