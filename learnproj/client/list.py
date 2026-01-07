import requests

endpoint = "http://localhost:8001/base/products/"

get_response = requests.get(endpoint)
print(get_response.json())
