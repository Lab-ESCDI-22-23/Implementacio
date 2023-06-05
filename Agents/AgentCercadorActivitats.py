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

from multiprocessing import Process, Queue
import logging
import argparse
import sys
import socket

from flask import Flask, render_template, request
from AgentUtil.FlaskServer import shutdown_server
from AgentUtil.Logging import config_logger
from AgentUtil.Util import gethostname

from AgentUtil.ACLMessages import *
from AgentUtil.Agent import Agent
from rdflib import Graph, Literal, RDF, URIRef, XSD, Namespace, Dataset
from rdflib.namespace import FOAF, RDF

from AgentUtil.ACL import ACL
from AgentUtil.DSO import DSO
from AgentUtil.ONTO import ONTO


FUSEKI_ENDPOINT = 'http://localhost:3030/MC_activitats'

CACHE_FILE = "./Data/cache_activitats"


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
        port = 9013
    else:
        port = args.port

    if args.open:
        hostname = '0.0.0.0'
        hostaddr = gethostname()
    else:
        hostaddr = hostname = socket.gethostname()

    print('DS Hostaddres =', hostaddr)
    print('DS Hostname =', hostname)
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


agn = Namespace("http://www.agentes.org#")
onto = Namespace("http://www.owl-ontologies.com/OntologiaECSDI.owl#")

# Contador de mensajes
mss_cnt = 0

CACHE_FILE = "./Data/cache_activitats"

# Datos del Agente
ActivitiesAgent = Agent('ActivitiesAgent',
                       agn.ActivitiesAgent,
                       'http://%s:%d/comm' % (hostaddr, port),
                       'http://%s:%d/Stop' % (hostaddr, port))

# Directory agent address
DirectoryAgent = Agent('DirectoryAgent',
                    agn.Directory,
                    'http://%s:%d/Register' % (dhostname, dport),
                    'http://%s:%d/Stop' % (dhostname, dport))

# Global triplestore graph
dsgraph = Graph()

cola1 = Queue()

