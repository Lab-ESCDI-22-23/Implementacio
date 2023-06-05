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

    q1 = Queue()
    q2 = Queue()
    q3 = Queue()
    q4 = Queue()

    outboundFlightGraph = Graph()
    returnFlightGraph = Graph()
    outboundFlightSearch = Process(target=search_flights, args=(q1, origin, destination, startDate, budget, outboundFlightGraph))
    returnFlightSearch = Process(target=search_flights, args=(q2, destination, origin, endDate, budget, returnFlightGraph))
    
    outboundFlightSearch.start()
    returnFlightSearch.start()
    
    outboundFlightSearch.join()
    returnFlightSearch.join()



    hotelsGraph = Graph()
    hotelsSearch = Process(target=search_hotels, args=(q3, destination, location, budget, hotelsGraph))
    hotelsSearch.start()
    hotelsSearch.join()

    
    #TODO
    activitiesGraph = Graph()
    activitiesSearch = Process(target=search_activities, args=(q4, destination, festive, cultural, playful, 3, startDate, endDate, activitiesGraph))
    activitiesSearch.start()
    activitiesSearch.join()


    resultOutboundFlight = q1.get()
    resultReturnFlight = q2.get()
    resultHotels = q3.get()
    resultActivities = q4.get()

    
    result = Graph()


    print("Inicio planificacion")
    #Afegim hotel seleccionat
    subject_hotel= onto.HotelSeleccionat
    hotelsSortedPrice = sorted(resultHotels,key=lambda hotel:hotel.get("price"))
    rangActivitats=0
    print("HOTELS SORTED PRICE: " + hotelsSortedPrice[1].get("price"))
    if float(hotelsSortedPrice[1].get("price"))>int(budget)/4:
        print("LLEGA HASTA AQUI")
        chosenHotel = sorted(resultHotels,key=lambda hotel:hotel.get("price"))[1]
        rangActivitats="1"
    elif float(hotelsSortedPrice[int(len(hotelsSortedPrice)/2)].get("price"))>int(budget)/4:
        print("LLEGA HASTA AQUI TMB")
        chosenHotel = sorted(resultHotels,key=lambda hotel:hotel.get("price"))[int(len(hotelsSortedPrice)/4)]
        rangActivitats="2"
    else:
        chosenHotel = sorted(resultHotels,key=lambda hotel:hotel.get("price"))[random.randrange(1,len(hotelsSortedPrice))]
        rangActivitats="3"
    result.add((subject_hotel, RDF.type, ONTO.Hotel))
    result.add((subject_hotel, ONTO.price, Literal(chosenHotel.get("price"), datatype=XSD.float)))
    result.add((subject_hotel, ONTO.id, Literal(chosenHotel.get("id"), datatype=XSD.string)))
    result.add((subject_hotel, ONTO.name, Literal(chosenHotel.get("name"), datatype=XSD.string)))
    result.add((subject_hotel, ONTO.location, Literal(chosenHotel.get("location"), datatype=XSD.string)))

    print("ARA FEM VOLS")
    #Afegim vol anada seleccionat
    subject_lodging_flight= onto.VolAnadaSeleccionat
    chosenLodgingFlight = sorted(resultOutboundFlight,key=lambda hotel:hotel.get("price"))[1]
    result.add((subject_lodging_flight, RDF.type, ONTO.Flight))
    result.add((subject_lodging_flight, ONTO.price, Literal(chosenLodgingFlight.get("price"), datatype=XSD.float)))
    result.add((subject_lodging_flight, ONTO.id, Literal(chosenLodgingFlight.get("id"), datatype=XSD.string)))
    result.add((subject_lodging_flight, ONTO.start, Literal(chosenLodgingFlight.get("startDate"), datatype=XSD.string)))
    result.add((subject_lodging_flight, ONTO.end, Literal(chosenLodgingFlight.get("endDate"), datatype=XSD.string)))
    result.add((subject_lodging_flight, ONTO.duration, Literal(chosenLodgingFlight.get("duration"), datatype=XSD.string)))
    
    #Afegim vol tornada seleccionat
    subject_return_flight= onto.VolTornadaSeleccionat
    chosenReturnFlight = sorted(resultReturnFlight,key=lambda hotel:hotel.get("price"))[1]
    result.add((subject_return_flight, RDF.type, ONTO.Flight))
    result.add((subject_return_flight, ONTO.price, Literal(chosenReturnFlight.get("price"), datatype=XSD.float)))
    result.add((subject_return_flight, ONTO.id, Literal(chosenReturnFlight.get("id"), datatype=XSD.string)))
    result.add((subject_return_flight, ONTO.start, Literal(chosenReturnFlight.get("startDate"), datatype=XSD.string)))
    result.add((subject_return_flight, ONTO.end, Literal(chosenReturnFlight.get("endDate"), datatype=XSD.string)))
    result.add((subject_return_flight, ONTO.duration, Literal(chosenReturnFlight.get("duration"), datatype=XSD.string)))

    print("PUNTO DE CONTROL 0")
    actividades_count = 0
    #1 = 1 actividad al dia de mañana o tarde
    #2 = 1 actividad al dia de mañana o tarde y otra de tanto en tanto de mañana o tarde o noche
    #3 = 1 actividad al dia de mañana, 1 actividad al dia de tarde y de tanto en tanto 1 actividad de noche

    actividadesMañanaOcio = []
    for activity in resultActivities:
        print("De momento entra")
        aux = activity is not None
        print("es: " + str(aux))
        try:
            if activity is not None and "Mati" in activity.get("schedule") and "Ocio" in activity.get("type") and activity.get("priceLevel") <= rangActivitats:
                print("antes del append")
                actividadesMañanaOcio.append(activity)
                print("despues del append")
        except:
            pass

    actividadesTardeOcio = []
    for activity in resultActivities:
        print("De momento entra")
        aux = activity is not None
        print("es: " + str(aux))
        try:
            if activity is not None and "Tarda" in activity.get("schedule") and "Ocio" in activity.get("type") and activity.get("priceLevel") <= rangActivitats:
                print("antes del append")
                actividadesTardeOcio.append(activity)
                print("despues del append")
        except:
            pass

    actividadesNocheOcio = []
    for activity in resultActivities:
        print("De momento entra")
        aux = activity is not None
        print("es: " + str(aux))
        try:
            if activity is not None and "Nocturna" in activity.get("schedule") and "Ocio" in activity.get(
                    "type") and activity.get("priceLevel") <= rangActivitats:
                print("antes del append")
                actividadesNocheOcio.append(activity)
                print("despues del append")
        except:
            pass


    print("POR AQUI PASA")

    actividadesMañanaCultural = []
    for activity in resultActivities:
        print("De momento entra")
        aux = activity is not None
        print("es: " + str(aux))
        try:
            if activity is not None and "Mati" in activity.get("schedule") and "Cultural" in activity.get(
                    "type") and activity.get("priceLevel") <= rangActivitats:
                print("antes del append")
                actividadesMañanaCultural.append(activity)
                print("despues del append")
        except:
            pass

    actividadesTardeCultural = []
    for activity in resultActivities:
        print("De momento entra")
        aux = activity is not None
        print("es: " + str(aux))
        try:
            if activity is not None and "Tarda" in activity.get("schedule") and "Cultural" in activity.get(
                    "type") and activity.get("priceLevel") <= rangActivitats:
                print("antes del append")
                actividadesTardeCultural.append(activity)
                print("despues del append")
        except:
            pass

    actividadesNocheCultural = []
    for activity in resultActivities:
        print("De momento entra")
        aux = activity is not None
        print("es: " + str(aux))
        try:
            if activity is not None and "Nocturna" in activity.get("schedule") and "Cultural" in activity.get(
                    "type") and activity.get("priceLevel") <= rangActivitats:
                print("antes del append")
                actividadesNocheCultural.append(activity)
                print("despues del append")
        except:
            pass


    print("PUNTO DE CONTROL 0.5")
    numeroOcio=0
    numeroCultural=0

    start = datetime.strptime(startDate, '%Y-%m-%d')
    end = datetime.strptime(endDate, '%Y-%m-%d')
    days = (end - start).days

    cargaActividades= random.randrange(1,4)
    diasViaje = days
    print("PUNTO DE CONTROL 1")
    for dia in range(0,diasViaje):
        actividades_count += 1
        if cargaActividades == 1:
            if float(numeroOcio)/float(playful) <= float(numeroCultural)/float(cultural):
                chosenActivity = (actividadesMañanaOcio+actividadesTardeOcio)[random.randrange(0,len((actividadesMañanaOcio+actividadesTardeOcio)))]
                numeroOcio+=1
            else:
                chosenActivity = (actividadesMañanaCultural+actividadesTardeCultural)[random.randrange(0,len((actividadesMañanaCultural+actividadesTardeCultural)))]
                numeroCultural+=1
            subject_actividades = URIRef("http://www.owl-ontologies.com/OntologiaECSDI.owl#ActividadSeleccionada" + str(actividades_count))
            result.add((subject_actividades, RDF.type, ONTO.Activity))
            result.add((subject_actividades, ONTO.name, Literal(chosenActivity.get("name"), datatype=XSD.string)))
            result.add((subject_actividades, ONTO.priceLevel, Literal(chosenActivity.get("priceLevel"), datatype=XSD.integer)))
            result.add((subject_actividades, ONTO.type, Literal(chosenActivity.get("type"), datatype=XSD.string)))
            result.add((subject_actividades, ONTO.schedule, Literal(chosenActivity.get("schedule"), datatype=XSD.string)))
        elif cargaActividades==2:
            if float(numeroOcio)/float(playful) <= float(numeroCultural)/float(cultural):
                chosenActivity = (actividadesMañanaOcio)[random.randrange(0,len((actividadesMañanaOcio)))]
                numeroOcio+=1
            else:
                chosenActivity = (actividadesMañanaCultural)[random.randrange(0,len((actividadesMañanaCultural)))]
                numeroCultural+=1
            subject_actividades = URIRef("http://www.owl-ontologies.com/OntologiaECSDI.owl#ActividadSeleccionada" + str(actividades_count))
            result.add((subject_actividades, RDF.type, ONTO.Activity))
            result.add((subject_actividades, ONTO.name, Literal(chosenActivity.get("name"), datatype=XSD.string)))
            result.add((subject_actividades, ONTO.priceLevel, Literal(chosenActivity.get("priceLevel"), datatype=XSD.integer)))
            result.add((subject_actividades, ONTO.type, Literal(chosenActivity.get("type"), datatype=XSD.string)))
            result.add((subject_actividades, ONTO.schedule, Literal(chosenActivity.get("schedule"), datatype=XSD.string)))
            actividades_count+=1
                
            if float(numeroOcio)/float(playful) <= float(numeroCultural)/float(cultural):
                chosenActivity = (actividadesTardeOcio)[random.randrange(0,len((actividadesTardeOcio)))]
                numeroOcio+=1
            else:
                chosenActivity = (actividadesTardeCultural)[random.randrange(0,len((actividadesTardeCultural)))]
                numeroCultural+=1

            print("PUNTO DE CONTROL 2")
            subject_actividades = URIRef("http://www.owl-ontologies.com/OntologiaECSDI.owl#ActividadSeleccionada" + str(actividades_count))
            result.add((subject_actividades, RDF.type, ONTO.Activity))
            result.add((subject_actividades, ONTO.name, Literal(chosenActivity.get("name"), datatype=XSD.string)))
            result.add((subject_actividades, ONTO.priceLevel, Literal(chosenActivity.get("priceLevel"), datatype=XSD.integer)))
            result.add((subject_actividades, ONTO.type, Literal(chosenActivity.get("type"), datatype=XSD.string)))
            result.add((subject_actividades, ONTO.schedule, Literal(chosenActivity.get("schedule"), datatype=XSD.string)))
            
        else:
            if float(numeroOcio)/float(playful) <= float(numeroCultural)/float(cultural):
                chosenActivity = (actividadesMañanaOcio)[random.randrange(0,len((actividadesMañanaOcio)))]
                numeroOcio+=1
            else:
                chosenActivity = (actividadesMañanaCultural)[random.randrange(0,len((actividadesMañanaCultural)))]
                numeroCultural+=1
            subject_actividades = URIRef("http://www.owl-ontologies.com/OntologiaECSDI.owl#ActividadSeleccionada" + str(actividades_count))
            result.add((subject_actividades, RDF.type, ONTO.Activity))
            result.add((subject_actividades, ONTO.name, Literal(chosenActivity.get("name"), datatype=XSD.string)))
            result.add((subject_actividades, ONTO.priceLevel, Literal(chosenActivity.get("priceLevel"), datatype=XSD.integer)))
            result.add((subject_actividades, ONTO.type, Literal(chosenActivity.get("type"), datatype=XSD.string)))
            result.add((subject_actividades, ONTO.schedule, Literal(chosenActivity.get("schedule"), datatype=XSD.string)))
            actividades_count+=1
                
            if float(numeroOcio)/float(playful) <= float(numeroCultural)/float(cultural):
                chosenActivity = (actividadesTardeOcio)[random.randrange(0,len((actividadesTardeOcio)))]
                numeroOcio+=1
            else:
                chosenActivity = (actividadesTardeCultural)[random.randrange(0,len((actividadesTardeCultural)))]
                numeroCultural+=1
                
            subject_actividades = URIRef("http://www.owl-ontologies.com/OntologiaECSDI.owl#ActividadSeleccionada" + str(actividades_count))
            result.add((subject_actividades, RDF.type, ONTO.Activity))
            result.add((subject_actividades, ONTO.name, Literal(chosenActivity.get("name"), datatype=XSD.string)))
            result.add((subject_actividades, ONTO.priceLevel, Literal(chosenActivity.get("priceLevel"), datatype=XSD.integer)))
            result.add((subject_actividades, ONTO.type, Literal(chosenActivity.get("type"), datatype=XSD.string)))
            result.add((subject_actividades, ONTO.schedule, Literal(chosenActivity.get("schedule"), datatype=XSD.string)))
            
            if float(numeroOcio)/float(playful) <= float(numeroCultural)/float(cultural):
                chosenActivity = (actividadesNocheOcio)[random.randrange(0,len((actividadesNocheOcio)))]
                numeroOcio+=1
            else:
                chosenActivity = (actividadesNocheCultural)[random.randrange(0,len((actividadesNocheCultural)))]
                numeroCultural+=1
                
            subject_actividades = URIRef("http://www.owl-ontologies.com/OntologiaECSDI.owl#ActividadSeleccionada" + str(actividades_count))
            result.add((subject_actividades, RDF.type, ONTO.Activity))
            result.add((subject_actividades, ONTO.name, Literal(chosenActivity.get("name"), datatype=XSD.string)))
            result.add((subject_actividades, ONTO.priceLevel, Literal(chosenActivity.get("priceLevel"), datatype=XSD.integer)))
            result.add((subject_actividades, ONTO.type, Literal(chosenActivity.get("type"), datatype=XSD.string)))
            result.add((subject_actividades, ONTO.schedule, Literal(chosenActivity.get("schedule"), datatype=XSD.string)))

    print("Final planificacion")
    print(result.serialize(format="turtle"))
    return result

