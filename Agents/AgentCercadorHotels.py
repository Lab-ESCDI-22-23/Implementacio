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
import sys
from multiprocessing import Process, Queue
import socket
from flask import Flask, request
from rdflib import Namespace, Graph
from pyparsing import Literal
from AgentUtil.FlaskServer import shutdown_server
from AgentUtil.Agent import Agent
from AgentUtil.OntoNamespaces import ONTO
from AgentUtil.ACLMessages import *


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
import socket

__author__ = 'agracia'

FUSEKI_ENDPOINT = 'http://localhost:3030/Hotels'


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
        port = 9014
    else:
        port = args.port

    if args.open:
        hostname = '0.0.0.0'
        hostaddr = gethostname()
    else:
        hostaddr = hostname = socket.gethostname()

    print('DS Hostname =', hostaddr)

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

# Contador de mensajes
mss_cnt = 0

# Datos del Agente
HotelsAgent = Agent('HotelsAgent',
                       agn.HotelsAgent,
                       'http://%s:%d/comm' % (hostname, port),
                       'http://%s:%d/Stop' % (hostname, port))

# Directory agent address
DirectoryAgent = Agent('DirectoryAgent',
                    agn.Directory,
                    'http://%s:%d/Register' % (dhostname, dport),
                    'http://%s:%d/Stop' % (dhostname, dport))

