from unittest.mock import patch, MagicMock

import boto3.dynamodb.conditions

from bips import get_bips

"""
Lieu des bips de test :
1 : au siège
2 : geoloc à côté du siège
3 : geoloc à l'autre bout de la terre
4 : geoloc sans coordonnées

Cas de tests de get_bips: tous les bips proche de moi mais pas loin de moi
Si geoloc mais pas de coordonnées: on renvoie une liste vide
Si geoloc proche du siège et coordonnées: on renvoie une liste de bips 1, 2
Si au siège et pas de coordonnées: should never happen
Si au siège et coordonnées: on renvoie une liste de bips 1, 2
Si geoloc proche de l'autre bout de la terre et coordonnées: on renvoie une liste de bips 3
"""

# les quatre bips de test:
# 1 : au siège
siege = {
    "pseudo": "Ada",
    "status_code": 100,
    "timestamp": "2023-10-20T12:31:00Z",
    "location": "au siège",
    "latitude": 48.8566,
    "longitude": 2.3522,
}

# 2 : geoloc à côté du siège
pres_du_siege = {
    "pseudo": "Beda",
    "status_code": 100,
    "timestamp": "2023-10-20T12:32:00Z",
    "location": "geoloc",
    "latitude": 48.8568,
    "longitude": 2.3522,
}

# 3 : geoloc à l'autre bout de la terre
bout_de_la_terre = {
    "pseudo": "Omeda",
    "status_code": 100,
    "timestamp": "2023-10-20T12:33:00Z",
    "location": "geoloc",
    "latitude": -48.8566,
    "longitude": -2.3522,
}

# 4 : geoloc sans coordonnées
sans_coordonnees = {
    "pseudo": "Secreda",
    "status_code": 100,
    "timestamp": "2023-10-20T12:34:00Z",
    "location": "geoloc",
}


# Cette fonction est utilisée pour mocker le retour de la requête à DynamoDB
def mock_query(*args, **kwargs):
    # Vous pouvez modifier cette structure en fonction de ce que vous attendez de votre base de données

    # j'ai une condition a plusieurs paramètres donc on filtre par location
    if isinstance(kwargs['KeyConditionExpression']._values[0], boto3.dynamodb.conditions.Equals):
        return {
            "Items": [siege, ]
        }
    else:
        return {
            "Items": [siege, pres_du_siege, bout_de_la_terre, sans_coordonnees]
        }


# extrait une liste de nom d'une liste de bips
def extract_pseudo(bips):
    return [bip["pseudo"] for bip in bips]


# Si geoloc mais pas de coordonnées: on renvoie une liste vide
@patch('boto3.resource')
def test_get_bips_secreda(boto_mock):
    init_mock(boto_mock)
    result = get_bips("geoloc")
    assert result == []


# Si geoloc proche du siège et coordonnées: on renvoie une liste de bips 1, 2
@patch('boto3.resource')
def test_get_bips_proche_du_siege(boto_mock):
    init_mock(boto_mock)
    result = get_bips("geoloc", 48.8565, 2.3521)
    assert extract_pseudo(result) == extract_pseudo([siege, pres_du_siege])


# Si au siège et pas de coordonnées: should never happen
@patch('boto3.resource')
def test_get_bips_siege_sans_coord(boto_mock):
    init_mock(boto_mock)
    result = get_bips("au siège")
    assert extract_pseudo(result) == extract_pseudo([siege])


# Si au siège et coordonnées: on renvoie une liste de bips 1, 2
@patch('boto3.resource')
def test_get_bips_siege(boto_mock):
    init_mock(boto_mock)
    result = get_bips("au siège", 48.8566, 2.3522)
    assert extract_pseudo(result) == extract_pseudo([siege, pres_du_siege])


# Si geoloc proche de l'autre bout de la terre et coordonnées: on renvoie une liste de bips 3
@patch('boto3.resource')
def test_get_bips_bout_de_la_terre(boto_mock):
    init_mock(boto_mock)
    result = get_bips("geoloc", -48.8565, -2.3523)
    assert extract_pseudo(result) == extract_pseudo([bout_de_la_terre])


def init_mock(boto_mock):
    # On configure le mock pour qu'il retourne le résultat attendu
    table_mock = MagicMock()
    table_mock.query.side_effect = mock_query
    boto_mock.return_value.Table.return_value = table_mock
