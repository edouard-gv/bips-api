import decimal
import json
import uuid
from datetime import datetime, date
from math import cos, pi

import boto3
from boto3.dynamodb.conditions import Key


# Configuration de la base de données DynamoDB
class DynamoService:

    @property
    def dynamodb(self):
        if not hasattr(self, "_dynamodb"):
            self._dynamodb = boto3.resource("dynamodb")
        return self._dynamodb

    @property
    def table(self):
        if not hasattr(self, "_table"):
            self._table = self.dynamodb.Table("Bips")
        return self._table


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
    service.table.put_item(Item=bip)
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

    bips_of_day = service.table.query(
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


# Fonction répondant à l'action d'émission d'un bip sur la websocket
def bip_handler(event, context):
    connection_id = event['requestContext']['connectionId']
    data = json.loads(event["body"])["data"]
    bip_id = add_bip(data, connection_id)
    response = {"message": f"Bip stacked with ID: {bip_id}"}
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
