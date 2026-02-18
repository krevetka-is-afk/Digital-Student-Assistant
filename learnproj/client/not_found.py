import requests

endpoint = "http://localhost:8001/base/products/1323243204324224/"

get_response = requests.get(endpoint)
print(get_response.json())
