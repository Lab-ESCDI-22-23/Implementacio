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
import socket


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

    # Datos del Agente
    FlightAgent = Agent('FlightAgent',
                    agn.FlightAgent,
                    'http://%s:%d/comm' % (hostaddr, port),
                    'http://%s:%d/Stop' % (hostaddr, port))

    # Directory agent address
    DirectoryAgent = Agent('DirectoryAgent',
                        agn.Directory,
                        'http://%s:%d/Register' % (dhostname, dport),
                        'http://%s:%d/Stop' % (dhostname, dport))

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

    logger.info('Nos registramos')

    global mss_cnt

    gmess = Graph()

    # Construimos el mensaje de registro
    gmess.bind('foaf', FOAF)
    gmess.bind('dso', DSO)
    reg_obj = agn[FlightAgent.name + '-Register']
    gmess.add((reg_obj, RDF.type, DSO.Register))
    gmess.add((reg_obj, DSO.Uri, FlightAgent.uri))
    gmess.add((reg_obj, FOAF.name, Literal(FlightAgent.name)))
    gmess.add((reg_obj, DSO.Address, Literal(FlightAgent.address)))
    gmess.add((reg_obj, DSO.AgentType, DSO.HotelsAgent))

    # Lo metemos en un envoltorio FIPA-ACL y lo enviamos
    gr = send_message(
        build_message(gmess, perf=ACL.request,
                      sender=FlightAgent.uri,
                      receiver=DirectoryAgent.uri,
                      content=reg_obj,
                      msgcnt=mss_cnt),
        DirectoryAgent.address)
    mss_cnt += 1

    return gr


