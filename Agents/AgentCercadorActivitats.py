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

CACHE_FILE = "./Data/cache_activitats"

# Datos del Agente
AgenteActividades = Agent('AgenteActividades',
                       agn.AgentSimple,
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
        gr = build_message(Graph(), ACL['not-understood'], sender=AgenteActividades.uri, msgcnt=get_count())


    else:
        # Obtenemos la performativa
        if msgdic['performative'] != ACL.request:
            print('Mensaje no es request')
            # Si no es un request, respondemos que no hemos entendido el mensaje
            gr = build_message(Graph(),
                               ACL['not-understood'],
                               sender=AgenteActividades.uri,
                               msgcnt=get_count())

        else:
            # Extraemos el objeto del contenido que ha de ser una accion de la ontologia
            # de registro
            print('Mensaje puede ser accion de onto')
            content = msgdic['content']
            # Averiguamos el tipo de la accion
            accion = gm.value(subject=content, predicate=RDF.type)

            # Accion de buscar productos
            if accion == ONTO.BuscarActividades:
                print("Works here")
                restriccions = gm.objects(content, ONTO.RestringidaPor)
                restriccions_dict = {}
                # Per totes les restriccions que tenim en la cerca d'hotels
                for restriccio in restriccions:
                    if gm.value(subject=restriccio, predicate=RDF.type) == ONTO.RestriccionNivelCarga:
                        carga_actividades = gm.value(subject=restriccio, predicate=ONTO.CargaActividades)
                        print('BÚSQUEDA->Restriccion de carga de actividades: ' + carga_actividades)
                        restriccions_dict['carga_actividades'] = carga_actividades

                    elif gm.value(subject=restriccio, predicate=RDF.type) == ONTO.RestriccionNivelPrecio:
                        nivel_precio = gm.value(subject=restriccio, predicate=ONTO.NivelPrecio)
                        print('BÚSQUEDA->Restriccion de nivel de precio:' + nivel_precio)
                        restriccions_dict['nivel_precio'] = nivel_precio


                    elif gm.value(subject=restriccio, predicate=RDF.type) == ONTO.RestriccionDias:
                        dias_viaje = gm.value(subject=restriccio, predicate=ONTO.DiasViaje)
                        print('BÚSQUEDA->Restriccion de dias de viaje: ' + dias_viaje)
                        restriccions_dict['dias_viaje'] = dias_viaje

                    elif gm.value(subject=restriccio, predicate=RDF.type) == ONTO.RestriccionProporcionActividades:
                        proporcion_ludico_festiva = gm.value(subject=restriccio, predicate=ONTO.ProporcionLudicoFestiva)
                        proporcion_cultural = gm.value(subject=restriccio, predicate=ONTO.ProporcionCultural)


                        print('BÚSQUEDA->Restriccion de proporcion ludica y festiva: ' + proporcion_ludico_festiva)
                        print('BÚSQUEDA->Restriccion de proporcion cultural: ' + proporcion_cultural)
                        restriccions_dict['proporcion_ludico_festiva'] = proporcion_ludico_festiva
                        restriccions_dict['proporcion_cultural'] = proporcion_cultural


                gr = buscar_actividades(**restriccions_dict)

    return gr.serialize(format='xml'), 200


def buscar_actividades_festivas(ciudad="Barcelona"):

    urls = [
        "https://maps.googleapis.com/maps/api/place/textsearch/json?query=discoteca%20en%20" + ciudad + "&key=AIzaSyBX1DSnnWxD6s-t9_YzjtpbrPbPYcXJxoA", #Nit
        "https://maps.googleapis.com/maps/api/place/textsearch/json?query=actividades%20ocio%20" + ciudad + "&key=AIzaSyBX1DSnnWxD6s-t9_YzjtpbrPbPYcXJxoA", #Mati-Tarda
        "https://maps.googleapis.com/maps/api/place/textsearch/json?query=parque%20atracciones%20zoo%20" + ciudad + "&key=AIzaSyBX1DSnnWxD6s-t9_YzjtpbrPbPYcXJxoA", #Mati-Tarda
        "https://maps.googleapis.com/maps/api/place/textsearch/json?query=bar%20cine%20" + ciudad + "&key=AIzaSyBX1DSnnWxD6s-t9_YzjtpbrPbPYcXJxoA" #Tarda-Nit
    ]

    results = []
    types = ["Nocturna", "Mati-Tarda", "Mati-Tarda", "Nocturna-Tarda"]
    for i, url in enumerate(urls):
        response = requests.get(url)
        data = response.json()

        for item in data.get("results", []):
            name = item.get("name")
            price_level = item.get("price_level", "-1")
            result = {"name": name, "price_level": price_level, "type": types[i]}
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

    types = ["Nocturna", "Nocturna-Tarda", "Mati-Tarda", "Mati-Tarda", "Mati-Tarda", "Mati-Tarda"]

    for i, url in enumerate(urls):
        response = requests.get(url)
        data = response.json()

        for item in data.get("results", []):
            name = item.get("name")
            price_level = item.get("price_level", "-1")
            result = {"name": name, "price_level": price_level, "type": types[i]}
            results.append(result)

    print("FIN LLAMADA API - TODO OK")
    return results

def guardar_cache(cache, ciudad_destino = ""):
    with open(CACHE_FILE, "w") as file:
        file.truncate(0)  # Borrar contenido inicial del archivo
        file.write(ciudad_destino + "\n")
        for result in cache:
            line = f"{result['name']},{result['price_level']},{result['type']}\n"
            file.write(line)

def cache_valida(ciudad_destino = ""):
    with open(CACHE_FILE, "r") as file:
        primera_linea = file.readline().strip()
    return primera_linea == ciudad_destino

def leer_cache():
    with open(CACHE_FILE, "r") as file:
        contenido = file.readlines()[1:]
    resultados = []
    for linea in contenido:
        nombre, precio, tipo = linea.strip().split(",")
        resultado = {"name": nombre, "price_level": precio, "type": tipo}
        resultados.append(resultado)
    return resultados

def buscar_actividades(carga_actividades=None, nivel_precio=2, dias_viaje=0, proporcion_ludico_festiva=0.5, proporcion_cultural=0.5, ciudad_destino="Barcelona"):

        print ("carga: " + carga_actividades)
        print("nivel precio: " + str(nivel_precio))
        print("dias viaje: " + str(dias_viaje))
        print("Proporcion ludido y festiva: " + str(proporcion_ludico_festiva))
        print("Proporcion cultural: " + str(proporcion_cultural))

        if (cache_valida(ciudad_destino)):
            print("ACCES A CACHE")
            actividades_totales = leer_cache()

        else:
            print("ACCES A API")
            actividades_ludico_festivas = buscar_actividades_festivas(ciudad_destino)
            actividades_culturales = buscar_actividades_culturales(ciudad_destino)
            actividades_totales = actividades_ludico_festivas + actividades_culturales
            guardar_cache(actividades_totales, ciudad_destino)

        actividades_filtradas = [actividad for actividad in actividades_totales if int(actividad["price_level"]) <= nivel_precio]

        result = Graph()
        actividades_count = 0

        for consulta in actividades_filtradas:
            name = consulta["name"]
            price_level = consulta["price_level"]
            print("Nombre: " + name)
            print("Price level: " + str(price_level))
            type = consulta["type"]
            print("Este es el tipo: " + type)
            print("--------------")

            actividades_count += 1
            subject_actividades = URIRef("http://www.owl-ontologies.com/OntologiaECSDI.owl#Actividad" + str(actividades_count))
            result.add((subject_actividades, RDF.type, ONTO.Actividad))
            result.add((subject_actividades, ONTO.NombreActividad, Literal(name, datatype=XSD.string)))
            result.add((subject_actividades, ONTO.NivelPrecio, Literal(price_level, datatype=XSD.integer)))

        print("FIN CONSTRUCCION - TODO OK - ENVIANDO GRAFO")
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

    buscar_actividades("Alta", 3, 5, 0.5, 0.5, "Madrid")
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
