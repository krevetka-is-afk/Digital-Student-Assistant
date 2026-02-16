import requests

product_id = input("what is the product ID u want to use?\n")
try:
    product_id = int(product_id)
except BaseException:
    print(f"{product_id} not a valid ID")
    product_id = None

if product_id:
    endpoint = f"http://localhost:8001/base/products/{product_id}/delete/"

    get_response = requests.delete(endpoint)
    print(get_response.status_code, get_response.status_code == 204)
