# -*- coding: utf-8 -*-
"""
Created on Fri Dec 27 15:58:13 2013

Esqueleto de agente usando los servicios web de Flask

/comm es la entrada para la recepcion de mensajes del agente
/Stop es la entrada que para el agente

Tiene una funcion AgentBehavior1 que se lanza como un thread concurrente

Asume que el agente de registro esta en el puerto 9000

@author: javier
"""
from amadeus import Client, ResponseError
import sys
from multiprocessing import Process, Queue
import socket
from flask import Flask, request
from rdflib import Namespace, Graph
from pyparsing import Literal
from AgentUtil.FlaskServer import shutdown_server
from AgentUtil.Agent import Agent
from AgentUtil.OntoNamespaces import ONTO
from Implementacio.Examples.AgentExamples.AgentUtil.ACLMessages import *


from multiprocessing import Process
import logging
import argparse

from flask import Flask, render_template, request
from rdflib import Graph, Namespace
from rdflib.namespace import FOAF, RDF
from rdflib import XSD, Namespace, Literal, URIRef
from AgentUtil.ACL import ACL
from AgentUtil.DSO import DSO
from AgentUtil.FlaskServer import shutdown_server
from AgentUtil.ACLMessages import build_message, send_message
from AgentUtil.Agent import Agent
from AgentUtil.Logging import config_logger
from AgentUtil.Util import gethostname
from AgentUtil.APIKeys import AMADEUS_KEY, AMADEUS_SECRET
import socket


amadeus = Client(
        client_id=AMADEUS_KEY,
        client_secret=AMADEUS_SECRET
    )

__author__ = 'agracia'



# Configuration stuff
hostname = socket.gethostname()
port = 9013

agn = Namespace("http://www.agentes.org#")

# Contador de mensajes
mss_cnt = 0

# Datos del Agente
AgenteActividades = Agent('AgenteVuelos',
                       agn.AgentSimple,
                       'http://%s:%d/comm' % (hostname, port),
                       'http://%s:%d/Stop' % (hostname, port))

# Directory agent address
DirectoryAgent = Agent('DirectoryAgent',
                       agn.Directory,
                       'http://%s:9000/Register' % hostname,
                       'http://%s:9000/Stop' % hostname)

# Global triplestore graph
dsgraph = Graph()

cola1 = Queue()

# Flask stuff
app = Flask(__name__)


def get_count():
    global mss_cnt
    mss_cnt += 1
    return mss_cnt

@app.route("/comm")
def comunicacion():
    """
    Entrypoint de comunicacion
    """

    print('Peticion de informacion recibida')

    global dsgraph
    message = request.args['content']
    print('El mensaje 1')
    gm = Graph()
    print('El mensaje 1.2')
    print(message)
    gm.parse(data=message, format='xml')
    print('El mensaje 2')
    msgdic = get_message_properties(gm)
    gr = None

    if msgdic is None:
        # Si no es, respondemos que no hemos entendido el mensaje
        print('Mensaje no entendido')
        gr = build_message(Graph(), ACL['not-understood'], sender=AgenteVuelos.uri, msgcnt=get_count())


    else:
        # Obtenemos la performativa
        if msgdic['performative'] != ACL.request:
            print('Mensaje no es request')
            # Si no es un request, respondemos que no hemos entendido el mensaje
            gr = build_message(Graph(),
                               ACL['not-understood'],
                               sender=AgenteVuelos.uri,
                               msgcnt=get_count())

        else:
            # Extraemos el objeto del contenido que ha de ser una accion de la ontologia
            # de registro
            print('Mensaje puede ser accion de onto')
            content = msgdic['content']
            # Averiguamos el tipo de la accion
            accion = gm.value(subject=content, predicate=RDF.type)

            # Accion de buscar productos
            if accion == ONTO.BuscarVuelos:
                print("Works here")
                restriccions = gm.objects(content, ONTO.RestringidaPor)
                restriccions_dict = {}
                # Per totes les restriccions que tenim en la cerca d'hotels
                for restriccio in restriccions:
                    if gm.value(subject=restriccio, predicate=RDF.type) == ONTO.RestriccionOrigenDesti:
                        ciutat_origen = gm.value(subject=restriccio, predicate=ONTO.CiudadOrigen)
                        ciutat_desti = gm.value(subject=restriccio, predicate=ONTO.CiudadDestino)
                        print('BÚSQUEDA->Restriccion de origen de vuelo: ' + ciutat_origen)
                        print('BÚSQUEDA->Restriccion de destino de vuelo: ' + ciutat_desti)
                        restriccions_dict['ciutat_origen'] = ciutat_origen
                        restriccions_dict['ciutat_desti'] = ciutat_desti

                    elif gm.value(subject=restriccio, predicate=RDF.type) == ONTO.RestriccionPrecio:
                        preciomax = gm.value(subject=restriccio, predicate=ONTO.PrecioMax)
                        preciomin = gm.value(subject=restriccio, predicate=ONTO.PrecioMin)
                        if preciomin:
                            print('BÚSQUEDA->Restriccion de precio minimo:' + preciomin)
                            restriccions_dict['preciomin'] = preciomin.toPython()
                        if preciomax:
                            print('BÚSQUEDA->Restriccion de precio maximo:' + preciomax)
                            restriccions_dict['preciomax'] = preciomax.toPython()


                    elif gm.value(subject=restriccio, predicate=RDF.type) == ONTO.RestriccionFecha:
                        fecha_salida = gm.value(subject=restriccio, predicate=ONTO.FechaSalida)
                        print('BÚSQUEDA->Restriccion de fecha salida: ' + fecha_salida)
                        restriccions_dict['fecha_salida'] = fecha_salida

                gr = buscar_vuelos(**restriccions_dict)

    return gr.serialize(format='xml'), 200



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