# Queue that waits for a 0 to end the agent
endQueue = Queue()


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

    reg_obj = agn[ActivitiesAgent.name + '-Register']
    gmess.add((reg_obj, RDF.type, DSO.Register))
    gmess.add((reg_obj, DSO.Uri, ActivitiesAgent.uri))
    gmess.add((reg_obj, FOAF.name, Literal(ActivitiesAgent.name)))
    gmess.add((reg_obj, DSO.Address, Literal(ActivitiesAgent.address)))
    gmess.add((reg_obj, DSO.AgentType, DSO.ActivitiesAgent))

    # Lo metemos en un envoltorio FIPA-ACL y lo enviamos
    gr = send_message(
        build_message(gmess, perf=ACL.request,
                      sender=ActivitiesAgent.uri,
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
        gr = build_message(Graph(), ACL['not-understood'], sender=ActivitiesAgent.uri, msgcnt=get_count())


    else:
        # Obtenemos la performativa
        if msgdic['performative'] != ACL.request:
            print('Mensaje no es request')
            # Si no es un request, respondemos que no hemos entendido el mensaje
            gr = build_message(Graph(),
                               ACL['not-understood'],
                               sender=ActivitiesAgent.uri,
                               msgcnt=get_count())

        else:
            # Get the action of the request
            content = msgdic['content']
            # Averiguamos el tipo de la accion
            accion = gm.value(subject=content, predicate=RDF.type)

            # Activities Request
            if accion == ONTO.ActivitiesRequest:
                logger.info("Activities request recived")
                
                messageGraph = resolve_request(gm)
                
                gr = build_message(messageGraph,
                                    ACL['inform'],
                                    sender=ActivitiesAgent.uri,
                                    msgcnt=get_count())
            else:
                print('Accio no reconeguda')
                gr = build_message(Graph(),
                                    ACL['not-understood'],
                                    sender=ActivitiesAgent.uri,
                                    msgcnt=get_count())

    return gr.serialize(format='xml'), 200

def resolve_request(activitiesRequestGraph: Graph):
    """
    Given the request graph, extracts the information and makes the request
    """
    msgdic = get_message_properties(activitiesRequestGraph)
    content = msgdic['content']

    # Get the date and the max price
    cultural = activitiesRequestGraph.value(subject=content, predicate=ONTO.cultural)
    festive = activitiesRequestGraph.value(subject=content, predicate=ONTO.festive)
    days = activitiesRequestGraph.value(subject=content, predicate=ONTO.days)
    destination = activitiesRequestGraph.value(subject=content, predicate=ONTO.destination)
    priceLevel = activitiesRequestGraph.value(subject=content, predicate=ONTO.priceLevel)
    print("Cultural: " + str(cultural))
    print("Festive: " + str(festive))
    print("Destination: " + str(destination))
    print("Days: " + str(days))
    
    return activities_seach(ciudad_destino=destination, nivel_precio=priceLevel, dias_viaje=days, proporcion_ludico_festiva=festive, proporcion_cultural=cultural)


def buscar_actividades_festivas(ciudad="Barcelona"):

    urls = [
        "https://maps.googleapis.com/maps/api/place/textsearch/json?query=discoteca%20en%20" + ciudad + "&key=AIzaSyBX1DSnnWxD6s-t9_YzjtpbrPbPYcXJxoA", #Nit
        "https://maps.googleapis.com/maps/api/place/textsearch/json?query=actividades%20ocio%20" + ciudad + "&key=AIzaSyBX1DSnnWxD6s-t9_YzjtpbrPbPYcXJxoA", #Mati-Tarda
        "https://maps.googleapis.com/maps/api/place/textsearch/json?query=parque%20atracciones%20zoo%20" + ciudad + "&key=AIzaSyBX1DSnnWxD6s-t9_YzjtpbrPbPYcXJxoA", #Mati-Tarda
        "https://maps.googleapis.com/maps/api/place/textsearch/json?query=bar%20cine%20" + ciudad + "&key=AIzaSyBX1DSnnWxD6s-t9_YzjtpbrPbPYcXJxoA" #Tarda-Nit
    ]

    results = []
    time = ["Nocturna", "Mati-Tarda", "Mati-Tarda", "Nocturna-Tarda"]
    for i, url in enumerate(urls):
        response = requests.get(url)
        data = response.json()

        for item in data.get("results", []):
            name = item.get("name")
            price_level = item.get("price_level", "-1")
            result = {"name": name, "price_level": price_level, "time": time[i], "type": "Ocio"}
            results.append(result)


    print("FIN LLAMADA API - TODO OK")
    return results


def buscar_actividades_culturales(ciudad="Barcelona"):

    urls = [
        "https://maps.googleapis.com/maps/api/place/textsearch/json?query=teatre%20culturals%20" + ciudad + "&key=AIzaSyBX1DSnnWxD6s-t9_YzjtpbrPbPYcXJxoA", #Nit
        "https://maps.googleapis.com/maps/api/place/textsearch/json?query=restaurantes%20" + ciudad + "&key=AIzaSyBX1DSnnWxD6s-t9_YzjtpbrPbPYcXJxoA",  #tarda-nit
        "https://maps.googleapis.com/maps/api/place/textsearch/json?query=museos%20en%20" + ciudad + "&key=AIzaSyBX1DSnnWxD6s-t9_YzjtpbrPbPYcXJxoA", #tarda-mati
        "https://maps.googleapis.com/maps/api/place/textsearch/json?query=iglesia%20catedrales%20importantes%20" + ciudad + "&key=AIzaSyBX1DSnnWxD6s-t9_YzjtpbrPbPYcXJxoA", #tarda-mati
        "https://maps.googleapis.com/maps/api/place/textsearch/json?query=monumentos%20importantes%20" + ciudad + "&key=AIzaSyBX1DSnnWxD6s-t9_YzjtpbrPbPYcXJxoA", #tarda-mati
        "https://maps.googleapis.com/maps/api/place/textsearch/json?query=sitios%20importantes%20" + ciudad + "&key=AIzaSyBX1DSnnWxD6s-t9_YzjtpbrPbPYcXJxoA" #tarda-mati
    ]

    results = []

    time = ["Nocturna", "Nocturna-Tarda", "Mati-Tarda", "Mati-Tarda", "Mati-Tarda", "Mati-Tarda"]

    for i, url in enumerate(urls):
        response = requests.get(url)
        data = response.json()

        for item in data.get("results", []):
            name = item.get("name")
            price_level = item.get("price_level", "-1")
            result = {"name": name, "price_level": price_level, "time": time[i], "type": "Cultural"}
            results.append(result)

    print("FIN LLAMADA API - TODO OK")
    return results


def guardar_cache(cache, ciudad_destino=""):
    actividades_count = 0
    g = Graph()

    guardar_estado_cache(ciudad_destino)

    for result in cache:
        actividades_count += 1
        subject_actividades = URIRef("http://www.owl-ontologies.com/OntologiaECSDI.owl#Actividad" + str(actividades_count))
        name = result['name']
        price_level = result['price_level']
        time = result['time']
        type = result['type']
        g.add((subject_actividades, RDF.type, ONTO.Activity))
        g.add((subject_actividades, ONTO.name, Literal(name, datatype=XSD.string)))
        g.add((subject_actividades, ONTO.price, Literal(price_level, datatype=XSD.integer)))
        g.add((subject_actividades, ONTO.schedule, Literal(time, datatype=XSD.string)))
        g.add((subject_actividades, ONTO.type, Literal(type, datatype=XSD.string)))

    # Actualización de los datos en Fuseki
    subject_cabeceraMC = URIRef("http://www.owl-ontologies.com/OntologiaECSDI.owl#CabeceraMC")
    g.add((subject_cabeceraMC, RDF.type, ONTO.CabeceraMC))
    g.add((subject_cabeceraMC, ONTO.on, Literal(ciudad_destino, datatype=XSD.string)))

    # Borrar el contenido previo en Fuseki
    delete_query = """
            DELETE {
                GRAPH <http://www.owl-ontologies.com/OntologiaECSDI.owl> {
                    ?s ?p ?o .
                }
            }
            WHERE {
                GRAPH <http://www.owl-ontologies.com/OntologiaECSDI.owl> {
                    ?s ?p ?o .
                }
            }
        """
    requests.post(f"{FUSEKI_ENDPOINT}/update", data=delete_query.encode())

    # Guardar los nuevos datos en Fuseki
    g.serialize(destination=None, format='xml')  # Serializar el grafo en formato XML

    update_query = f"""
        INSERT DATA {{
            GRAPH <http://www.owl-ontologies.com/OntologiaECSDI.owl> {{
                {g.serialize(format='nt')}  # Obtener la representación N-Triples del grafo
            }}
        }}
    """

    # Enviar la actualización a Fuseki mediante una consulta SPARQL
    response = requests.post(f"{FUSEKI_ENDPOINT}/update", data=update_query.encode())

    if response.status_code == 200:
        print("Datos guardados exitosamente en Fuseki.")
    else:
        print("Error al guardar los datos en Fuseki:", response.text)



def leer_cache(proporcion_ludico_festiva=0.5, proporcion_cultural=0.5):

    # Consulta SPARQL para obtener los datos del grafo en Fuseki
    query = """
        prefix default:<http://www.owl-ontologies.com/OntologiaECSDI.owl#>
        prefix rdf:<http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        SELECT ?actividad ?nombre ?precio ?time ?type
        WHERE {
            GRAPH <http://www.owl-ontologies.com/OntologiaECSDI.owl> {
                { ?actividad rdf:type default:Actividad}.
                ?actividad default:NombreActividad ?nombre .
                ?actividad default:NivelPrecio ?precio .
                ?actividad default:Horario ?time .
                ?actividad default:TipoActividad ?type .   
            
    """

    if(proporcion_ludico_festiva != 0 and proporcion_cultural == 0):
        query += """FILTER( str(?type) = 'Ocio')}}"""
    elif(proporcion_ludico_festiva == 0 and proporcion_cultural != 0):
        query += """FILTER( str(?type) = 'Cultural')}}"""
    else:
        query +="""}}"""

    # Realizar la consulta SPARQL a Fuseki
    response = requests.post(f"{FUSEKI_ENDPOINT}/query", data={"query": query})

    if response.status_code == 200:
        # Parsear la respuesta en formato JSON
        results = response.json()

        # Obtener los datos de los resultados
        bindings = results.get("results", {}).get("bindings", [])
        resultados = []
        for binding in bindings:
            nombre = binding.get("nombre", {}).get("value", "")
            precio = int(binding.get("precio", {}).get("value", ""))
            time = binding.get("time", {}).get("value", "")
            type = binding.get("type", {}).get("value", "")
            resultados.append({"name": nombre, "price_level": precio, "time": time, "type": type})

        return resultados
    else:
        print("Error al leer los datos de Fuseki:", response.text)
        return []


def guardar_estado_cache(ciudad_destino=""):
    with open(CACHE_FILE, "w+") as file:
        file.truncate(0)  # Borrar contenido inicial del archivo
        file.write(ciudad_destino + "\n")

def leer_estado_cache():
    with open(CACHE_FILE, "r") as file:
        return file.readline().strip()

def activities_seach(ciudad_destino="Barcelona", nivel_precio=2, dias_viaje=0, proporcion_ludico_festiva=0.5, proporcion_cultural=0.5):

        print("nivel precio: " + str(nivel_precio))
        print("dias viaje: " + str(dias_viaje))
        print("Proporcion ludido y festiva: " + str(proporcion_ludico_festiva))
        print("Proporcion cultural: " + str(proporcion_cultural))

        #if (leer_estado_cache() == ciudad_destino):
        if (0):
            print("ACCES A CACHE")
            actividades_totales = leer_cache(proporcion_ludico_festiva, proporcion_cultural)

        else:
            print("ACCES A API")
            actividades_ludico_festivas = buscar_actividades_festivas(ciudad_destino)
            actividades_culturales = buscar_actividades_culturales(ciudad_destino)
            guardar_cache(actividades_ludico_festivas + actividades_culturales, ciudad_destino)
            if (proporcion_ludico_festiva != 0 and proporcion_cultural != 0): actividades_totales = actividades_ludico_festivas + actividades_culturales
            elif (proporcion_ludico_festiva == 0 and proporcion_cultural != 0): actividades_totales = actividades_culturales
            elif (proporcion_ludico_festiva != 0 and proporcion_cultural == 0): actividades_totales = actividades_ludico_festivas



        actividades_filtradas = [actividad for actividad in actividades_totales if int(actividad["price_level"]) <= nivel_precio]

        result = Graph()
        actividades_count = 0

        for consulta in actividades_filtradas:
            name = consulta["name"]
            price_level = consulta["price_level"]
            print("Nombre: " + name)
            print("Price level: " + str(price_level))
            time = consulta["time"]
            print("Este es el horario: " + time)
            tipo = consulta["type"]
            print("Tipo Actividad: " + tipo)
            print("--------------")

            actividades_count += 1
            subject_actividades = URIRef("http://www.owl-ontologies.com/OntologiaECSDI.owl#Activity" + str(actividades_count))
            result.add((subject_actividades, RDF.type, ONTO.Activity))
            result.add((subject_actividades, ONTO.name, Literal(name, datatype=XSD.string)))
            result.add((subject_actividades, ONTO.price, Literal(price_level, datatype=XSD.integer)))

        print("FIN CONSTRUCCION - TODO OK - ENVIANDO GRAFO")
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

