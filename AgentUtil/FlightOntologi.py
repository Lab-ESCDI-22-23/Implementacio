from rdflib import URIRef
from rdflib.namespace import ClosedNamespace

MOT =  ClosedNamespace(
    uri=URIRef('http://www.MyOntologi.com/#'),
    terms=[
        # Classes
        'Accio',
        
        'Peticio Viatje',
        'Resposta Vitaje',
        
        'Peticio Vols',
        'Peticio Hotles',
        'Peticio Activitats',
        ''
        
        'Producte'
        'Vol',
        'Activitat',
        'Allotjament',
        'Ciutat',
        'Usuari',
        
        
        'SolverAgent',
        'Modify',

        # Object properties
        'ProductType',

        # Data properties
        'Uri',
        'Name',
        'Address',
        
        # Named Individuals
        'FlightsAgent',
        'HotelsAgent',
        'TravelServiceAgent',
        'PersonalAgent',
        'WeatherAgent',
        'PaymentAgent'
    ]
)