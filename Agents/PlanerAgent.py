"""
filename: SimpleInfoAgent

Antes de ejecutar hay que añadir la raiz del proyecto a la variable PYTHONPATH

Agente que se registra como agente de hoteles y espera peticiones

@author: agracia
"""

from multiprocessing import Process, Queue
import logging
import argparse

from flask import Flask, render_template, request
from AgentUtil.FlaskServer import shutdown_server
from AgentUtil.Logging import config_logger
from AgentUtil.Util import gethostname

from AgentUtil.ACLMessages import build_message, send_message, get_message_properties
from AgentUtil.Agent import Agent
from rdflib import Graph, Namespace, Literal, XSD, URIRef
from rdflib.namespace import FOAF, RDF
import socket

from AgentUtil.ACL import ACL
from AgentUtil.DSO import DSO
from AgentUtil.ONTO import ONTO


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
        port = 9010
    else:
        port = args.port

    if args.open:
        hostname = '0.0.0.0'
        hostaddr = gethostname()
    else:
        hostaddr = hostname = socket.gethostname()

    print('DS Hostname =', hostaddr)
    print('DS Hostname =', port)

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
    onto = Namespace("http://www.owl-ontologies.com/OntologiaECSDI.owl#")
    
    # Contador de mensajes
    mss_cnt = 0


# Datos del Agente
TravelServiceAgent = Agent("TravelServiceAgent",
                  agn.TravelServiceAgent,
                  'http://%s:%d/comm' % (hostaddr, port),
                  'http://%s:%d/Stop' % (hostaddr, port))

# Directory agent address
DirectoryAgent = Agent('DirectoryAgent',
                       agn.Directory,
                       'http://%s:%d/Register' % (dhostname, dport),
                       'http://%s:%d/Stop' % (dhostname, dport))

# Global dsgraph triplestore
dsgraph = Graph()

# Queue that waits for a 0 to end the agent
endQueue = Queue()

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
    
    
    
    reg_obj = agn[TravelServiceAgent.name + '-Register']
    gmess.add((reg_obj, RDF.type, DSO.Register))
    gmess.add((reg_obj, DSO.Uri, TravelServiceAgent.uri))
    gmess.add((reg_obj, FOAF.name, Literal(TravelServiceAgent.name)))
    gmess.add((reg_obj, DSO.Address, Literal(TravelServiceAgent.address)))
    gmess.add((reg_obj, DSO.AgentType, DSO.TravelServiceAgent))

    # Lo metemos en un envoltorio FIPA-ACL y lo enviamos
    gr = send_message(
        build_message(gmess, perf=ACL.request,
                      sender=TravelServiceAgent.uri,
                      receiver=DirectoryAgent.uri,
                      content=reg_obj,
                      msgcnt=mss_cnt),
        DirectoryAgent.address)
    mss_cnt += 1

    return gr

def get_count():
    global mss_cnt
    mss_cnt += 1
    return mss_cnt

@app.route("/comm")
def comunicacion():
    """
    Entrypoint de comunicacion del agente
    """
    print('Peticion de informacion recibida')

    global dsgraph
    message = request.args['content']
    gm = Graph()
    gm.parse(data=message, format='xml')
    msgdic = get_message_properties(gm)
    
    gr = None

    if msgdic is None:
        # If the message is not a ACL request
        print("Message don't understood")
        gr = build_message(Graph(), ACL['not-understood'], sender=TravelServiceAgent.uri, msgcnt=get_count())

    else:
        # Get the performative
        if msgdic['performative'] != ACL.request:
            print('Message is not a request')
            # Is is not request return not understood
            gr = build_message(Graph(),
                               ACL['not-understood'],
                               sender=TravelServiceAgent.uri,
                               msgcnt=get_count())

        else:
            # Get the action of the request
            content = msgdic['content']
            accion = gm.value(subject=content, predicate=RDF.type)
            
            # Trip Request
            if accion == ONTO.TripRequest:
                logger.info("Trip request recived")
                messageGraph = build_trip(gm)
                
                gr = build_message(messageGraph,
                                   ACL['inform'],
                                   sender=TravelServiceAgent.uri,
                                   msgcnt=get_count())
     
            else:
                print('Accio no reconeguda')
                gr = build_message(Graph(),
                                   ACL['not-understood'],
                                   sender=TravelServiceAgent.uri,
                                   msgcnt=get_count())


    return gr.serialize(format='xml'), 200

