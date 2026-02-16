import requests

# endpoint = "https://httpbin.org/anything"
endpoint = "http://localhost:8001/base/"

get_response = requests.post(
    endpoint,
    params={"abc": 123},
    json={"title": "ABC123", "content": "Hello, World!", "price": "abc123"},
)
print(get_response.json())
print(get_response.status_code)