def search_hotels(queue, city, location, budget, hotelsGraph):

    global mss_cnt
    
    logger.info('Inici Buscar Hotels')

    print("minPrice: " + str(1))
    # Search in the directory for an Hotel agent
    typeResponse = directory_search_message(DSO.HotelsAgent)
    
    
    responseGraph = typeResponse.value(predicate=RDF.type, object=ACL.FipaAclMessage)
    content = typeResponse.value(subject=responseGraph, predicate=ACL.content)
    hotelAgentAddres = typeResponse.value(subject=content, predicate=DSO.Address)
    hotelAgentUri = typeResponse.value(subject=content, predicate=DSO.Uri)

    messageGraph = Graph()

    hotelsRequestObj = onto['HotelRequest_' + str(mss_cnt)]
    
    messageGraph.add((hotelsRequestObj, RDF.type, ONTO.HotelRequest))
    
    # Add the city
    dest = onto[city]
    messageGraph.add((dest, RDF.type, ONTO.City))
    messageGraph.add((dest, ONTO.name, Literal(city)))
    messageGraph.add((hotelsRequestObj, ONTO.destination, dest))
    
    minPrice = 1
    maxPrice = budget
    if minPrice:
        messageGraph.add((hotelsRequestObj, ONTO.minPrice, Literal(minPrice)))
    if maxPrice:
        messageGraph.add((hotelsRequestObj, ONTO.maxPrice, Literal(maxPrice)))
    if location:
        messageGraph.add((hotelsRequestObj, ONTO.location, Literal(location)))
    
    msg = build_message(gmess=messageGraph, perf=ACL.request, sender= TravelServiceAgent.uri, receiver=hotelAgentUri, content=hotelsRequestObj, msgcnt= mss_cnt)
    mss_cnt += 1
    
    logger.info('Enviar Buscar Hotels')
    hotelsGraph = send_message(msg, hotelAgentAddres)
    logger.info('Rebre Buscar Hotels')
    
    hotels_list = []
    subjects_position = {}
    pos = 0
    
    responseGraph = hotelsGraph.value(predicate=RDF.type, object=ACL.FipaAclMessage)
    
    #print(hotelsGraph.serialize(format="turtle"))
    
    for s, p, o in hotelsGraph:
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
            if p == ONTO.name:
                hotel['name'] = o
            if p == ONTO.price:
                hotel['price'] = o
            if p == ONTO.location:
                hotel["location"] = o

    # Imprimir hotels_list
    for hotel in hotels_list:
        print("--- Hotel ---")
        print("ID:", hotel.get('id'))
        print("Nom:", hotel.get('name'))
        print("Preu:", hotel.get('price'))
        print("Localitzacio:", hotel.get('location'))
        print("---------------------")
    logger.info('Fi Buscar hotels')

    queue.put(hotels_list)
    return hotels_list

