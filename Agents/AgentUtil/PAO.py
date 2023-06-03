from rdflib import URIRef
from rdflib.namespace import ClosedNamespace

PAO =  ClosedNamespace(
    uri=URIRef('http://www.semanticweb.org/planifier-agent-ontology#'),
    terms=[
        # Classes
        'TripRequest',
        'User',
        'City',

        #Relations
        'From',     # Domain: TripRequest, Range: City
        'To',       # Domain: TripRequest, Range: City
        'By',       # Domain: TripRequest, Range: User

        # Data properties
        'Budget',   # Type: Int, Domain: TripRequest
        'Start',    # Type: Date, Domain: TripRequest
        'End',      # Type: Date, Domain: TripRequest
        'Name',     # Type: String, Domain: City, User
        'Playful',  # Type: Int, Domain: TripRequest
        'Cultural',  # Type: Int, Domain: TripRequest
        'Festive',  # Type: Int, Domain: TripRequest
        
        
    ]
)