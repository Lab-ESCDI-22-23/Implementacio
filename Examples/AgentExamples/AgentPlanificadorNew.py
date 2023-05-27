# -*- coding: utf-8 -*-
"""
filename: SimpleInfoAgent

Antes de ejecutar hay que añadir la raiz del proyecto a la variable PYTHONPATH

Agente que se registra como agente de hoteles y espera peticiones

@author: javier
"""

from multiprocessing import Process, Queue
import logging
import argparse

from flask import Flask, request
from rdflib import Graph, Namespace, Literal
from rdflib.namespace import FOAF, RDF

from AgentUtil.ACL import ACL
from AgentUtil.FlaskServer import shutdown_server
from AgentUtil.ACLMessages import build_message, send_message, get_message_properties
from AgentUtil.Agent import Agent
from AgentUtil.Logging import config_logger
from AgentUtil.DSO import DSO
from AgentUtil.Util import gethostname
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
import socket



__author__ = 'javier'

hostname = socket.gethostname()
# Configuration stuff
port = 9011

app = Flask(__name__)
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

# Configuration constants and variables
agn = Namespace("http://www.agentes.org#")

# Contador de mensajes
mss_cnt = 0
def get_count():
    global mss_cnt
    mss_cnt += 1
    return mss_cnt

# Datos del Agente
AgentePlanficador = Agent('AgentePlanficador',
                  agn.AgentePlanficador,
                  'http://%s:%d/comm' % (hostname, port),
                  'http://%s:%d/Stop' % (hostname, port))

# Directory agent address
DirectoryAgent = Agent('DirectoryAgent',
                       agn.Directory,
                       'http://%s:9000/Register' % hostname,
                       'http://%s:9000/Stop' % hostname)


AgenteHotel = Agent('AgenteHotel',
                            agn.AgenteHotel,
                            'http://%s:9010/comm' % hostname,
                            'http://%s:9010/Stop' % hostname)

AgenteVuelos = Agent('AgenteVuelos',
                            agn.AgenteVuelos,
                            'http://%s:9012/comm' % hostname,
                            'http://%s:9012/Stop' % hostname)

# Global dsgraph triplestore
dsgraph = Graph()

# Cola de comunicacion entre procesos
cola1 = Queue()


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
    reg_obj = agn[AgentePlanficador.name + '-Register']
    gmess.add((reg_obj, RDF.type, DSO.Register))
    gmess.add((reg_obj, DSO.Uri, AgentePlanficador.uri))
    gmess.add((reg_obj, FOAF.name, Literal(AgentePlanficador.name)))
    gmess.add((reg_obj, DSO.Address, Literal(AgentePlanficador.address)))
    gmess.add((reg_obj, DSO.AgentType, DSO.HotelsAgent))

    # Lo metemos en un envoltorio FIPA-ACL y lo enviamos
    gr = send_message(
        build_message(gmess, perf=ACL.request,
                      sender=AgentePlanficador.uri,
                      receiver=DirectoryAgent.uri,
                      content=reg_obj,
                      msgcnt=mss_cnt),
        DirectoryAgent.address)
    mss_cnt += 1

    return gr


#@app.route("/iface", methods=['GET', 'POST'])
def browser_iface():
    """
    Permite la comunicacion con el agente via un navegador
    via un formulario
    """
    return 'Nothing to see here'


@app.route("/stop")
def stop():
    """
    Entrypoint que para el agente

    :return:
    """
    tidyup()
    shutdown_server()
    return "Parando Servidor"


@app.route("/comm")
def comunicacion():
    """
    Entrypoint de comunicacion del agente
    Simplemente retorna un objeto fijo que representa una
    respuesta a una busqueda de hotel

    """

    message = request.args['content']
    gm = Graph()
    gm.parse(data=message)

    msgdic = get_message_properties(gm)

    gr = None
    global mss_cnt
    if msgdic is None:
        mss_cnt += 1
        # Si no es, respondemos que no hemos entendido el mensaje
        gr = build_message(Graph(), ACL['not-understood'], sender=AgentePlanficador.uri, msgcnt=str(mss_cnt))

    else:
        # Obtenemos la performativa
        if msgdic['performative'] != ACL.request:
            # Si no es un request, respondemos que no hemos entendido el mensaje
            gr = build_message(Graph(),
                               ACL['not-understood'],
                               sender=AgentePlanficador.uri,
                               msgcnt=str(mss_cnt))

        else:
            # Extraemos el objeto del contenido que ha de ser una accion de la ontologia
            # de registro
            content = msgdic['content']
            # Averiguamos el tipo de la accion
            accion = gm.value(subject=content, predicate=RDF.type)

    gr = Graph()
    return gr.serialize(format='xml')