def buscar_vuelos(ciutat_origen=None, ciutat_desti=None, preciomin=sys.float_info.min, preciomax=sys.float_info.max, fecha_salida=None):

        print ("orig: " + ciutat_origen)
        print("dest: " + ciutat_desti)
        print("precio min: " + str(preciomin))
        print("precio max: " + str(preciomax))
        print("Fecha salida: " + fecha_salida)

        response = amadeus.shopping.flight_offers_search.get(
            originLocationCode=ciutat_origen,
            destinationLocationCode=ciutat_desti,
            departureDate=fecha_salida,
            adults=1)
        print("FLIGHTS")
        print("-----------------------------------")

        flight_data_ordenado_por_duracion = [flight_data for flight_data in response.data
                            if float(flight_data['price']['total']) >= preciomin and
                            float(flight_data['price']['total']) <= preciomax]



        result = Graph()
        vuelos_count = 0
        print(len(flight_data_ordenado_por_duracion))

        for flight_data in flight_data_ordenado_por_duracion:
            # Obtener información del precio
            vuelos_count += 1
            print(vuelos_count)
            precio_vuelo = flight_data['price']['total']

            # Obtener información de los itinerarios
            itineraries = flight_data['itineraries']
            fecha_salida = itineraries[0]['segments'][0]['departure']['at']
            fecha_llegada = itineraries[0]['segments'][-1]['arrival']['at']
            duracion_vuelo = convertir_duracion_a_minutos(itineraries[0]['duration'])
            # Obtener identificador del vuelo
            id_vuelo = flight_data['id']
            subject_vuelo = URIRef("http://www.owl-ontologies.com/OntologiaECSDI.owl#Vuelo" + id_vuelo)


            result.add((subject_vuelo, RDF.type, ONTO.Vuelo))
            result.add((subject_vuelo, ONTO.PrecioVuelo, Literal(precio_vuelo, datatype=XSD.float)))
            result.add((subject_vuelo, ONTO.Identificador, Literal(id_vuelo, datatype=XSD.string)))
            result.add((subject_vuelo, ONTO.FechaSalida, Literal(fecha_salida, datatype=XSD.string)))
            result.add((subject_vuelo, ONTO.FechaLlegada, Literal(fecha_llegada, datatype=XSD.string)))
            result.add((subject_vuelo, ONTO.DuracionVuelo, Literal(duracion_vuelo, datatype=XSD.float)))

        return result

@app.route("/Stop")
def stop():
    """
    Entrypoint que para el agente

    :return:
    """
    tidyup()
    shutdown_server()
    return "Parando Servidor"


def tidyup():
    """
    Acciones previas a parar el agente

    """
    pass


def agentbehavior1(cola):
    """
    Un comportamiento del agente

    :return:
    """

    #buscar_vuelos("BCN", "LON", 100, 150, "2023-05-28")
    pass


if __name__ == '__main__':
    # Ponemos en marcha los behaviors
    ab1 = Process(target=agentbehavior1, args=(cola1,))
    ab1.start()

    # Ponemos en marcha el servidor
    app.run(host=hostname, port=port)

    # Esperamos a que acaben los behaviors
    ab1.join()
    print('The End')
