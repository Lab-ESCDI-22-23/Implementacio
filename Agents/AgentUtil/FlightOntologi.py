from rdflib import URIRef
from rdflib.namespace import ClosedNamespace

MOT =  ClosedNamespace(
    uri=URIRef('http://www.MyOntologi.com/#'),
    terms=[
        # Classes
        'Accio',
        
        'PeticioViatje',
        
        'PeticioVols',
        'PeticioHotles',
        'PeticioActivitats',    
        
        'Producte'
        'Vol',
        'Activitat',
        'Allotjament',
        'Ciutat',
        'Usuari',
        

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