def buscar_hoteles(ciutat_desti=None, preciomin=sys.float_info.min, preciomax=sys.float_info.max, ubicacion=None):
    global mss_cnt
    g = Graph()

    action = ONTO['BuscarHoteles_' + str(mss_cnt)]
    g.add((action, RDF.type, ONTO.BuscarHoteles))
    print("Buscar hoteles v1")
    if ciutat_desti:
        cityRestriction = ONTO['RestriccionCiudad_' + str(mss_cnt)]
        g.add((cityRestriction, RDF.type, ONTO.RestriccionCiudad))
        g.add((cityRestriction, ONTO.CiudadHotel, Literal(ciutat_desti)))  # datatype=XSD.string !??!!?!?!?
        g.add((action, ONTO.RestringidaPor, URIRef(cityRestriction)))
    print("Buscar hoteles v2")
    if preciomin:
        minPriceRestriction = ONTO['RestriccionPrecio_' + str(mss_cnt)]
        g.add((minPriceRestriction, RDF.type, ONTO.RestriccionPrecio))
        g.add((minPriceRestriction, ONTO.PrecioMin, Literal(preciomin)))
        g.add((action, ONTO.RestringidaPor, URIRef(minPriceRestriction)))
    print("Buscar hoteles v3")
    if preciomax:
        maxPriceRestriction = ONTO['RestriccionPrecio_' + str(mss_cnt)]
        g.add((maxPriceRestriction, RDF.type, ONTO.RestriccionPrecio))
        g.add((maxPriceRestriction, ONTO.PrecioMax, Literal(preciomax)))
        g.add((action, ONTO.RestringidaPor, URIRef(maxPriceRestriction)))
    print("Buscar hoteles v4")
    if ubicacion:
        ubiRestriction = ONTO['RestriccionUbicacion_' + str(mss_cnt)]
        g.add((ubiRestriction, RDF.type, ONTO.RestriccionUbicacion))
        g.add((ubiRestriction, ONTO.UbicacionHotel, Literal(ubicacion)))
        g.add((action, ONTO.RestringidaPor, URIRef(ubiRestriction)))
    print("Buscar hoteles v5")
    msg = build_message(gmess=g, perf=ACL.request, sender= AgentePlanficador.uri, receiver=AgenteHotel.uri, content=action, msgcnt= mss_cnt)
    print("Buscar hoteles v6")
    mss_cnt += 1
    gproducts = send_message(msg, AgenteHotel.address)
    print("Buscar hoteles v7")

    hotels_list = []
    subjects_position = {}
    pos = 0
    for s, p, o in gproducts:
        if s not in subjects_position:
            subjects_position[s] = pos
            pos += 1
            hotels_list.append({})
        if s in subjects_position:
            hotel = hotels_list[subjects_position[s]]
            if p == RDF.type:
                hotel['url'] = s
            if p == ONTO.Identificador:
                hotel['id'] = o
            if p == ONTO.Nombre:
                hotel['name'] = o
            if p == ONTO.CiudadHotel:
                hotel['city'] = o
            if p == ONTO.PrecioHotel:
                hotel['price'] = o
            if p == ONTO.UbicacionHotel:
                hotel["location"] = o

    # Print de hotels_list
    for hotel in hotels_list:
        print("--- Hotel ---")
        print("ID:", hotel.get('id'))
        print("Nombre:", hotel.get('name'))
        print("Ciudad:", hotel.get('city'))
        print("Precio:", hotel.get('price'))
        print("Ubicación:", hotel.get('location'))
        print("Valoración:", hotel.get('rating'))
        print("---------------------")



