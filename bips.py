import decimal
import json
import uuid
from datetime import datetime, date
from math import cos, pi

import boto3
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError


# Configuration de la base de données DynamoDB
class DynamoService:

    @property
    def dynamodb(self):
        if not hasattr(self, "_dynamodb"):
            self._dynamodb = boto3.resource("dynamodb")
        return self._dynamodb

    @property
    def bips_table(self):
        if not hasattr(self, "_bips_table"):
            self._bips_table = self.dynamodb.Table("Bips")
        return self._bips_table

    @property
    def bipers_table(self):
        if not hasattr(self, "_bipers_table"):
            self._bipers_table = self.dynamodb.Table("Bipers")
        return self._bipers_table


# Fonction pour insérer un nouveau Bip dans la base de données
def add_bip(data, connection_id):
    service = DynamoService()
    bip = {
        "connection_id": connection_id,
        "id": str(uuid.uuid4()),
        "pseudo": data["pseudo"],
        "status_code": data["status_code"],
        "location": data["location"],
        "timestamp": datetime.utcnow().isoformat(),
        "day": str(date.today())
    }
    if "latitude" in data and "longitude" in data:
        bip["latitude"] = decimal.Decimal(str(data.get("latitude")))
        bip["longitude"] = decimal.Decimal(str(data.get("longitude")))
    service.bips_table.put_item(Item=bip)
    return bip["id"]


# Fonction pour encoder un décimal représentant un status en JSON
def decimal2status(obj):
    if isinstance(obj, decimal.Decimal):
        return int(obj)
    return obj


def decimal2coords(obj):
    if isinstance(obj, decimal.Decimal):
        return float(round(obj, 6))
    return obj


def calculate_bounding_box_half_dimensions(lat, lon, distance):
    radius = 6371e3  # rayon de la Terre en mètres
    to_radians = pi / 180  # conversion de degrés à radians

    # calcul de l'offset en degrés
    d_lat = distance / radius * (180 / pi)
    d_lon = distance / (radius * cos(lat * to_radians)) * (180 / pi)

    return d_lat, d_lon


# Fonction pour récupérer les Bips qui ont été postés au même endroit aujourd'hui
def get_bips(location, latitude=None, longitude=None):
    service = DynamoService()

    bips_of_day = service.bips_table.query(
        IndexName="day-timestamp-index",
        ScanIndexForward=False,
        KeyConditionExpression=Key("day").eq(str(date.today())),
    )["Items"]

    if latitude is not None or longitude is not None:
        d_lat, d_lon = calculate_bounding_box_half_dimensions(latitude, longitude, 50)
        bips_around = [bip for bip in bips_of_day
                       if "latitude" in bip and latitude - d_lat <= bip["latitude"] <= latitude + d_lat
                       and "longitude" in bip and longitude - d_lon <= bip["longitude"] <= longitude + d_lon
                       or (location != "geoloc" and bip["location"] == location)]

    # Si on n'a pas communiqué de latitude et longitude, on ne filtre pas par coordonnées
    else:
        bips_around = [bip for bip in bips_of_day
                       if (location != "geoloc" and bip["location"] == location)]

    return [
        map_bip(bip) for bip in bips_around
    ]


def map_bip(bip):
    bip_mapped = {"pseudo": bip["pseudo"],
                  "status_code": decimal2status(bip["status_code"]),
                  "timestamp": bip["timestamp"],
                  }
    if "latitude" in bip and "longitude" in bip:
        bip_mapped["latitude"] = decimal2coords(bip["latitude"])
        bip_mapped["longitude"] = decimal2coords(bip["longitude"])
    return bip_mapped


# Fonction pour envoyer une notification à tous les clients connectés
def notify_connected_bipers():
    table = DynamoService().bipers_table

    # Créer un client pour l'API Gateway Management API
    client = boto3.client('apigatewaymanagementapi', endpoint_url='https://djlftbwj16.execute-api.eu-west-3.amazonaws.com/Prod/')

    # Récupérer les IDs de connexion depuis DynamoDB
    try:
        response = table.scan()
        connection_ids = [item['connectionId'] for item in response['Items']]
    except ClientError as e:
        print(e.response['Error']['Message'])
        return {
            'statusCode': 500,
            'body': json.dumps('Error fetching connection IDs')
        }

    # Envoyer des notifications
    message = {'action': 'notify', 'data': 'new bip'}
    for connection_id in connection_ids:
        try:
            client.post_to_connection(
                ConnectionId=connection_id,
                Data=json.dumps(message).encode('utf-8')
            )
        except ClientError as e:
            print(e.response['Error']['Message'])
            # Gérer les connexions expirées
            if e.response['Error']['Code'] == 'GoneException':
                # Supprimer l'ID de connexion de DynamoDB si nécessaire
                pass

    return len(connection_ids)


# Fonction répondant à l'action d'émission d'un bip sur la websocket
def bip_handler(event, context):
    connection_id = event['requestContext']['connectionId']
    data = json.loads(event["body"])["data"]
    bip_id = add_bip(data, connection_id)
    nb_notified_bipers = notify_connected_bipers()
    response = {"message": f"Bip stacked with ID: {bip_id} and {nb_notified_bipers} connected bipers notified"}
    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(response),
    }


# Fonction principale pour AWS Lambda
def lambda_handler(event, context):
    if "http" in event["requestContext"]:
        http_method = event["requestContext"]["http"]["method"]
    else:
        http_method = event["requestContext"]["httpMethod"]

    if http_method == "GET":
        location = event["queryStringParameters"]["location"]
        # Si on a communiqué une latitude et une longitude, on les utilise pour filtrer les Bips
        if "latitude" in event["queryStringParameters"] and "longitude" in event["queryStringParameters"]:
            latitude = float(event["queryStringParameters"]["latitude"])
            longitude = float(event["queryStringParameters"]["longitude"])
            response = get_bips(location, latitude, longitude)
        else:
            response = get_bips(location)
    else:
        response = {"error": "Invalid request"}

    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(response),
    }
