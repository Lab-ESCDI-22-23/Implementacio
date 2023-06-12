"""
filename: SimpleInfoAgent

Antes de ejecutar hay que añadir la raiz del proyecto a la variable PYTHONPATH

Agente que se registra como agente de hoteles y espera peticiones

@author: agracia
"""

from multiprocessing import Process, Queue
import logging
import argparse
from operator import attrgetter
import socket

from flask import Flask, render_template, request
from AgentUtil.FlaskServer import shutdown_server
from AgentUtil.Logging import config_logger
from AgentUtil.Util import gethostname

from AgentUtil.ACLMessages import build_message, send_message, get_message_properties
from AgentUtil.Agent import Agent
from rdflib import Graph, Namespace, Literal, XSD, URIRef
from rdflib.namespace import FOAF, RDF

from AgentUtil.ACL import ACL
from AgentUtil.DSO import DSO
from AgentUtil.ONTO import ONTO

from datetime import datetime, date
import random


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
    print('DS Port =', port)

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
    minPrice = tripRequestGraph.value(subject=content, predicate=ONTO.minPrice)
    maxPrice = tripRequestGraph.value(subject=content, predicate=ONTO.maxPrice)
       
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
    
    result = Graph()
    
    tripPlanificationObj = onto["TripPlanification_", get_count()]
    result.add((tripPlanificationObj, RDF.type, ONTO.TripPlanification))
    hotelObj = onto["ChosedHotel"]
    result.add((hotelObj, RDF.type, ONTO.Hotel))
    outboundFlightObj = onto["OutBoundFlight"]
    result.add((outboundFlightObj, RDF.type, ONTO.Flight))
    returnFlightObj = onto["ReturnFlight"]
    result.add((returnFlightObj, RDF.type, ONTO.Flight))
    
    result.add((tripPlanificationObj, ONTO.outboundFlight, outboundFlightObj))
    result.add((tripPlanificationObj, ONTO.returnFlight, returnFlightObj))
    result.add((tripPlanificationObj, ONTO.lodging, hotelObj))
    
    result.add((outboundFlightObj, ONTO.id, Literal("1")))
    result.add((outboundFlightObj, ONTO.price, Literal("1000000")))
    result.add((outboundFlightObj, ONTO.duration, Literal("583")))
    result.add((outboundFlightObj, ONTO.date, Literal("1987-07-04")))
    
    result.add((returnFlightObj, ONTO.id, Literal("2")))
    result.add((returnFlightObj, ONTO.price, Literal("1000000")))
    result.add((returnFlightObj, ONTO.duration, Literal("193")))
    result.add((returnFlightObj, ONTO.date, Literal("2034-09-23")))
    
    result.add((hotelObj, ONTO.name, Literal("My Hotel")))
    result.add((hotelObj, ONTO.price, Literal("1000000")))
    result.add((hotelObj, ONTO.location, Literal("En medio")))
    
    activities = [
        {
            'name' : 'activitat  mati 1',
            'priceLevel' : '1',
            'type': "ludico",
            'schedule': 'Mati-Tarda'
        },
        {
            'name' : 'activitat  mati 2',
            'priceLevel' : '1',
            'type': "ludico",
            'schedule': 'Mati-Tarda'
        },
        {
            'name' : 'activitat  mati 3',
            'priceLevel' : '1',
            'type': "ludico",
            'schedule': 'Mati-Tarda'
        },
        {
            'name' : 'activitat  mati 4',
            'priceLevel' : '1',
            'type': "ludico",
            'schedule': 'Mati-Tarda'
        },
        {
            'name' : 'activitat tarda 1',
            'priceLevel' : '1',
            'type': "ludico",
            'schedule': 'Nocturna-Tarda'
        },
        {
            'name' : 'activitat tarda 2',
            'priceLevel' : '1',
            'type': "ludico",
            'schedule': 'Nocturna-Tarda'
        },
        {
            'name' : 'activitat tarda 3',
            'priceLevel' : '1',
            'type': "ludico",
            'schedule': 'Nocturna-Tarda'
        },
        {
            'name' : 'activitat tarda 4',
            'priceLevel' : '1',
            'type': "ludico",
            'schedule': 'Nocturna-Tarda'
        },
        {
            'name' : 'activitat tarda 5',
            'priceLevel' : '1',
            'type': "ludico",
            'schedule': 'Nocturna-Tarda'
        },
        {
            'name' : 'activitat tarda 6',
            'priceLevel' : '1',
            'type': "ludico",
            'schedule': 'Nocturna-Tarda'
        },
        {
            'name' : 'activitat tarda 7',
            'priceLevel' : '1',
            'type': "ludico",
            'schedule': 'Nocturna-Tarda'
        },
        {
            'name' : 'activitat nit 1',
            'priceLevel' : '1',
            'type': "ludico",
            'schedule': 'Nocturna'
        },
        {
            'name' : 'activitat nit 2',
            'priceLevel' : '1',
            'type': "ludico",
            'schedule': 'Nocturna'
        },
        {
            'name' : 'activitat nit 3',
            'priceLevel' : '1',
            'type': "ludico",
            'schedule': 'Nocturna'
        },
        {
            'name' : 'activitat nit 4',
            'priceLevel' : '1',
            'type': "ludico",
            'schedule': 'Nocturna'
        },
        {
            'name' : 'activitat nit 5',
            'priceLevel' : '1',
            'type': "ludico",
            'schedule': 'Nocturna'
        },  
    ]
    
    actividades_count = 1
    for chosenActivity in activities:
        subject_actividades = URIRef("http://www.owl-ontologies.com/OntologiaECSDI.owl#ActividadSeleccionada" + str(actividades_count))
        result.add((subject_actividades, RDF.type, ONTO.Activity))
        result.add((subject_actividades, ONTO.name, Literal(chosenActivity.get("name"), datatype=XSD.string)))
        result.add((subject_actividades, ONTO.priceLevel, Literal(chosenActivity.get("priceLevel"), datatype=XSD.integer)))
        result.add((subject_actividades, ONTO.type, Literal(chosenActivity.get("type"), datatype=XSD.string)))
        result.add((subject_actividades, ONTO.schedule, Literal(chosenActivity.get("schedule"), datatype=XSD.string)))
        result.add((tripPlanificationObj, ONTO.planedActivity, subject_actividades))
        actividades_count += 1
    
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

    #search_hotels(city="Barcelona", location="Céntrico", minPrice=50, maxPrice=400)

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
    app.run(host=hostname, port=port)

    # Wait unitl the behaviors ends
    init.join()
    print('The End')