# Global triplestore graph
dsgraph = Graph()

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

    reg_obj = agn[HotelsAgent.name + '-Register']
    gmess.add((reg_obj, RDF.type, DSO.Register))
    gmess.add((reg_obj, DSO.Uri, HotelsAgent.uri))
    gmess.add((reg_obj, FOAF.name, Literal(HotelsAgent.name)))
    gmess.add((reg_obj, DSO.Address, Literal(HotelsAgent.address)))
    gmess.add((reg_obj, DSO.AgentType, DSO.HotelsAgent))

    # Lo metemos en un envoltorio FIPA-ACL y lo enviamos
    gr = send_message(
        build_message(gmess, perf=ACL.request,
                      sender=HotelsAgent.uri,
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
        gr = build_message(Graph(), ACL['not-understood'], sender=HotelsAgent.uri, msgcnt=get_count())


    else:
        # Get the performative
        if msgdic['performative'] != ACL.request:
            print('Mensaje no es request')
            # Is is not request return not understood
            gr = build_message(Graph(),
                                ACL['not-understood'],
                                sender=HotelsAgent.uri,
                                msgcnt=get_count())

        else:
            # Get the action of the request
            content = msgdic['content']
            # Averiguamos el tipo de la accion
            accion = gm.value(subject=content, predicate=RDF.type)

            # Trip Request
            if accion == ONTO.HotelRequest:
                logger.info("Hotels request recived")

                messageGraph = resolve_request(gm)

                gr = build_message(messageGraph,
                                    ACL['inform'],
                                    sender=HotelsAgent.uri,
                                    msgcnt=get_count())
            else:
                print('Accio no reconeguda')
                gr = build_message(Graph(),
                                    ACL['not-understood'],
                                    sender=HotelsAgent.uri,
                                    msgcnt=get_count())

    return gr.serialize(format='xml'), 200


def resolve_request(hotelRequestGraph: Graph):
    """
    Given the request graph, extracts the information and makes the request
    """
    msgdic = get_message_properties(hotelRequestGraph)
    content = msgdic['content']

    # Get the date and the max price
    min_price = hotelRequestGraph.value(subject=content, predicate=ONTO.minPrice)
    max_price = hotelRequestGraph.value(subject=content, predicate=ONTO.maxPrice)
    destination = hotelRequestGraph.value(subject=content, predicate=ONTO.destination)
    location = hotelRequestGraph.value(subject=content, predicate=ONTO.location)

    print("Min price: " + str(min_price))
    print("Max price: " + str(max_price))
    print("Destination: " + str(destination))
    print("Location: " + str(location))
    return search_hotels(destination=destination, maxPrice=max_price, minPrice=min_price, location=location)


def search_hotels(destination=None, minPrice=sys.float_info.min, maxPrice=sys.float_info.max, location=None):

    first = second = 0
    query = """
            prefix rdf:<http://www.w3.org/1999/02/22-rdf-syntax-ns#>
            prefix xsd:<http://www.w3.org/2001/XMLSchema#>
            prefix default:<http://www.owl-ontologies.com/OntologiaECSDI.owl#>
            prefix owl:<http://www.w3.org/2002/07/owl#>
            SELECT DISTINCT ?hotel ?nombre ?precio ?id ?ubicacion ?ciutat_desti
            where {
                { ?hotel rdf:type default:Hotel }.
                ?hotel default:CiudadHotel ?ciutat_desti .
                ?hotel default:NombreHotel ?nombre .
                ?hotel default:PrecioHotel ?precio .
                ?hotel default:UbicacionHotel ?ubicacion .
                ?hotel default:Identificador ?id . 
                FILTER("""

    if destination is not None:
        query += """str(?ciutat_desti) = '""" + destination + """'"""
        first = 1

    if location is not None:
        if first == 1:
            query += """ && """
        query += """str(?ubicacion) = '""" + location + """'"""
        first = 1

    if first == 1 or second == 1:
        query += """ && """

    print("Min: " + str(minPrice) + " Max: " + str(maxPrice))
    query += """?precio >= """ + str(minPrice) + """ &&
                    ?precio <= """ + str(maxPrice) + """  )}
                    order by asc(UCASE(str(?nombre)))"""

    response = requests.post(f"{FUSEKI_ENDPOINT}/query", data={"query": query})
    results = response.json()
    bindings = results.get("results", {}).get("bindings", [])
    result = Graph()
    hotel_count = 0
    for binding in bindings:
        nombre_hotel = binding.get("nombre", {}).get("value", "")
        print("Nombre del hotel --> " + nombre_hotel)
        precio_hotel = binding.get("precio", {}).get("value", "")
        print("Precio/noche del hotel --> " + precio_hotel)
        print("---------------------------------------")
        id_hotel = binding.get("id", {}).get("value", "")
        subject_hotel = URIRef(binding.get("hotel", {}).get("value", ""))

        ubicacion_hotel = binding.get("ubicacion", {}).get("value", "")

        hotel_count += 1
        result.add((subject_hotel, RDF.type, ONTO.Hotel))
        result.add((subject_hotel, ONTO.price, Literal(precio_hotel, datatype=XSD.float)))
        result.add((subject_hotel, ONTO.id, Literal(id_hotel, datatype=XSD.string)))
        result.add((subject_hotel, ONTO.name, Literal(nombre_hotel, datatype=XSD.string)))
        result.add((subject_hotel, ONTO.location, Literal(ubicacion_hotel, datatype=XSD.string)))

        hotels_list = []
        subjects_position = {}
        pos = 0

    for s, p, o in result:
        if s not in subjects_position:
                subjects_position[s] = pos
                pos += 1
                hotels_list.append({})
        if s in subjects_position:
                hotel = hotels_list[subjects_position[s]]
                if p == RDF.type:
                    hotel['url'] = s
                if p == ONTO.id:
                    hotel['id'] = o
                if p == ONTO.price:
                    hotel['price'] = o
                if p == ONTO.name:
                    hotel['name'] = o
                if p == ONTO.location:
                    hotel['location'] = o

        # Imprimir flights_list
    for hotel in hotels_list:
            print("--- Hotel ---")
            print("ID:", hotel.get('id'))
            print("Name:", hotel.get('name'))
            print("Price/Night:", hotel.get('price'))
            print("Location:", hotel.get('location'))
            print("---------------------")

    print(hotel_count)
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
    #search_hotels("Barcelona", 0, 200, "Céntrico")

    pass


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
    # Ponemos en marcha los behaviors
    ab1 = Process(target=startAndWait, args=(cola1,))
    ab1.start()

    # Ponemos en marcha el servidor
    app.run(host=hostname, port=port)

    # Esperamos a que acaben los behaviors
    ab1.join()
    print('The End')
