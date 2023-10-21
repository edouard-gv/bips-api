import json
import boto3

dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table('bipers')


def lambda_handler(event, context):
    connection_id = event['requestContext']['connectionId']

    # Stocker l'ID de connexion dans DynamoDB
    table.put_item(Item={'connectionId': connection_id})

    # Répondre au client
    response = {
        "statusCode": 200,
        "body": json.dumps({
            "message": "Connexion établie avec succès pour l'id :"+connection_id+"!"
        })
    }
    return response
