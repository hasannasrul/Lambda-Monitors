import requests
import boto3
import os
import json
from datetime import datetime
import time

s3 = boto3.client('s3')

###################### Some utility functions ############################################

def upload_logs_to_s3(logs, bucket_name, key):
    logs_str = json.dumps(logs, indent=2)
    s3.put_object(Body=logs_str, Bucket=bucket_name, Key=key)

############### Monitor class to implement monitoring features ##############################

class MonitorAPI():
    def __init__(self):
        pass

    def test_api(self, endpoint):
        try:
            # Record start time
            start_time = datetime.now()

            # Make API request
            response = requests.get(endpoint)
            response_time = (datetime.now() - start_time).total_seconds()

            # Check if the response is successful (status code 2xx)
            is_successful = response.ok

            # Log API response details
            api_result = {
                'endpoint': endpoint,
                'status_code': response.status_code,
                'is_successful': is_successful,
                'response_time': response_time,
                'response_headers': dict(response.headers),
                'response_body': response.text[:500]  # Limit response body length
            }

            return api_result

        except Exception as e:
            # Log if there's an exception during API request
            api_result = {
                'endpoint': endpoint,
                'error': str(e)
            }
            return api_result

############### Actual Lambda Handler function ##############################

def handler(event, context):
    # Extract API endpoints from the event
    endpoints = event.get('endpoints')

    # Check if the endpoints are provided
    if not endpoints:
        return {
            'statusCode': 400,
            'body': 'Error: Missing endpoints in the event'
        }

    monitor = MonitorAPI()
    api_results = []

    try:
        # Test each API endpoint
        for endpoint in endpoints:
            result = monitor.test_api(endpoint)
            api_results.append(result)

        # Upload API test results to S3
        timestamp = int(time.time() * 1000) 
        key = f'API-Monitoring-logs-{timestamp}.json'
        upload_logs_to_s3(api_results, os.environ['S3_BUCKET_NAME'], key)

        return {
            'statusCode': 200,
            'body': json.dumps(api_results),
            's3_key': key
        }

    except Exception as e:
        # Log any unexpected exception
        error_message = f'Error during API monitoring: {str(e)}'
        return {
            'statusCode': 500,
            'body': error_message
        }
