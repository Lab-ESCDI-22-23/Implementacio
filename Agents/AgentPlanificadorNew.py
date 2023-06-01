# -*- coding: utf-8 -*-
"""
filename: SimpleInfoAgent

Antes de ejecutar hay que añadir la raiz del proyecto a la variable PYTHONPATH

Agente que se registra como agente de hoteles y espera peticiones

@author: agracia
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
                            'http://%s:9010/comm' % "clients-xsf-101.upc.es",
                            'http://%s:9010/Stop' % "clients-xsf-101.upc.es")

AgenteVuelos = Agent('AgenteVuelos',
                            agn.AgenteVuelos,
                            'http://%s:9012/comm' % hostname,
                            'http://%s:9012/Stop' % hostname)

AgenteActividades = Agent('AgenteActividades',
                            agn.AgenteVuelos,
                            'http://%s:9013/comm' % hostname,
                            'http://%s:9013/Stop' % hostname)

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
    gmess.add((reg_obj, DSO.AgentType, DSO.PersonalAgent))

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
        gr = build_message(Graph(), ACL['not-understood'], sender=AgentePlanficador.uri, msgcnt=get_count())

    else:
        # Obtenemos la performativa
        if msgdic['performative'] != ACL.request:
            print('Mensaje no es request')
            # Si no es un request, respondemos que no hemos entendido el mensaje
            gr = build_message(Graph(),
                               ACL['not-understood'],
                               sender=AgentePlanficador.uri,
                               msgcnt=get_count())

        else:
            # Extraemos el objeto del contenido que ha de ser una accion de la ontologia
            # de registro
            print('Mensaje puede ser accion de onto')
            content = msgdic['content']
            # Averiguamos el tipo de la accion
            accion = gm.value(subject=content, predicate=RDF.type)

            # Accion de buscar productos
            if accion == ONTO.PeticioViatge:
                print("Peticio de viatge")

                #OBTENIR PARAMETRES PETICIO
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
                    gr = buscar_vuelos(**restriccions_dict)

                    # CREAR VIATGE [Paralelisme?]
                    """
                    logger.info('Hotels')
                    hotels = buscar_hoteles(**restriccions_hotels) #"Barcelona", 10, 120, "Centro"
                    logger.info('Hotels Done')
                    logger.info('Vols anada')
                    volsAnada = buscar_vuelos(**restriccions_volsAnada) #"BCN", "LON", 50, 100, "2023-06-30"
                    logger.info('Vols anada Done')
                    logger.info('Vols tornada')
                    volsTornada = buscar_vuelos(**restriccions_volsTornada) #"LON", "BCN", 50, 100, "2023-07-05"
                    logger.info('Vols torndada Done')
                    logger.info('Activitats')
                    activitats = buscar_actividades(**restriccions_activitats) #"Alta", 3, 5, 1, 1
                    logger.info('Activitats Done')

                    if hotels.empty():
                        logger.info('No hi ha hotels disponibles amb els requeriments introduits')
                    elif volsAnada.empty():
                        logger.info('No hi ha vols de anada disponibles amb els requeriments introduits')
                    elif volsTornada.empty():
                        logger.info('No hi ha vols de tornada disponibles amb els requeriments introduits')
                    elif activitats.size() > 0:  # num dies
                        logger.info('No hi ha prous activitats disponibles amb els requeriments introduits')
                    else:
                    """

                gr = None #CONSTRUIR GRAF DE RESPOSTA
                """
                -Vols (2)
                -Hotel (1)
                -Activitat(Num de dies):
                    -Mati
                    -Tarda
                    -Nit
                """
            else:
                print('Accio no reconeguda')
                gr = build_message(Graph(),
                                   ACL['not-understood'],
                                   sender=AgentePlanficador.uri,
                                   msgcnt=get_count())


    return gr.serialize(format='xml'), 200


def buscar_hoteles(ciutat_desti=None, preciomin=sys.float_info.min, preciomax=sys.float_info.max, ubicacion=None):
    logger.info('Inici Buscar Hotels')

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
    logger.info('Enviar Buscar Hotels')
    gproducts = send_message(msg, AgenteHotel.address)
    logger.info('Rebre Buscar Hotels')

    print("Buscar hoteles fin")

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
            if p == ONTO.NombreHotel:
                hotel['name'] = o
            if p == ONTO.CiudadHotel:
                hotel['city'] = o
            if p == ONTO.PrecioHotel:
                hotel['price'] = o
            if p == ONTO.UbicacionHotel:
                hotel["location"] = o

    logger.info('Fi Buscar hotels')
    return hotels_list
    """
    # Print de hotels_list
    for hotel in hotels_list:
        print("--- Hotel ---")
        print("ID:", hotel.get('id'))
        print("Nombre:", hotel.get('name'))
        print("Ciudad:", hotel.get('city'))
        print("Precio:", hotel.get('price'))
        print("Ubicación:", hotel.get('location'))

        print("---------------------")
    """



def buscar_vuelos(ciutat_origen=None, ciutat_desti=None, preciomin=sys.float_info.min, preciomax=sys.float_info.max, fecha_salida=None):
    logger.info('Inici Buscar Vols')

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
    logger.info('Enviar Buscar Vols')
    gproducts = send_message(msg, AgenteVuelos.address)
    logger.info('Rebre Buscar Vols')
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

    logger.info('Fi Buscar Vols')

    return flights_list
    """
    # Imprimir flights_list
    for flight in flights_list:
        print("--- Vuelo ---")
        print("ID:", flight.get('id'))
        print("Fecha llegada:", flight.get('fecha_llegada'))
        print("Fecha Salida:", flight.get('fecha_salida'))
        print("Precio:", flight.get('precio'))
        print("Duracion:", flight.get('duracion'))
        print("---------------------")
    """


def buscar_actividades(carga_actividades=None, nivel_precio=2, dias_viaje=0, proporcion_ludico_festiva=0.5, proporcion_cultural=0.5):
    logger.info('Inici Buscar Activitats')

    global mss_cnt
    g = Graph()

    action = ONTO['BuscarActividades_' + str(mss_cnt)]
    g.add((action, RDF.type, ONTO.BuscarActividades))
    print("Buscar Actividades v1")
    if carga_actividades:
        cargaRestriction = ONTO['RestriccionNivelCarga_' + str(mss_cnt)]
        g.add((cargaRestriction, RDF.type, ONTO.RestriccionNivelCarga))
        g.add((cargaRestriction, ONTO.CargaActividades, Literal(carga_actividades)))  # datatype=XSD.string !??!!?!?!?
        g.add((action, ONTO.RestringidaPor, URIRef(cargaRestriction)))
    print("Buscar Actividades v2")

    if nivel_precio:
        nivelPrecioRestriction = ONTO['RestriccionNivelPrecio_' + str(mss_cnt)]
        g.add((nivelPrecioRestriction, RDF.type, ONTO.RestriccionNivelPrecio))
        g.add((nivelPrecioRestriction, ONTO.NivelPrecio, Literal(nivel_precio)))  # datatype=XSD.string !??!!?!?!?
        g.add((action, ONTO.RestringidaPor, URIRef(nivelPrecioRestriction)))
    print("Buscar Actividades v2.1")

    if dias_viaje:
        diasRestriction = ONTO['RestriccionDias_' + str(mss_cnt)]
        g.add((diasRestriction, RDF.type, ONTO.RestriccionDias))
        g.add((diasRestriction, ONTO.DiasViaje, Literal(dias_viaje)))
        g.add((action, ONTO.RestringidaPor, URIRef(diasRestriction)))
    print("Buscar Actividades v3")

    if proporcion_ludico_festiva:
        propLudiFestRestriction = ONTO['RestriccionProporcionActividades_' + str(mss_cnt)]
        g.add((propLudiFestRestriction, RDF.type, ONTO.RestriccionProporcionActividades))
        g.add((propLudiFestRestriction, ONTO.ProporcionLudicoFestiva, Literal(proporcion_ludico_festiva)))
        g.add((action, ONTO.RestringidaPor, URIRef(propLudiFestRestriction)))

    print("Buscar Actividades v4")
    if proporcion_cultural:
        propCultRestriction = ONTO['RestriccionProporcionActividades_' + str(mss_cnt)]
        g.add((propCultRestriction, RDF.type, ONTO.RestriccionProporcionActividades))
        g.add((propCultRestriction, ONTO.ProporcionCultural, Literal(proporcion_cultural)))
        g.add((action, ONTO.RestringidaPor, URIRef(propCultRestriction)))


    print("Buscar Actividades v5")
    msg = build_message(gmess=g, perf=ACL.request, sender= AgentePlanficador.uri, receiver=AgenteActividades.uri, content=action, msgcnt= mss_cnt)
    print("Buscar Actividades v6")
    mss_cnt += 1
    logger.info('Enviar Buscar Activitats')
    gproducts = send_message(msg, AgenteActividades.address)
    logger.info('Rebre Buscar Activitats')

    print("Buscar Actividades Fin")

    actividades_list = []
    subjects_position = {}
    pos = 0

    for s, p, o in gproducts:
        if s not in subjects_position:
            subjects_position[s] = pos
            pos += 1
            actividades_list.append({})
        if s in subjects_position:
            actividad = actividades_list[subjects_position[s]]
            if p == RDF.type:
                actividad['url'] = s
            if p == ONTO.Identificador:
                actividad['id'] = o
            if p == ONTO.NombreActividad:
                actividad['nombre_actividad'] = o
            if p == ONTO.NivelPrecio:
                actividad['nivel_precio'] = o

    logger.info('Fi Buscar Acivitats')

    return actividades_list
    """
    # Imprimir flights_list
    for actividad in actividades_list:
        print("--- Actividad ---")
        #print("ID:", actividad.get('id'))
        print("Fecha llegada:", actividad.get('nombre_actividad'))
        print("Fecha Salida:", actividad.get('nivel_precio'))

        print("---------------------")
    """




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
    logger.info('Register')
    gr = register_message()
    logger.info('Register Done')


    # PARALELISME
    logger.info('Creating')
    p1 = Process(target=buscar_hoteles, args=("Barcelona", 10, 120, "Centro"))
    p2 = Process(target=buscar_vuelos, args=("BCN", "LON", 50, 100, "2023-06-30"))
    p3 = Process(target=buscar_actividades, args=("Alta", 3, 5, 1, 1))
    logger.info('Starting')
    p1.start()
    p2.start()
    p3.start()
    logger.info('Joining')
    p1.join()
    #p2.join()
    #p3.join()
    logger.info('Done')


    """
    logger.info('Hotels')
    hotels = buscar_hoteles("Barcelona", 10, 120, "Centro")
    logger.info('Hotels Done')
    logger.info('Vols anada')
    volsAnada = buscar_vuelos("BCN", "LON", 50, 100, "2023-06-30")
    logger.info('Vols anada Done')
    logger.info('Vols tornada')
    volsTornada = buscar_vuelos("LON", "BCN", 50, 100, "2023-07-05")
    logger.info('Vols torndada Done')
    logger.info('Activitats')
    activitats = buscar_actividades("Alta", 3, 5, 1, 1)
    logger.info('Activitats Done')

    if hotels.empty():
        logger.info('No hi ha hotels disponibles amb els requeriments introduits')
    elif volsAnada.empty():
        logger.info('No hi ha vols de anada disponibles amb els requeriments introduits')
    elif volsTornada.empty():
        logger.info('No hi ha vols de tornada disponibles amb els requeriments introduits')
    elif activitats.size() > 0: #num dies
        logger.info('No hi ha prous activitats disponibles amb els requeriments introduits')
    else:
        logger.info('Planejant')

    """

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
