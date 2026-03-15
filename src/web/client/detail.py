import requests

endpoint = "http://localhost:8001/base/projects/1/"

get_response = requests.get(endpoint)
print(get_response.json())