def directory_search_message(type):
    """
    Search in the directory agent the addres of one type of agent

    :param type: Type of the agent to search
    :return:
    """
    global mss_cnt
    print('Searching in the Directory agent an agent of type: ', type)
    #logger.info('Searching in the Directory agent an agent of type: ', type)

    messageGraph = Graph()

    messageGraph.bind('foaf', FOAF)
    messageGraph.bind('dso', DSO)
    actionObject = agn[TravelServiceAgent.name + '-search']
    messageGraph.add((actionObject, RDF.type, DSO.Search))
    messageGraph.add((actionObject, DSO.AgentType, type))

    msg = build_message(messageGraph, perf=ACL.request,
                        sender=TravelServiceAgent.uri,
                        receiver=DirectoryAgent.uri,
                        content=actionObject,
                        msgcnt=mss_cnt)
    
    gr = send_message(msg, DirectoryAgent.address)
    mss_cnt += 1
    logger.info('Search response recived')

    return gr

def build_trip(tripRequestGraph: Graph):
    msgdic = get_message_properties(tripRequestGraph)
    content = msgdic['content']
    
    # Get fields atributes of the trip request
    startDate = tripRequestGraph.value(subject=content, predicate=ONTO.start)
    endDate = tripRequestGraph.value(subject=content, predicate=ONTO.end)
    location = tripRequestGraph.value(subject=content, predicate=ONTO.location)
    playful = tripRequestGraph.value(subject=content, predicate=ONTO.playful)
    cultural = tripRequestGraph.value(subject=content, predicate=ONTO.cultural)
    festive = tripRequestGraph.value(subject=content, predicate=ONTO.festive)
    budget = tripRequestGraph.value(subject=content, predicate=ONTO.budget)
       
    # Get the origin and the destination
    origin = None
    destination = None
    for city in tripRequestGraph.subjects(RDF.type, ONTO.City):
        if (content, ONTO.origin, city) in tripRequestGraph:
            origin = tripRequestGraph.value(city, ONTO.name)
            print("origin", origin)
        elif (content, ONTO.destination, city) in tripRequestGraph:
            destination = tripRequestGraph.value(city, ONTO.name)
            print("destination", destination)
            
    
    # Get the user making the request     
    user = None
    for person in tripRequestGraph.subjects(RDF.type, FOAF.Person):
        if (content, ONTO.by, person) in tripRequestGraph:
            user = person
       
    logger.info('Trip request made:')
    print("User:", user)
    print("Start:", startDate)
    print("End:", endDate)
    print("Origin:", origin)
    print("Destination:", destination)
    print("Location: ", location)
    print("Budget:", budget)
    print("Playful:", playful)
    print("Cultural:", cultural)
    print("Festive:", festive)
    
    lodgingFlightGraph = Graph()
    returnFlightGraph = Graph()
    lodgingFlightSearch = Process(target=search_flights, args=(origin, destination, startDate, budget, lodgingFlightGraph))
    returnFlightSearch = Process(target=search_flights, args=(destination, origin, endDate, budget, returnFlightGraph))
    lodgingFlightSearch.start()
    returnFlightSearch.start()
    
    lodgingFlightSearch.join()
    returnFlightSearch.join()
    
    print(lodgingFlightGraph)
    print(returnFlightGraph)
    
    tripGraph = Graph()
    
    return tripGraph


def search_hotels(city=None, location=None, budget=None):
    global mss_cnt
    
    logger.info('Inici Buscar Hotels')
    
    # Search in the directory for an Hotel agent
    typeResponse = directory_search_message(DSO.HotelsAgent)
    
    responseGraph = typeResponse.value(predicate=RDF.type, object=ACL.FipaAclMessage)
    content = typeResponse.value(subject=responseGraph, predicate=ACL.content)
    hotelAgentAddres = typeResponse.value(subject=content, predicate=DSO.Address)
    hotelAgentUri = typeResponse.value(subject=content, predicate=DSO.Uri)

    messageGraph = Graph()

    hotelsRequestObj = onto['HotelRequest_' + str(mss_cnt)]
    
    messageGraph.add((hotelsRequestObj, RDF.type, ONTO.HotelRequest))
    
    if city:
        messageGraph.add((hotelsRequestObj, ONTO.on , URIRef(city)))
    if budget:
        messageGraph.add((hotelsRequestObj, ONTO.budget, Literal(budget)))
    if location:
        messageGraph.add((hotelsRequestObj, ONTO.location, Literal(location)))
    
    msg = build_message(gmess=messageGraph, perf=ACL.request, sender= TravelServiceAgent.uri, receiver=hotelAgentUri, content=hotelsRequestObj, msgcnt= mss_cnt)
    mss_cnt += 1
    
    logger.info('Enviar Buscar Hotels')
    hotelsResponse = send_message(msg, hotelAgentAddres)
    logger.info('Rebre Buscar Hotels')

    print("Buscar hoteles fin")


