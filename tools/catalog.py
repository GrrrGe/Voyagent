"""Original demo fixtures. Costs and scheduling assumptions are not quotes."""
CITIES = {
    'Tokyo': {
        'airport': 'HND', 'country': 'Japan', 'fare': 68000, 'night': 11200,
        'stay': 'Asakusa House', 'area': 'Asakusa',
        'clusters': [
            ('Asakusa', 'Senso-ji temple', 'Sumida riverside walk', 'Tokyo National Museum'),
            ('Shibuya', 'Meiji Jingu grounds', 'Shibuya crossing', 'Shibuya museum visit'),
            ('Ueno', 'Ueno Park', 'Ameyoko market', 'National Museum of Nature and Science'),
            ('Ginza', 'Tsukiji outer market', 'Ginza walk', 'Ginza gallery visit'),
            ('Yanaka', 'Yanaka lanes', 'Nezu Shrine', 'Local craft workshop'),
            ('Shinjuku', 'Shinjuku Gyoen', 'City observation deck', 'Local history museum'),
            ('Asakusa', 'Kappabashi shops', 'Sumida Park', 'Tea workshop'),
        ],
    },
    'Lisbon': {
        'airport': 'LIS', 'country': 'Portugal', 'fare': 52000, 'night': 8900,
        'stay': 'Alfama Rooms', 'area': 'Alfama',
        'clusters': [
            ('Alfama', 'Alfama lanes', 'Portas do Sol viewpoint', 'Fado Museum'),
            ('Belem', 'Belem waterfront', 'Jeronimos exterior', 'Maritime Museum'),
            ('Baixa', 'Praca do Comercio', 'Rua Augusta walk', 'Lisbon Story Centre'),
            ('Chiado', 'Chiado bookshops', 'Carmo square', 'Chiado Museum'),
            ('Parque das Nacoes', 'Riverfront walk', 'Water gardens', 'Lisbon Oceanarium'),
        ],
    },
    'Paris': {
        'airport': 'CDG', 'country': 'France', 'fare': 48000, 'night': 14500,
        'stay': 'Canal Studio Hotel', 'area': 'Canal Saint-Martin',
        'clusters': [
            ('Le Marais', 'Place des Vosges', 'Marais lanes', 'Carnavalet Museum'),
            ('Louvre', 'Tuileries Garden', 'Seine walk', 'Louvre Museum'),
            ('Montmartre', 'Sacre-Coeur exterior', 'Montmartre walk', 'Montmartre Museum'),
            ('Left Bank', 'Luxembourg Garden', 'Latin Quarter walk', 'Cluny Museum'),
        ],
    },
    'Dubai': {
        'airport': 'DXB', 'country': 'United Arab Emirates', 'fare': 74000, 'night': 12800,
        'stay': 'Marina View Rooms', 'area': 'Dubai Marina',
        'clusters': [
            ('Dubai Marina', 'Marina walk', 'JBR beachfront', 'Marina museum visit'),
            ('Downtown', 'Burj Khalifa exterior', 'Dubai Mall walk', 'Aquarium visit'),
            ('Deira', 'Gold Souk lanes', 'Creek crossing', 'Coffee museum visit'),
            ('Jumeirah', 'Jumeirah beach walk', 'Kite Beach park', 'Etihad museum visit'),
            ('Al Fahidi', 'Al Fahidi lanes', 'Dubai Creek walk', 'Coin museum visit'),
            ('Palm Jumeirah', 'Boardwalk stroll', 'Palm viewpoints', 'Aquaventure water park'),
        ],
    },
    'Bangkok': {
        'airport': 'BKK', 'country': 'Thailand', 'fare': 69000, 'night': 7400,
        'stay': 'Riverside House', 'area': 'Riverside',
        'clusters': [
            ('Riverside', 'Wat Arun exterior', 'River ferry ride', 'Royal Barge museum'),
            ('Old City', 'Grand Palace exterior', 'Wat Pho grounds', 'National Museum'),
            ('Chinatown', 'Yaowarat lanes', 'Street food walk', 'Chinatown heritage center'),
            ('Sukhumvit', 'Benjasiri Park', 'Soi shopping walk', 'Contemporary art gallery'),
            ('Silom', 'Lumphini Park', 'Patpong market walk', 'Sri Mariamman temple visit'),
            ('Chatuchak', 'Weekend market lanes', 'Chatuchak Park', 'Children discovery museum'),
        ],
    },
}
ORIGINS = {'San Francisco': 'SFO', 'New York': 'JFK', 'Toronto': 'YYZ', 'London': 'LHR', 'Chennai': 'MAA', 'Dhaka': 'DAC', **{k: v['airport'] for k, v in CITIES.items()}}
COUNTRY_ALIASES = {'japan': 'Tokyo', 'thailand': 'Bangkok', 'uae': 'Dubai', 'emirates': 'Dubai'}