@app.route("/iface", methods=['GET', 'POST'])
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

    Asumimos que se reciben siempre acciones que se refieren a lo que puede hacer
    el agente (buscar con ciertas restricciones, reservar)
    Las acciones se mandan siempre con un Request
    Prodriamos resolver las busquedas usando una performativa de Query-ref
    """
    global dsgraph
    global mss_cnt

    logger.info('Peticion de informacion recibida')

    # Extraemos el mensaje y creamos un grafo con el
    message = request.args['content']
    gm = Graph()
    gm.parse(data=message, format='xml')

    msgdic = get_message_properties(gm)

    # Comprobamos que sea un mensaje FIPA ACL
    if msgdic is None:
        # Si no es, respondemos que no hemos entendido el mensaje
        gr = build_message(Graph(), ACL['not-understood'], sender=InfoAgent.uri, msgcnt=mss_cnt)
    else:
        # Obtenemos la performativa
        perf = msgdic['performative']

        if perf != ACL.request:
            # Si no es un request, respondemos que no hemos entendido el mensaje
            gr = build_message(Graph(), ACL['not-understood'], sender=InfoAgent.uri, msgcnt=mss_cnt)
        else:
            # Extraemos el objeto del contenido que ha de ser una accion de la ontologia de acciones del agente
            # de registro

            # Averiguamos el tipo de la accion
            logger.info("-----")
            logger.info('content' in msgdic)
            if 'content' in msgdic:
                content = msgdic['content']
                accion = gm.value(subject=content, predicate=RDF.type)
                logger.info(accion)

                # Aqui realizariamos lo que pide la accion
                if False: #accion == "CercaVols": #ONTO.action.CercaVols?
                    #OBTENIR PARAMETRES DEL GRAF

                    dataInici = "1/1/2024"
                    dataFi = "10/1/2024"
                    pressupost = 200
                    origen = "Barcelona"
                    desti = "Paris"


                    #"FER" PETICIÓ segons parametres (Consulta API o Random(utilitzant paramentres))
                    idVolAnada = "AAA"
                    idVolTornada = "BBB"
                    preuVolAnada = 100.0
                    preuVolTornada = 90.0
                    home = "BCN"
                    visit = "CDG"
                    data_anada = "12:00" #tecnicament en format date
                    data_tornada = "3:00"
                    duracio_anada = 2.5
                    duracio_tornada = 3

                    #CONSTRUIR GRAF DE RESPOSTA
                    gmess = Graph()
                    prods = Namespace('http://la.nostra.ontologia.org/producte/')
                    vols = Namespace('http://la.nostra.ontologia.org/vols/') #vols és subclasse de prods, com es fa?

                    #gmess.bind('foaf', FOAF) cal?

                    # Construimos el mensaje de registro
                    vol_anada = prods.vol
                    vol_tornada = prods.vol

                    gmess.add((vol_anada, RDF.type, prods.vol))
                    gmess.add((vol_tornada, RDF.type, prods.vol))

                    gmess.add((vol_anada, prods.id, Literal(idVolAnada)))
                    gmess.add((vol_anada, prods.nom, Literal('vol_anada')))
                    gmess.add((vol_anada, prods.preu, Literal(preuVolAnada)))

                    gmess.add((vol_tornada, prods.id, Literal(idVolTornada)))
                    gmess.add((vol_tornada, prods.nom, Literal('vol_anada')))
                    gmess.add((vol_tornada, prods.preu, Literal(preuVolTornada)))

                    gmess.add((vol_anada, vols.desti, Literal(visit)))
                    gmess.add((vol_anada, vols.origen, Literal(home)))
                    gmess.add((vol_anada, vols.data, Literal(data_anada)))
                    gmess.add((vol_anada, vols.duracio, Literal(duracio_anada)))

                    gmess.add((vol_tornada, vols.desti, Literal(home)))
                    gmess.add((vol_tornada, vols.origen, Literal(visit)))
                    gmess.add((vol_tornada, vols.data, Literal(data_tornada)))
                    gmess.add((vol_tornada, vols.duracio, Literal(duracio_tornada)))

                    gr = build_message(gmess,
                                       perf=ACL.response,
                                       sender=InfoAgent.uri,
                                       msgcnt=mss_cnt,
                                       receiver=msgdic['sender'], )

            #else:


            ##################################3

            # "FER" PETICIÓ segons parametres (Consulta API o Random(utilitzant paramentres))
            idPeticio = 1
            
            idVolAnada = "AAA"
            idVolTornada = "BBB"
            preuVolAnada = 100.0
            preuVolTornada = 90.0
            home = "BCN"
            visit = "CDG"
            data_anada = "12:00"  # tecnicament en format date
            data_tornada = "3:00"
            duracio_anada = 2.5
            duracio_tornada = 3
            
            

            logger.info("---PETICIO FETA---")

            # CONSTRUIR GRAF DE RESPOSTA
            gmess = Graph()
            logger.info("---graf---")
            prods = Namespace('http://la.nostra.ontologia.org/producte/')
            vols = Namespace('http://la.nostra.ontologia.org/vols/')  # vols és subclasse de prods, com es fa?
            logger.info("---namespaces---")

            
            myOnt = Namespace('http://la.nostra.ontologia.org/')
            
            response = myOnt[FlightAgent.name + '-Response-Peticio-Vols' + idPeticio]
            volAnada = myOnt[idVolAnada]
            volTornada = myOnt[idVolTornada]
            
            gmess.add((volAnada, RDF.type, myOnt.vol))
            gmess.add((volAnada, myOnt, ))
            
            gmess.add((response, RDF.type, myOnt.RespostaCercaVol))
            
            gmess.add((response, myOnt.volAnada, vol))
            gmess.add((response, myOnt.volTornada, vol))
            
            # gmess.bind('foaf', FOAF) cal?

            # Construimos el mensaje de registro
            vol_anada = prods.vol_a
            vol_tornada = prods.vol_t
            logger.info("---objectes---")

            gmess.add((vol_anada, RDF.type, prods.vol))
            gmess.add((vol_tornada, RDF.type, prods.vol))
            logger.info("---tipus---")

            gmess.add((vol_anada, prods.id, Literal(idVolAnada)))
            gmess.add((vol_anada, prods.nom, Literal('vol_anada')))
            gmess.add((vol_anada, prods.preu, Literal(preuVolAnada)))

            gmess.add((vol_tornada, prods.id, Literal(idVolTornada)))
            gmess.add((vol_tornada, prods.nom, Literal('vol_Tornada')))
            gmess.add((vol_tornada, prods.preu, Literal(preuVolTornada)))

            gmess.add((vol_anada, vols.desti, Literal(visit)))
            gmess.add((vol_anada, vols.origen, Literal(home)))
            gmess.add((vol_anada, vols.data, Literal(data_anada)))
            gmess.add((vol_anada, vols.duracio, Literal(duracio_anada)))

            gmess.add((vol_tornada, vols.desti, Literal(home)))
            gmess.add((vol_tornada, vols.origen, Literal(visit)))
            gmess.add((vol_tornada, vols.data, Literal(data_tornada)))
            gmess.add((vol_tornada, vols.duracio, Literal(duracio_tornada)))
            logger.info("---done---")

            gr = build_message(gmess,
                               ACL['inform'],
                               sender=InfoAgent.uri,
                               msgcnt=mss_cnt,
                               receiver=msgdic['sender'], )
            #fipa acl performativa inform?
            logger.info("---built---")

            #####################################

            # Por ahora simplemente retornamos un Inform-done
            """
            logger.info('INFORM DONE')

            gr = build_message(Graph(),
                           ACL['inform'],
                           sender=InfoAgent.uri,
                           msgcnt=mss_cnt,
                           receiver=msgdic['sender'], )
            """
    mss_cnt += 1

    logger.info('Respondemos a la peticion')

    return gr.serialize(format='xml')


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
    fin = False
    while not fin:
        while cola.empty():
            pass
        v = cola.get()
        if v == 0:
            fin = True
        else:
            print(v)



if __name__ == '__main__':
    # Ponemos en marcha los behaviors
    ab1 = Process(target=agentbehavior1, args=(cola1,))
    ab1.start()

    # Ponemos en marcha el servidor
    app.run(host=hostname, port=port)

    # Esperamos a que acaben los behaviors
    ab1.join()
    logger.info('The End')
