import requests
import boto3
import os
import json
from datetime import datetime
import time

s3 = boto3.client('s3')
dynamodb = boto3.client('dynamodb')

# DynamoDB Table Name
table_name = 'APIResponsesTableNew'

###################### Some utility functions ############################################

def upload_logs_to_s3(logs, bucket_name, key):
    logs_str = json.dumps(logs, indent=2)
    s3.put_object(Body=logs_str, Bucket=bucket_name, Key=key)

############### Monitor class to implement monitoring features ##############################

class MonitorAPI():
    def __init__(self):
        pass

    def test_api(self, method, endpoint, body=None):
        try:
            # Record start time
            start_time = datetime.now()

            # Make API request based on the method
            if method == 'GET':
                response = requests.get(endpoint)
            elif method == 'POST':
                response = requests.post(endpoint, json=body)
            elif method == 'DELETE':
                response = requests.delete(endpoint, json=body)
            else:
                raise ValueError(f'Invalid HTTP method: {method}')

            response_time = (datetime.now() - start_time).total_seconds()

            # Check if the response is successful (status code 2xx)
            is_successful = response.ok
            # Log API response details
            api_result = {
                'method': method,
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
                'method': method,
                'endpoint': endpoint,
                'error': str(e)
            }
            return api_result

############### Actual Lambda Handler function ##############################

def handler(event, context):
    # Extract API tests from the event
    api_tests = event.get('API-Test')

    # Check if API tests are provided
    if not api_tests:
        return {
            'statusCode': 400,
            'body': 'Error: Missing API-Test in the event'
        }

    monitor = MonitorAPI()
    api_results = []

    for api_test in api_tests:
        endpoint = api_test.get('endpoint')
        method = api_test.get('method')
        body = api_test.get('body')

        if not (endpoint and method):
            return {
                'statusCode': 400,
                'body': f'Error: Missing endpoint/method in API test: {json.dumps(api_test)}'
            }

        try:
            # Test API endpoint
            result = monitor.test_api(method, endpoint, body)
            api_results.append(result)

            # Save API response data to DynamoDB
            dynamodb.put_item(
                TableName=table_name,
                Item={
                    'Endpoint': {'S': endpoint},
                    'Method': {'S': method},
                    'StatusCode': {'N': str(result['status_code'])},
                    'IsSuccessful': {'BOOL': result['is_successful']},
                    'ResponseTime': {'N': str(result['response_time'])},
                    'ResponseHeaders': {'S': json.dumps(result['response_headers'])},
                    'ResponseBody': {'S': result['response_body']}
                }
            )

        except Exception as e:
            # Log any unexpected exception
            error_message = f'Error during API monitoring: {str(e)}'
            return {
                'statusCode': 500,
                'body': error_message
            }

    # Upload API test results to S3
    timestamp = int(time.time() * 1000)
    key = f'API-Monitoring-logs-{timestamp}.json'
    upload_logs_to_s3(api_results, os.environ['S3_BUCKET_NAME'], key)

    return {
        'statusCode': 200,
        'body': json.dumps(api_results),
        's3_key': key
    }
