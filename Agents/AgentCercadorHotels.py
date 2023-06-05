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

__author__ = 'javier'

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
        port = 9011
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
AgenteHotel = Agent('AgenteHotel',
                       agn.HotelsAgent,
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

    print('Nos registramos')

    global mss_cnt

    gmess = Graph()

    # Construimos el mensaje de registro
    gmess.bind('foaf', FOAF)
    gmess.bind('dso', DSO)
    reg_obj = agn[AgenteHotel.name + '-Register']
    gmess.add((reg_obj, RDF.type, DSO.Register))
    gmess.add((reg_obj, DSO.Uri, AgenteHotel.uri))
    gmess.add((reg_obj, FOAF.name, Literal(AgenteHotel.name)))
    gmess.add((reg_obj, DSO.Address, Literal(AgenteHotel.address)))
    gmess.add((reg_obj, DSO.AgentType, DSO.HotelsAgent))

    # Lo metemos en un envoltorio FIPA-ACL y lo enviamos
    gr = send_message(
        build_message(gmess, perf=ACL.request,
                      sender=AgenteHotel.uri,
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
        gr = build_message(Graph(), ACL['not-understood'], sender=AgenteHotel.uri, msgcnt=get_count())


    else:
        # Obtenemos la performativa
        if msgdic['performative'] != ACL.request:
            print('Mensaje no es request')
            # Si no es un request, respondemos que no hemos entendido el mensaje
            gr = build_message(Graph(),
                               ACL['not-understood'],
                               sender=AgenteHotel.uri,
                               msgcnt=get_count())

        else:
            # Extraemos el objeto del contenido que ha de ser una accion de la ontologia
            # de registro
            print('Mensaje puede ser accion de onto')
            content = msgdic['content']
            # Averiguamos el tipo de la accion
            accion = gm.value(subject=content, predicate=RDF.type)

            # Accion de buscar productos
            if accion == ONTO.BuscarHoteles:
                print("Works here")
                restriccions = gm.objects(content, ONTO.RestringidaPor)
                restriccions_dict = {}
                # Per totes les restriccions que tenim en la cerca d'hotels
                for restriccio in restriccions:
                    if gm.value(subject=restriccio, predicate=RDF.type) == ONTO.RestriccionCiudad:
                        ciutat_desti = gm.value(subject=restriccio, predicate=ONTO.CiudadHotel)
                        print('BÚSQUEDA->Restriccion de ciutat del hotel: ' + ciutat_desti)
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


                    elif gm.value(subject=restriccio, predicate=RDF.type) == ONTO.RestriccionUbicacion:
                        ubicacion = gm.value(subject=restriccio, predicate=ONTO.UbicacionHotel)
                        print('BÚSQUEDA->Restriccion de Nombre: ' + ubicacion)
                        restriccions_dict['ubicacion'] = ubicacion

                    elif gm.value(subject=restriccio, predicate=RDF.type) == ONTO.RestriccionDiasViaje:
                        diasViaje = gm.value(subject=restriccio, predicate=ONTO.DiasViaje)
                        print('BÚSQUEDA->Restriccion de Valoracion: ' + diasViaje)
                        restriccions_dict['diasViaje'] = diasViaje

                gr = buscar_hoteles(**restriccions_dict)

    return gr.serialize(format='xml'), 200

def buscar_hoteles(ciutat_desti=None, preciomin=sys.float_info.min, preciomax=sys.float_info.max, ubicacion=None, diasViaje=None):
    graph = Graph()
    ontologyFile = open('./Data/Hoteles')
    graph.parse(ontologyFile, format='xml')
    first = second = 0
    print("Funciona" + ciutat_desti)

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

    if ciutat_desti is not None:
        query += """str(?ciutat_desti) = '""" + ciutat_desti + """'"""
        first = 1

    if ubicacion is not None:
        if first == 1:
            query += """ && """
        query += """str(?ubicacion) = '""" + ubicacion + """'"""
        first = 1



    if first == 1 or second == 1:
        query += """ && """

    print("Min: " + str(preciomin) + " Max: " + str(preciomax))
    query += """?precio >= """ + str(preciomin) + """ &&
                    ?precio <= """ + str(preciomax) + """  )}
                    order by asc(UCASE(str(?nombre)))"""

    graph_query = graph.query(query)
    result = Graph()
    hotel_count = 0
    for row in graph_query:
        nombre_hotel = row.nombre
        print("Nombre del hotel --> " + nombre_hotel)
        precio_hotel = row.precio
        id_hotel = row.id
        subject_hotel = row.hotel
        ciudad_destino = row.ciutat_desti
        ubicacion_hotel = row.ubicacion
        hotel_count += 1
        result.add((subject_hotel, RDF.type, ONTO.Hotel))
        result.add((subject_hotel, ONTO.PrecioHotel, Literal(precio_hotel, datatype=XSD.float)))
        result.add((subject_hotel, ONTO.Identificador, Literal(id_hotel, datatype=XSD.string)))
        result.add((subject_hotel, ONTO.NombreHotel, Literal(nombre_hotel, datatype=XSD.string)))
        result.add((subject_hotel, ONTO.UbicacionHotel, Literal(ubicacion_hotel, datatype=XSD.string)))
        result.add((subject_hotel, ONTO.CiudadHotel, Literal(ciudad_destino, datatype=XSD.string)))

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
    # Register the Agent
    logger.info('Register')
    gr = register_message()
    logger.info('Register Done')

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