def buscar_vuelos(ciutat_origen=None, ciutat_desti=None, preciomin=sys.float_info.min, preciomax=sys.float_info.max, fecha_salida=None):
    global mss_cnt
    g = Graph()

    action = ONTO['BuscarVuelos_' + str(mss_cnt)]
    g.add((action, RDF.type, ONTO.BuscarVuelos))
    print("Buscar Vuelos v1")
    if ciutat_origen:
        cityRestrictionOrig = ONTO['RestriccionOrigenDesti' + str(mss_cnt)]
        g.add((cityRestrictionOrig, RDF.type, ONTO.RestriccionOrigenDesti))
        g.add((cityRestrictionOrig, ONTO.CiudadOrigen, Literal(ciutat_origen)))  # datatype=XSD.string !??!!?!?!?
        g.add((action, ONTO.RestringidaPor, URIRef(cityRestrictionOrig)))
    print("Buscar Vuelos v2")

    if ciutat_desti:
        cityRestrictionDest = ONTO['RestriccionOrigenDesti' + str(mss_cnt)]
        g.add((cityRestrictionDest, RDF.type, ONTO.RestriccionOrigenDesti))
        g.add((cityRestrictionDest, ONTO.CiudadDestino, Literal(ciutat_desti)))  # datatype=XSD.string !??!!?!?!?
        g.add((action, ONTO.RestringidaPor, URIRef(cityRestrictionDest)))
    print("Buscar Vuelos v2.1")

    if preciomin:
        minPriceRestriction = ONTO['RestriccionPrecio_' + str(mss_cnt)]
        g.add((minPriceRestriction, RDF.type, ONTO.RestriccionPrecio))
        g.add((minPriceRestriction, ONTO.PrecioMin, Literal(preciomin)))
        g.add((action, ONTO.RestringidaPor, URIRef(minPriceRestriction)))
    print("Buscar Vuelos v3")
    if preciomax:
        maxPriceRestriction = ONTO['RestriccionPrecio_' + str(mss_cnt)]
        g.add((maxPriceRestriction, RDF.type, ONTO.RestriccionPrecio))
        g.add((maxPriceRestriction, ONTO.PrecioMax, Literal(preciomax)))
        g.add((action, ONTO.RestringidaPor, URIRef(maxPriceRestriction)))

    print("Buscar Vuelos v4")
    if fecha_salida:
        fechaRestriction = ONTO['RestriccionFecha_' + str(mss_cnt)]
        g.add((fechaRestriction, RDF.type, ONTO.RestriccionFecha))
        g.add((fechaRestriction, ONTO.FechaSalida, Literal(fecha_salida)))
        g.add((action, ONTO.RestringidaPor, URIRef(fechaRestriction)))
    print("Buscar Vuelos v5")
    msg = build_message(gmess=g, perf=ACL.request, sender= AgentePlanficador.uri, receiver=AgenteVuelos.uri, content=action, msgcnt= mss_cnt)
    print("Buscar Vuelos v6")
    mss_cnt += 1

    gproducts = send_message(msg, AgenteVuelos.address)
    print("Buscar Vuelos Fin")

    flights_list = []
    subjects_position = {}
    pos = 0

    for s, p, o in gproducts:
        if s not in subjects_position:
            subjects_position[s] = pos
            pos += 1
            flights_list.append({})
        if s in subjects_position:
            flight = flights_list[subjects_position[s]]
            if p == RDF.type:
                flight['url'] = s
            if p == ONTO.Identificador:
                flight['id'] = o
            if p == ONTO.FechaSalida:
                flight['fecha_salida'] = o
            if p == ONTO.FechaLlegada:
                flight['fecha_llegada'] = o
            if p == ONTO.PrecioVuelo:
                flight['precio'] = o
            if p == ONTO.DuracionVuelo:
                flight['duracion'] = o

    # Imprimir flights_list
    for flight in flights_list:
        print("--- Vuelo ---")
        print("ID:", flight.get('id'))
        print("Fecha llegada:", flight.get('fecha_llegada'))
        print("Fecha Salida:", flight.get('fecha_salida'))
        print("Precio:", flight.get('precio'))
        print("Duracion:", flight.get('duracion'))
        print("---------------------")






def tidyup():
    """
    Acciones previas a parar el agente

    """
    global cola1
    cola1.put(0)


def agentbehavior1(cola):
    """
    Un comportamiento del agente

    :return:
    """
    # Registramos el agente
    gr = register_message()

    # Escuchando la cola hasta que llegue un 0
    #buscar_hoteles("Barcelona", 10, 120, "Centro")
    buscar_vuelos("BCN", "LON", 150, 200, "2023-05-28")

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