def search_flights(origin, destination, date, budget, flightsGraph):
    global mss_cnt
    
    # Search in the directory for an Hotel agent
    typeResponse = directory_search_message(DSO.FlightsAgent)
    
    responseGraph = typeResponse.value(predicate=RDF.type, object=ACL.FipaAclMessage)
    content = typeResponse.value(subject=responseGraph, predicate=ACL.content)
    flightAgentAddres = typeResponse.value(subject=content, predicate=DSO.Address)
    flightAgentUri = typeResponse.value(subject=content, predicate=DSO.Uri)

    messageGraph = Graph()
    messageGraph.bind('foaf', FOAF)
    messageGraph.bind('onto', onto)

    flightRequestObj = onto['FlightRequest_' + str(mss_cnt)]
    
    messageGraph.add((flightRequestObj, RDF.type, ONTO.FlightRequest))
    messageGraph.add((flightRequestObj, ONTO.date, Literal(date)))
    messageGraph.add((flightRequestObj, ONTO.maxPrice, Literal(budget)))
    
    #Create the city and add them
    ori = onto[origin]
    dest = onto[destination]
    messageGraph.add((ori, RDF.type, ONTO.City))
    messageGraph.add((ori, ONTO.name, Literal(origin)))
    messageGraph.add((dest, RDF.type, ONTO.City))
    messageGraph.add((dest, ONTO.name, Literal(destination)))
    
    messageGraph.add((flightRequestObj, ONTO.origin, ori))
    messageGraph.add((flightRequestObj, ONTO.destination, dest))
    
    msg = build_message(gmess=messageGraph, perf=ACL.request, sender= TravelServiceAgent.uri, receiver=flightAgentUri, content=flightRequestObj, msgcnt= mss_cnt)
    mss_cnt += 1
    
    logger.info('Search flight')
    flightsGraph = send_message(msg, flightAgentAddres)
    logger.info('Recive flights')
    
    flights_list = []
    subjects_position = {}
    pos = 0
    
    for s, p, o in flightsGraph:
        if s not in subjects_position:
            subjects_position[s] = pos
            pos += 1
            flights_list.append({})
        if s in subjects_position:
            flight = flights_list[subjects_position[s]]
            if p == RDF.type:
                flight['url'] = s
            if p == ONTO.id:
                flight['id'] = o
            if p == ONTO.start:
                flight['startDate'] = o
            if p == ONTO.end:
                flight['endDate'] = o
            if p == ONTO.price:
                flight['price'] = o
            if p == ONTO.duration:
                flight['duration'] = o

    # Imprimir flights_list
    for flight in flights_list:
        print("--- Vuelo ---")
        print("ID:", flight.get('id'))
        print("Fecha llegada:", flight.get('endDate'))
        print("Fecha Salida:", flight.get('startDate'))
        print("Precio:", flight.get('price'))
        print("Duracion:", flight.get('duration'))
        print("---------------------")

    logger.info('Fi Buscar Vols')
    
def search_activities(city, festive, cultural, playful, budget, start, end):
    global mss_cnt
    
    # Search in the directory for an Hotel agent
    typeResponse = directory_search_message(DSO.ActivitiesAgent)
    
    responseGraph = typeResponse.value(predicate=RDF.type, object=ACL.FipaAclMessage)
    content = typeResponse.value(subject=responseGraph, predicate=ACL.content)
    activitiesAgentAddres = typeResponse.value(subject=content, predicate=DSO.Address)
    activitiesAgentUri = typeResponse.value(subject=content, predicate=DSO.Uri)

    messageGraph = Graph()

    activitiesRequestObj = onto['ActivitiesRequest_' + str(mss_cnt)]
    
    messageGraph.add((activitiesRequestObj, RDF.type, ONTO.ActivitiesRequest))
    
    
     
    
    msg = build_message(gmess=messageGraph, perf=ACL.request, sender= TravelServiceAgent.uri, receiver=activitiesAgentUri, content=hotelsRequestObj, msgcnt= mss_cnt)
    mss_cnt += 1
    
    logger.info('Search flight')
    flightResponse = send_message(msg, activitiesAgentAddres)
    logger.info('Recive flights')


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

# Starts the agent
if __name__ == '__main__':
    # Start the first behavior to register and wait
    init = Process(target=startAndWait, args=(endQueue,))
    init.start()
    

    # Starts the server
    app.run(host=hostname, port=port, debug=True)

    # Wait unitl the behaviors ends
    init.join()
    print('The End')