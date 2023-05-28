# -*- coding: utf-8 -*-
"""
Created on Fri Dec 27 15:58:13 2013

Consulta a Foursquare mediante el modulo foursquare

https://github.com/mLewisLogic/foursquare

Demo que hace una consulta a FourSquare con unas coordenadas dentro de Barcelona
en un area de 4Km a la redonda buscando museos

Se ha de crear un fichero python APIKeys.py que contenga la información para el
acceso a FourSquare (FQCLIENT_ID, FQCLIENT_SECRET)

@author: javier
"""
import json

import requests
__author__ = 'javier'

import foursquare
#from AgentUtil.APIKeys import FQCLIENT_ID, FQCLIENT_SECRET


#CLIENT_ID = FQCLIENT_ID
#CLIENT_SECRET = FQCLIENT_SECRET

# Se conecta a FQ con la información de acceso
if __name__ == '__main__':
    url = "https://api.foursquare.com/v3/places/search?query=cultura&ll=41.3851%2C2.1734&radius=5000"

    headers = {
        "accept": "application/json",
        "Authorization": "fsq3NP3orIfjrH0u3ku9BYlb+AThGV7nKvM4EXO3PjKxXWM="
    }

    response = requests.get(url, headers=headers)
    data = response.json()  # Obtener el contenido JSON de la respuesta


    for result in data["results"]:
        name = result["name"]
        fsq_id = result["fsq_id"]
        print("Name:", name)
        print("fsq_id:", fsq_id)
        print("---")
