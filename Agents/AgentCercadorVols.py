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
from flask import Flask, render_template, request
from rdflib import XSD, Namespace, Literal, URIRef, Graph
from AgentUtil.FlaskServer import shutdown_server
from AgentUtil.Agent import Agent
from AgentUtil.ACLMessages import *

import logging
import argparse

from rdflib.namespace import FOAF, RDF
from AgentUtil.ACL import ACL
from AgentUtil.DSO import DSO
from AgentUtil.ONTO import ONTO
from AgentUtil.ACLMessages import build_message, send_message
from AgentUtil.Logging import config_logger
from AgentUtil.Util import gethostname
from AgentUtil.APIKeys import AMADEUS_KEY, AMADEUS_SECRET


amadeus = Client(
        client_id=AMADEUS_KEY,
        client_secret=AMADEUS_SECRET
    )

__author__ = 'agracia'


if True:
    # Definimos los parametros de la linea de comandos
    parser = argparse.ArgumentParser()
    parser.add_argument('--open', help="Define si el servidor esta abierto al exterior o no", action='store_true',
                        default=False)
    parser.add_argument('--verbose', help="Genera un log de la comunicacion del servidor web", action='store_true',
                            default=False)
    parser.add_argument('--port', type=int, help="Puerto de comunicacion del agente")
    parser.add_argument('--dhost', help="Host del agente de directorio")
    parser.add_argument('--dport', type=int, help="Puerto de comunicacion del agente de directorio")

    # Logging
    logger = config_logger(level=1)

    # parsing de los parametros de la linea de comandos
    args = parser.parse_args()

    # Configuration stuff
    if args.port is None:
        port = 9012
    else:
        port = args.port

    if args.open:
        hostname = '0.0.0.0'
        hostaddr = gethostname()
    else:
        hostaddr = hostname = socket.gethostname()

    print('Informer Hostname =', hostname)
    print('Informer Hostaddres =', hostaddr)
    print('Informer Port =', port)

    if args.dport is None:
        dport = 9000
    else:
        dport = args.dport

    if args.dhost is None:
        dhostname = socket.gethostname()
    else:
        dhostname = args.dhost

    # Flask stuff
    app = Flask(__name__)
    if not args.verbose:
        log = logging.getLogger('werkzeug')
        log.setLevel(logging.ERROR)
        
        
    agn = Namespace("http://www.agentes.org#")
    onto = Namespace("http://www.owl-ontologies.com/OntologiaECSDI.owl#")

    # Contador de mensajes
    mss_cnt = 0

# Datos del Agente
FlightsAgent = Agent('FlightsAgent',
                       agn.FlightsAgent,
                       'http://%s:%d/comm' % (hostaddr, port),
                       'http://%s:%d/Stop' % (hostaddr, port))

# Directory agent address
DirectoryAgent = Agent('DirectoryAgent',
                    agn.Directory,
                    'http://%s:%d/Register' % (dhostname, dport),
                    'http://%s:%d/Stop' % (dhostname, dport))

# Global triplestore graph
dsgraph = Graph()

# Queue that waits for a 0 to end the agent
endQueue = Queue()

cola1 = Queue()

def get_count():
    global mss_cnt
    mss_cnt += 1
    return mss_cnt

def register_message():
    """
    Envia un mensaje de registro al servicio de registro
    usando una performativa Request y una accion Register del
    servicio de directorio

    :param gmess:
    :return:
    """

    logger.info('Register the Agent')

    global mss_cnt

    gmess = Graph()

    # Build the register message
    gmess.bind('foaf', FOAF)
    gmess.bind('dso', DSO)
    
    
    reg_obj = agn[FlightsAgent.name + '-Register']
    gmess.add((reg_obj, RDF.type, DSO.Register))
    gmess.add((reg_obj, DSO.Uri, FlightsAgent.uri))
    gmess.add((reg_obj, FOAF.name, Literal(FlightsAgent.name)))
    gmess.add((reg_obj, DSO.Address, Literal(FlightsAgent.address)))
    gmess.add((reg_obj, DSO.AgentType, DSO.FlightsAgent))

    # Lo metemos en un envoltorio FIPA-ACL y lo enviamos
    gr = send_message(
        build_message(gmess, perf=ACL.request,
                      sender=FlightsAgent.uri,
                      receiver=DirectoryAgent.uri,
                      content=reg_obj,
                      msgcnt=mss_cnt),
        DirectoryAgent.address)
    mss_cnt += 1

    return gr

