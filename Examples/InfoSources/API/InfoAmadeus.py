"""
.. module:: InfoAmadeus

InfoAmadeus
******

:Description: InfoAmadeus

    Consulta a Amadeus mediante la libreria amadeus

https://github.com/amadeus4dev/amadeus-python

Demo que hace una consulta simple a Amadeus de un vuelo Barcelona a Paris, hoteles en Londres y Actividades en Barcelona
Consultar la web de la libreria para mas tipos de queries e informacion

Para usarla hay que darse de alta en el site de desarrolladores de Amadeus y crear una API para obtener una Key de acceso
https://developers.amadeus.com/

Se ha de crear un fichero python APIKeys.py que contenga la información para el
acceso a Amadeis (AMADEUS_KEY, AMADEUS_SECRET)

:Authors:
    bejar

:Version: 

:Date:  02/02/2021
"""
from amadeus import Client, ResponseError
#from AgentUtil.APIKeys import AMADEUS_KEY, AMADEUS_SECRET
from pprint import PrettyPrinter

__author__ = 'bejar'

def convertir_duracion_a_minutos(duracion):
    # Eliminar los caracteres no numéricos
    duracion = duracion.replace("PT", "").replace("H", "H ").replace("M", "M ").strip()

    # Dividir la cadena en horas y minutos
    partes = duracion.split(" ")
    horas = 0
    minutos = 0

    for parte in partes:
        if parte.endswith("H"):
            horas = int(parte[:-1])
        elif parte.endswith("M"):
            minutos = int(parte[:-1])

    # Calcular la duración total en minutos
    duracion_minutos = horas * 60 + minutos

    return duracion_minutos


if __name__ == '__main__':
    amadeus = Client(
        client_id="UeGdPNT4DX36I6qWE4YXMgFS6B5kpMiJ",
        client_secret="jR7XMBRxKFvT2FIS"
    )
    ppr = PrettyPrinter(indent=4)

    # Flights query
    try:
        response = amadeus.shopping.flight_offers_search.get(
            originLocationCode='BCN',
            destinationLocationCode='PAR',
            departureDate='2023-05-28',
            adults=1)
        print("FLIGHTS")
        print("-----------------------------------")
        #ppr.pprint(response.data[0])


        flight_data_ordenado_por_duracion = sorted(response.data, key=lambda x: convertir_duracion_a_minutos(x['itineraries'][0]['duration']))

        for flight_data in flight_data_ordenado_por_duracion:
            # Obtener información del precio
            price_total = flight_data['price']['total']

            # Obtener información de los itinerarios
            itineraries = flight_data['itineraries']
            departure_date = itineraries[0]['segments'][0]['departure']['at']
            arrival_date = itineraries[0]['segments'][-1]['arrival']['at']
            duration = itineraries[0]['duration']

            # Obtener identificador del vuelo
            flight_id = flight_data['id']

            # Imprimir la información
            print("Precio total: ", price_total)
            print("Fecha de salida: ", departure_date)
            print("Fecha de llegada: ", arrival_date)
            print("Duración: ", convertir_duracion_a_minutos(duration))
            print("Identificador del vuelo: ", flight_id)
            print("-----------------------------------")
    except ResponseError as error:
        print(error)





