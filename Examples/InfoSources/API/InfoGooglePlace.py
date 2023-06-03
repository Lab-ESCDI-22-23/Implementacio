"AIzaSyBX1DSnnWxD6s-t9_YzjtpbrPbPYcXJxoA"
import json

from googleplaces import GooglePlaces

if __name__ == '__main__':

    import requests

    urls = [
        "https://maps.googleapis.com/maps/api/place/textsearch/json?query=museos%20en%20"+ "Paris" +"&key=AIzaSyBX1DSnnWxD6s-t9_YzjtpbrPbPYcXJxoA",
    ]

    results = []

    for i, url in enumerate(urls):
        response = requests.get(url)
        data = response.json()

        for item in data.get("results", []):
            name = item.get("name")
            price_level = item.get("price_level")
            result = {"name": name, "price_level": price_level, "type": f"Consulta {i + 1}"}
            results.append(result)

            print("Nombre:", name)
            print("Price level:", price_level)
            print("Type:", f"Consulta {i + 1}")
            print("---------------")