@app.route("/comm")
def comunicacion():
    """
    Entrypoint de comunicacion
    """

    print('Peticion de informacion recibida')

    global dsgraph
    message = request.args['content']
    gm = Graph()
    gm.parse(data=message, format='xml')
    msgdic = get_message_properties(gm)
    
    gr = None

    if msgdic is None:
        # Si no es, respondemos que no hemos entendido el mensaje
        print('Mensaje no entendido')
        gr = build_message(Graph(), ACL['not-understood'], sender=FlightsAgent.uri, msgcnt=get_count())


    else:
        # Get the performative
        if msgdic['performative'] != ACL.request:
            print('Mensaje no es request')
            # Is is not request return not understood
            gr = build_message(Graph(),
                               ACL['not-understood'],
                               sender=FlightsAgent.uri,
                               msgcnt=get_count())

        else:
            # Get the action of the request
            content = msgdic['content']
            # Averiguamos el tipo de la accion
            accion = gm.value(subject=content, predicate=RDF.type)

            # Trip Request
            if accion == ONTO.FlightRequest:
                logger.info("Flights request recived")
                
                messageGraph = resolve_request(gm)
                
                gr = build_message(messageGraph,
                                   ACL['inform'],
                                   sender=FlightsAgent.uri,
                                   msgcnt=get_count())    
            else:
                print('Accio no reconeguda')
                gr = build_message(Graph(),
                                   ACL['not-understood'],
                                   sender=FlightsAgent.uri,
                                   msgcnt=get_count())         

    return gr.serialize(format='xml'), 200


def resolve_request(flightRequestGraph: Graph):
    """
    Given the request graph, extracts the information and makes the request
    """
    msgdic = get_message_properties(flightRequestGraph)
    content = msgdic['content']
    
    # Get the date and the max price
    date = flightRequestGraph.value(subject=content, predicate=ONTO.date)
    max_price = flightRequestGraph.value(subject=content, predicate=ONTO.maxPrice)
    
    # Get the origin and the destination
    origin = None
    destination = None
    for city in flightRequestGraph.subjects(RDF.type, ONTO.City):
        if (content, ONTO.origin, city) in flightRequestGraph:
            origin = flightRequestGraph.value(city, ONTO.name)
        if (content, ONTO.destination, city) in flightRequestGraph:
            destination = flightRequestGraph.value(city, ONTO.name)
    
    return search_flights(origin=origin, destination=destination, date=date, maxPrice=max_price, minPrice=1)
    

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

def search_flights(origin=None, destination=None, minPrice=1, maxPrice=sys.float_info.max, date=None):

        print ("orig: " + origin)
        print("dest: " + destination)
        print("precio min: " + str(minPrice))
        print("precio max: " + str(maxPrice))
        print("Fecha salida: " + date)

        response = amadeus.shopping.flight_offers_search.get(
            originLocationCode=origin,
            destinationLocationCode=destination,
            departureDate=date,
            adults=1)
        print("FLIGHTS")
        print("-----------------------------------")

        flight_data_ordenado_por_duracion = [flight_data for flight_data in response.data
                            if float(flight_data['price']['total']) >= minPrice and
                            float(flight_data['price']['total']) <= maxPrice]



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
            date = itineraries[0]['segments'][0]['departure']['at']
            fecha_llegada = itineraries[0]['segments'][-1]['arrival']['at']
            duracion_vuelo = convertir_duracion_a_minutos(itineraries[0]['duration'])
            # Obtener identificador del vuelo
            id_vuelo = flight_data['id']
            subject_vuelo = onto["Flight_", id_vuelo] 

            print("--- Vuelo ---")
            print("ID:", id_vuelo)
            print("Fecha llegada:", fecha_llegada)
            print("Fecha Salida:", date)
            print("Precio:", precio_vuelo)
            print("Duracion:", duracion_vuelo)
            print("---------------------")
            result.add((subject_vuelo, RDF.type, ONTO.Flight))
            result.add((subject_vuelo, ONTO.price, Literal(precio_vuelo, datatype=XSD.float)))
            result.add((subject_vuelo, ONTO.id, Literal(id_vuelo, datatype=XSD.string)))
            result.add((subject_vuelo, ONTO.start, Literal(date, datatype=XSD.string)))
            result.add((subject_vuelo, ONTO.end, Literal(fecha_llegada, datatype=XSD.string)))
            result.add((subject_vuelo, ONTO.duration, Literal(duracion_vuelo, datatype=XSD.float)))

        return result

# --------------- Functions to keep the server runing ---------------
@app.route("/stop")
def stop():
    """
    Entrypoint to stop the agent

    :return:
    """
    tidyup()
    shutdown_server()
    return "Server Stoped"

def tidyup():
    """
    Actions before stop the server

    """
    global endQueue
    endQueue.put(0)

def startAndWait(endQueue):
    """
    Starts the Agent and Waits for it to Stops
    
    :return:
    """
    # Register the Agent
    regResponseGraph = register_message()

    # Wait until the 0 arrives to End
    end = False
    while not end:
        while endQueue.empty():
            pass
        endSignal = endQueue.get()
        if endSignal == 0:
            end = True
        else:
            print(endSignal)

if __name__ == '__main__':
    # Start the first behavior to register and wait
    init = Process(target=startAndWait, args=(endQueue,))
    init.start()

    # Starts the server
    app.run(host=hostname, port=port, debug=True)

    # Wait unitl the behaviors ends
    init.join()
    logger.info('The End')