def search_flights(queue, origin, destination, date, budget, flightsGraph):
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
    if str(origin) == "Barcelona":
        messageGraph.add((ori, ONTO.code, Literal("BCN")))
        print("BCN")
    elif str(origin) == "London":
        messageGraph.add((ori, ONTO.code, Literal("LON")))
        print("LON")
    elif str(origin) == "Madrid":
        messageGraph.add((ori, ONTO.code, Literal("MAD")))
        print("MAD")
    else:
        print("no equal")
    messageGraph.add((dest, RDF.type, ONTO.City))
    messageGraph.add((dest, ONTO.name, Literal(destination)))
    if str(destination) == "Barcelona":
        messageGraph.add((dest, ONTO.code, Literal("BCN")))
        print("BCN")
    elif str(destination) == "London":
        messageGraph.add((dest, ONTO.code, Literal("LON")))
        print("LON")
    elif str(destination) == "Madrid":
        messageGraph.add((dest, ONTO.code, Literal("MAD")))
        print("MAD")
    else:
        print("no equal")
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

    queue.put(flights_list)
    return flights_list
    
def search_activities(queue, city, festive, cultural, playful, priceLevel, start, end, activitiesGraph):
    global mss_cnt
    
    # Search in the directory for an Activities agent
    typeResponse = directory_search_message(DSO.ActivitiesAgent)
    
    responseGraph = typeResponse.value(predicate=RDF.type, object=ACL.FipaAclMessage)
    content = typeResponse.value(subject=responseGraph, predicate=ACL.content)
    activitiesAgentAddres = typeResponse.value(subject=content, predicate=DSO.Address)
    activitiesAgentUri = typeResponse.value(subject=content, predicate=DSO.Uri)

    messageGraph = Graph()
    
    activitiesRequestObj = onto['ActivitiesRequest_' + str(mss_cnt)]
    messageGraph.add((activitiesRequestObj, RDF.type, ONTO.ActivitiesRequest))
    
    # Add the city
    dest = onto[city]
    messageGraph.add((dest, RDF.type, ONTO.City))
    messageGraph.add((dest, ONTO.name, Literal(city)))
    messageGraph.add((activitiesRequestObj, ONTO.destination, dest))





    # Add the days
    # TODO: calculate the days
    startDate = datetime.strptime(start, '%Y-%m-%d')
    endDate = datetime.strptime(end, '%Y-%m-%d')
    days = (endDate-startDate).days
    messageGraph.add((activitiesRequestObj, ONTO.days, Literal(str(days))))
    
    # Add the price level
    # TODO: calculate the price level
    messageGraph.add((activitiesRequestObj, ONTO.priceLevel, Literal(priceLevel)))
    
    # Add cultural-festive
    # TODO: calculate precentages
    culturalPercentage = int(cultural)/10
    festivePrecentage = int(festive)/10
    messageGraph.add((activitiesRequestObj, ONTO.cultural, Literal(culturalPercentage)))
    messageGraph.add((activitiesRequestObj, ONTO.festive, Literal(festivePrecentage)))
    
    
    msg = build_message(gmess=messageGraph, perf=ACL.request, sender= TravelServiceAgent.uri, receiver=activitiesAgentUri, content=activitiesRequestObj, msgcnt= mss_cnt)

    mss_cnt += 1
    
    logger.info('Search activities')
    activitiesGraph = send_message(msg, activitiesAgentAddres)
    logger.info('Recive activities')
    
    activities_list = []
    subjects_position = {}
    pos = 0

    #print(activitiesGraph.serialize(format="turtle"))

    for s, p, o in activitiesGraph:
        if s not in subjects_position:
            subjects_position[s] = pos
            pos += 1
            activities_list.append({})
        if s in subjects_position:
            activity = activities_list[subjects_position[s]]
            if p == RDF.type:
                activity['url'] = s
            if p == ONTO.name:
                activity['name'] = o
            if p == ONTO.priceLevel:
                activity['priceLevel'] = o
            if p == ONTO.type:
                activity['type'] = o
            if p == ONTO.schedule:
                activity["schedule"] = o

    # Imprimir flights_list
    for activity in activities_list:
        print("--- Activitats ---")
        print("Nom:", activity.get('name'))
        print("Nivell de preu:", activity.get('priceLevel'))
        print("Tipus:", activity.get('type'))
        print("Schedule:", activity.get('schedule'))
        print("---------------------")

    logger.info('Fi Buscar Activitats')

    queue.put(activities_list)
    return activities_list

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
