import requests

# endpoint = "https://httpbin.org/anything"
endpoint = "http://localhost:8001/base/"

get_response = requests.get(endpoint, params={"abc": 123}, json={"query": "Hello, World!"})
print(get_response.json())
print(get_response.status_code)
