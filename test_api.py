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

    # 2. Tester l'authentification /login
    import os
    from dotenv import load_dotenv
    load_dotenv()
    
    odoo_user = os.getenv("ODOO_USERNAME")
    odoo_password = os.getenv("ODOO_PASSWORD")
    odoo_db = os.getenv("ODOO_DB")
    odoo_url = os.getenv("ODOO_URL")
    
    if odoo_user and odoo_password:
        print("Test de la connexion avec les identifiants du fichier .env...")
        test_endpoint("POST", "/login", {
            "username": odoo_user,
            "password": odoo_password,
            "db": odoo_db,
            "url": odoo_url
        })
    else:
        print("Identifiants .env manquants pour tester l'authentification.")

    # 3. Tester la lecture du module Ventes
    test_endpoint("GET", "/sales/")

    # 4. Tester la création d'un événement
    test_endpoint("POST", "/events/", {"data": {"nom": "Conférence Capsy", "date": "2024-10-12"}})

    # 5. Tester la modification des paramètres
    test_endpoint("PUT", "/settings/1", {"data": {"theme": "dark", "notifications": True}})

