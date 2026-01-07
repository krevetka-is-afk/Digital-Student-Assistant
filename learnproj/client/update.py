import requests

endpoint = "http://localhost:8001/base/products/1/update/"

data = {"title": "Hello world my old friend", "price": 9999.99}

get_response = requests.put(endpoint, json=data)
print(get_response.json())
