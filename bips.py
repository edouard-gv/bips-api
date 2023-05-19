import decimal
import json
import uuid
from datetime import datetime, timedelta, date
from math import cos, pi

import boto3
from boto3.dynamodb.conditions import Key

# Configuration de la base de données DynamoDB
dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table("Bips")


# Fonction pour insérer un nouveau Bip dans la base de données
def add_bip(data):
    bip = {
        "id": str(uuid.uuid4()),
        "pseudo": data["pseudo"],
        "status_code": data["status_code"],
        "location": data["location"],
        "latitude": decimal.Decimal(str(data.get("latitude", None))),
        "longitude": decimal.Decimal(str(data.get("longitude", None))),
        "timestamp": datetime.utcnow().isoformat(),
        "day": str(date.today())
    }
    table.put_item(Item=bip)
    return bip["id"]


# Fonction pour encoder un décimal représentant un status en JSON
def decimal2status(obj):
    if isinstance(obj, decimal.Decimal):
        return int(obj)
    return obj


def calculate_bounding_box_half_dimensions(lat, lon, distance):
    radius = 6371e3  # rayon de la Terre en mètres
    to_radians = pi / 180  # conversion de degrés à radians

    # calcul de l'offset en degrés
    d_lat = distance / radius * (180 / pi)
    d_lon = distance / (radius * cos(lat * to_radians)) * (180 / pi)

    return d_lat, d_lon


# Fonction pour récupérer les Bips qui ont été postés au même endroit aujourd'hui
def get_bips(location, latitude=0, longitude=0):
    locations_with_same_name = table.query(
        IndexName="day-location-index",
        KeyConditionExpression=Key("day").eq(str(date.today())) & Key("location").eq(location),
    ) if location != "geoloc" else {"Items": []}  # Si on demande les Bips géolocalisés, on ne filtre pas par location

    # Si on n'a pas communiqué de latitude et longitude, on ne filtre pas par coordonnées
    if latitude == 0 and longitude == 0:
        locations_around = {"Items": []}
    else:
        locations_around = table.query(
            IndexName="day-location-index",
            KeyConditionExpression=Key("day").eq(str(date.today())),
        )

    d_lat, d_lon = calculate_bounding_box_half_dimensions(latitude, longitude, 50)
    return [
        {"pseudo": bip["pseudo"], "status_code": decimal2status(bip["status_code"]), "timestamp": bip["timestamp"]}
        for bip in locations_with_same_name["Items"] +
                   [bip for bip in locations_around["Items"]
                    if latitude - d_lat <= bip["latitude"] <= latitude + d_lat
                    and longitude - d_lon <= bip["longitude"] <= longitude + d_lon
                    and (location == "geoloc" or bip["location"] != location)]
    ]


# Fonction principale pour AWS Lambda
def lambda_handler(event, context):
    if "http" in event["requestContext"]:
        http_method = event["requestContext"]["http"]["method"]
    else:
        http_method = event["requestContext"]["httpMethod"]

    if http_method == "POST":
        data = json.loads(event["body"])
        bip_id = add_bip(data)
        response = {"message": f"Bip stacked with ID: {bip_id}"}
    elif http_method == "GET":
        location = event["queryStringParameters"]["location"]
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
