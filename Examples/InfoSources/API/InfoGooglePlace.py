"AIzaSyBX1DSnnWxD6s-t9_YzjtpbrPbPYcXJxoA"
import json

from googleplaces import GooglePlaces

if __name__ == '__main__':

    import requests

    url = "https://maps.googleapis.com/maps/api/place/textsearch/json?query=discoteca%20en%20Barcelona&key=AIzaSyBX1DSnnWxD6s-t9_YzjtpbrPbPYcXJxoA"

    payload = {}
    headers = {}

    response = requests.request("GET", url, headers=headers, data=payload)

    data = response.json()

    # Obtener los valores importantes
    results = data['results']  # Acceder a la lista de resultados

    for item in results:
        # Obtener los valores importantes de cada objeto
        price_level = item.get('price_level', 'N/A')  # Usar get() para manejar claves no encontradas
        name = item.get('name', 'N/A')

        # Imprimir los valores
        print("Price Level:", price_level)
        print("Name:", name)
        print("-----")  # Separador entre objetos

