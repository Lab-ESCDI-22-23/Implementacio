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

from flask import Flask, render_template, request
from rdflib import Graph, Namespace, Literal, XSD, URIRef
from rdflib.namespace import FOAF, RDF

from AgentUtil.ACL import ACL
from AgentUtil.FlaskServer import shutdown_server
from AgentUtil.ACLMessages import build_message, send_message, get_message_properties
from AgentUtil.Agent import Agent
from AgentUtil.Logging import config_logger
from AgentUtil.DSO import DSO
from AgentUtil.Util import gethostname
import socket

from datetime import datetime

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
        port = 9001
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

    # Configuration constants and variables
    agn = Namespace("http://www.agentes.org#")
    onto = Namespace("http://www.owl-ontologies.com/OntologiaECSDI.owl#")

    # Contador de mensajes
    mss_cnt = 0

# Datos del Agente
InformAgent = Agent('InformAgent',
                agn.InformAgent,
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
    
    
    
    reg_obj = agn[InformAgent.name + '-Register']
    gmess.add((reg_obj, RDF.type, DSO.Register))
    gmess.add((reg_obj, DSO.Uri, InformAgent.uri))
    gmess.add((reg_obj, FOAF.name, Literal(InformAgent.name)))
    gmess.add((reg_obj, DSO.Address, Literal(InformAgent.address)))
    gmess.add((reg_obj, DSO.AgentType, DSO.InfoAgent))

    # Lo metemos en un envoltorio FIPA-ACL y lo enviamos
    gr = send_message(
        build_message(gmess, perf=ACL.request,
                      sender=InformAgent.uri,
                      receiver=DirectoryAgent.uri,
                      content=reg_obj,
                      msgcnt=mss_cnt),
        DirectoryAgent.address)
    mss_cnt += 1

    return gr

@app.route("/iface", methods=['GET', 'POST'])
def browser_iface():
    if request.method == 'GET':
        return render_template('iface.html')
    else:
        # Get the data from the form
        user        = request.form['username']
        tripStart   = request.form['start']
        tripEnd     = request.form['end']
        origin      = request.form['from']
        destination = request.form['to']
        budget      = request.form['budget']
        playful     = request.form['playful']
        cultural    = request.form['cultural']
        festive      = request.form['festive']
        location      = request.form['location']
        
        # Build the message and send it
        tripPlanificationGraph = trip_request(user, tripStart, tripEnd, origin, destination, budget, playful, cultural, festive, location)
        
        
    
        print("Result recived")
        
        outboundFlight = {}
        returnFlight = {}

        print(tripPlanificationGraph.serialize(format="turtle"))
    
        for flight in tripPlanificationGraph.subjects(RDF.type, ONTO.Flight):
            # Get outboundFlight info 
            if (None, ONTO.outboundFlight, flight) in tripPlanificationGraph:
                outboundFlight['id'] = tripPlanificationGraph.value(flight, ONTO.id)
                outboundFlight['price'] = tripPlanificationGraph.value(flight, ONTO.price)
                outboundFlight['duration'] = tripPlanificationGraph.value(flight, ONTO.duration)
                outboundFlight['date'] = tripPlanificationGraph.value(flight, ONTO.start)
            
            # Get returnFlight info 
            elif (None, ONTO.returnFlight, flight) in tripPlanificationGraph:
                returnFlight['id'] = tripPlanificationGraph.value(flight, ONTO.id)
                returnFlight['price'] = tripPlanificationGraph.value(flight, ONTO.price)
                returnFlight['duration'] = tripPlanificationGraph.value(flight, ONTO.duration)
                returnFlight['date'] = tripPlanificationGraph.value(flight, ONTO.start)
                
        startDate = datetime.strptime(outboundFlight['date'].split("T")[0], '%Y-%m-%d')
        endDate = datetime.strptime(returnFlight['date'].split("T")[0], '%Y-%m-%d')
       
        days = (endDate-startDate).days
             
        hotel = {}
        for hoteles in tripPlanificationGraph.subjects(RDF.type, ONTO.Hotel):
            print("Entrem bucle hotel")
            if (None, ONTO.lodging, hoteles) in tripPlanificationGraph:
                hotel['name'] = str(tripPlanificationGraph.value(hoteles, ONTO.name))
                hotel['price'] = str(tripPlanificationGraph.value(hoteles, ONTO.price))
                hotel['location'] = str(tripPlanificationGraph.value(hoteles, ONTO.location))


        activities = []     
        for activity in tripPlanificationGraph.subjects(RDF.type, ONTO.Activity):
            print("Entrem bucle activity")
            if (None, ONTO.planedActivity, activity) in tripPlanificationGraph:
                tempActivity = {}
                #activityObj = tripPlanificationGraph.subjects(RDF.type, ONTO.Activity)
                # Get the activities info 
                tempActivity['name'] = str(tripPlanificationGraph.value(activity, ONTO.name))
                tempActivity['priceLevel'] = str(tripPlanificationGraph.value(activity, ONTO.priceLevel))
                tempActivity['type'] = str(tripPlanificationGraph.value(activity, ONTO.type))
                tempActivity['schedule'] = str(tripPlanificationGraph.value(activity, ONTO.schedule))
                print(tempActivity)
                activities.append(tempActivity)

        print(activities)

        morningActivities = []
        afternoneActivities = []     
        nightActivities = []   
        
        for actividad in activities:
            horario = actividad['schedule']
            if horario == "Mati-Tarda":
                morningActivities.append(actividad)
            elif horario == "Nocturna-Tarda":
                afternoneActivities.append(actividad)
            elif horario == 'Nocturna':
                nightActivities.append(actividad)
                
        days = (endDate-startDate).days
                
        planificacion = distribuir_actividades(morningActivities, afternoneActivities, nightActivities, days)

        print(planificacion)
        print(morningActivities)
        print(afternoneActivities)
        print(nightActivities)
        
         # Pasar las listas de actividades a la plantilla
        return render_template('planification.html', outboundFlight=outboundFlight, returnFlight=returnFlight, hotel=hotel, morningActivities=morningActivities, afternoneActivities=afternoneActivities, nightActivities=nightActivities)


def distribuir_actividades(morningActivities, afternoneActivities, nightActivities, days):
    num_activities = len(morningActivities) + len(afternoneActivities) + len(nightActivities)
    promedio_actividades = num_activities // days

    actividades_manana = promedio_actividades // 3
    actividades_tarde = promedio_actividades // 3
    actividades_noche = promedio_actividades // 3

    # Ajustar distribución si no es divisible exactamente por el número de días
    actividades_sobrantes = num_activities - (promedio_actividades * days)
    actividades_manana += actividades_sobrantes

    # Asignar actividades a los días de viaje y franjas horarias
    dias_viaje = [f"Día {i+1}" for i in range(days)]
    franjas_horarias = ["Mañana", "Tarde", "Noche"]
    planificacion = {}

    for dia in dias_viaje:
        planificacion[dia] = {
            "Mañana": [],
            "Tarde": [],
            "Noche": []
        }

    for i, dia in enumerate(dias_viaje):
        for _ in range(actividades_manana):
            if len(morningActivities) > 0:
                planificacion[dia]["Mañana"].append(morningActivities.pop(0))

        for _ in range(actividades_tarde):
            if len(afternoneActivities) > 0:
                planificacion[dia]["Tarde"].append(afternoneActivities.pop(0))

        for _ in range(actividades_noche):
            if len(nightActivities) > 0:
                planificacion[dia]["Noche"].append(nightActivities.pop(0))

    return planificacion

@app.route("/comm")
def comunicacion():
    """
    Entrypoint de comunicacion del agente
    Simplemente retorna un objeto fijo que representa una
    respuesta a una busqueda de hotel

    Asumimos que se reciben siempre acciones que se refieren a lo que puede hacer
    el agente (buscar con ciertas restricciones, reservar)
    Las acciones se mandan siempre con un Request
    Prodriamos resolver las busquedas usando una performativa de Query-ref
    """
    pass


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
    actionObject = agn[InformAgent.name + '-search']
    messageGraph.add((actionObject, RDF.type, DSO.Search))
    messageGraph.add((actionObject, DSO.AgentType, type))

    msg = build_message(messageGraph, perf=ACL.request,
                        sender=InformAgent.uri,
                        receiver=DirectoryAgent.uri,
                        content=actionObject,
                        msgcnt=mss_cnt)
    
    gr = send_message(msg, DirectoryAgent.address)
    mss_cnt += 1
    logger.info('Search response recived')

    return gr

def trip_request(user, tripStart, tripEnd, origin, destination, budget, playful, cultural, festive, location):
    
    global mss_cnt
    
    # Search in the directory for a Planifier agent
    typeResponse = directory_search_message(DSO.TravelServiceAgent)
    
    responseGraph = typeResponse.value(predicate=RDF.type, object=ACL.FipaAclMessage)
    content = typeResponse.value(subject=responseGraph, predicate=ACL.content)
    planifierAddres = typeResponse.value(subject=content, predicate=DSO.Address)
    planifierUri = typeResponse.value(subject=content, predicate=DSO.Uri)


    print("Planifier addres: ", planifierAddres)
    print("Planifier uri: ", planifierUri)
    messageGraph = Graph()
    
    messageGraph.bind('foaf', FOAF)
    messageGraph.bind('onto', onto)
    
    #Build the person 
    person = onto[user]
    messageGraph.add((person, RDF.type, FOAF.Person))
    messageGraph.add((person, FOAF.name, Literal(user)))
    
    tripRequestObj = onto['TripRequest_' + str(mss_cnt)] #Object of the trip request
    
    messageGraph.add((tripRequestObj, RDF.type, ONTO.TripRequest)) 
    
    messageGraph.add((tripRequestObj, ONTO.by, person)) #Add the user making the request
    
    #Add the dates
    messageGraph.add((tripRequestObj, ONTO.start, Literal(tripStart)))
    messageGraph.add((tripRequestObj, ONTO.end, Literal(tripEnd)))
    messageGraph.add((tripRequestObj, ONTO.location, Literal(location)))
    messageGraph.add((tripRequestObj, ONTO.budget, Literal(budget)))
    
    #Add the activities types
    messageGraph.add((tripRequestObj, ONTO.playful, Literal(playful)))
    messageGraph.add((tripRequestObj, ONTO.festive, Literal(festive)))
    messageGraph.add((tripRequestObj, ONTO.cultural, Literal(cultural)))
    
    #Create the city and add them
    ori = onto[origin]
    dest = onto[destination]
    messageGraph.add((ori, RDF.type, ONTO.City))
    messageGraph.add((ori, ONTO.name, Literal(origin)))
    messageGraph.add((dest, RDF.type, ONTO.City))
    messageGraph.add((dest, ONTO.name, Literal(destination)))
    
    messageGraph.add((tripRequestObj, ONTO.origin, ori))
    messageGraph.add((tripRequestObj, ONTO.destination, dest))
    
    
    
    message = build_message(messageGraph, perf=ACL.request,
                        sender=InformAgent.uri,
                        receiver=planifierUri,
                        content=tripRequestObj,
                        msgcnt=mss_cnt)
    
    logger.info("send the message")
    responseGraph = send_message(message, planifierAddres)
    mss_cnt += 1
    
    return responseGraph
    
    
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
    app.run(host=hostname, port=port)

    # Wait unitl the behaviors ends
    init.join()
    logger.info('The End')
