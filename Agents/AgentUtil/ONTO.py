from rdflib import URIRef
from rdflib.namespace import ClosedNamespace

ONTO =  ClosedNamespace(
    uri=URIRef('http://www.owl-ontologies.com/OntologiaECSDI.owl#'),
    terms=[
        # Classes
        'TripRequest',
        'FlightRequest',
        'HotelRequest',
        'ActivitiesRequest',
        
        'TripPlanification',
        'Flight',
        'Hotel',
        'Activity',
        'User',
        'City',

        #Relations
        'origin',           # Domain: TripRequest, FlightRequest, Flight Range: City
        'destination',      # Domain: TripRequest, FlightRequest, Flight Range: City
        'by',               # Domain: TripRequest, Range: User
        'outboundFlight',   # Domain: TripPlanification, Range: Flight
        'returnFlight',     # Domain: TripPlanification, Range: Flight
        'on',               # Domain: Activity, Hotel, ActivitiesRequest, HotelRequest, Range: City
        'lodging',          # Domain: TripPlanification, Range: Hotel
        'result',           # Domain: TripRequest, Range: TripPlanification

        # Data properties
        'budget',           # Type: Int, Domain: TripRequest, ActivitiesRequest, HotelRequest, FlightRequest
        'start',            # Type: Date, Domain: TripRequest, TripPlanification
        'end',              # Type: Date, Domain: TripRequest, TripPlanification
        'name',             # Type: String, Domain: City, User
        'playful',          # Type: Int, Domain: TripRequest, ActivitiesRequest, Activity
        'cultural',         # Type: Int, Domain: TripRequest, ActivitiesRequest, Activity
        'festive',          # Type: Int, Domain: TripRequest, ActivitiesRequest, Activity
        'location',         # Type: String, Domain: Hotel, HotelRequest || Accepted values: 'Centric' , 'No Centric'
        'date',
        'price',   
        'maxPrice',
        'duration',
        'id',         
        
        
    ]
)