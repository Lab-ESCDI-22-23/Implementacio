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
from AgentUtil.PAO import PAO
from AgentUtil.OntoNamespaces import ONTO


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
    
    # Contador de mensajes
    mss_cnt = 0



# Datos del Agente
TravelServiceAgent = Agent("TravelServiceAgent",
                  agn.TravelServiceAgent,
                  'http://%s:%d/comm' % (hostname, port),
                  'http://%s:%d/Stop' % (hostname, port))

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
            if accion == PAO.TripRequest:
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
    tripRequestObj = tripRequestGraph.objects(content, PAO.TripRequest)
    startDate = tripRequestGraph.value(subject=tripRequestObj, predicate=PAO.Start)
    endDate = tripRequestGraph.value(subject=tripRequestObj, predicate=PAO.End)
    location = tripRequestGraph.value(subject=tripRequestObj, predicate=PAO.Location)
    playful = tripRequestGraph.value(subject=tripRequestObj, predicate=PAO.Playful)
    cultural = tripRequestGraph.value(subject=tripRequestObj, predicate=PAO.Cultural)
    festive = tripRequestGraph.value(subject=tripRequestObj, predicate=PAO.Festive)
    budget = tripRequestGraph.value(subject=tripRequestObj, predicate=PAO.Budget)
    originCity = tripRequestGraph.value(subject=tripRequestObj, predicate=PAO.From)
    originCity = tripRequestGraph.value(subject=tripRequestObj, predicate=PAO.From)
    
    logger.info('Trip request made:')
    logger.info(startDate)
    logger.info(endDate)
    logger.info(budget)
    logger.info(playful)
    logger.info(cultural)
    logger.info(festive)
    
    tripGraph = Graph()
    return tripGraph

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
    #regResponseGraph = register_message()

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
    regResponseGraph = register_message()
    init = Process(target=startAndWait, args=(endQueue,))
    init.start()
    

    # Starts the server
    app.run(host=hostname, port=port, debug=True)

    # Wait unitl the behaviors ends
    init.join()
    print('The End')