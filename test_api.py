import requests
import json

BASE_URL = "http://localhost:8000"

def test_endpoint(method, path, data=None):
    url = f"{BASE_URL}{path}"
    print(f"Testing {method} {url}...")
    
    try:
        if method == "GET":
            response = requests.get(url)
        elif method == "POST":
            response = requests.post(url, json=data)
        elif method == "PUT":
            response = requests.put(url, json=data)
            
        print(f"Status Code: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2, ensure_ascii=False)}")
        print("-" * 30)
    except Exception as e:
        print(f"Erreur : Assurez-vous que le serveur tourne (python main.py)\n{e}")

if __name__ == "__main__":
    # 1. Tester la racine
    test_endpoint("GET", "/")

    # 2. Tester la lecture du module Ventes
    test_endpoint("GET", "/sales/")

    # 3. Tester la création d'un événement
    test_endpoint("POST", "/events/", {"data": {"nom": "Conférence Capsy", "date": "2024-10-12"}})

    # 4. Tester la modification des paramètres
    test_endpoint("PUT", "/settings/1", {"data": {"theme": "dark", "notifications": True}})
