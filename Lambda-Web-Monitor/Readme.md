# Run Selenium in AWS Lambda

This is a repository to setup selenium for AWS Lambda Function. It will Monitor website passed
as a event to this function and store the logs to AWS S3.

# Pre-requistes

1. AWS Account
2. Docker
3. AWS CLI

## Install AWS CLI and configure AWS creds

```
aws configure
```

## Create Repository to push you image which will be used in Lambda function

```
aws ecr create-repository --repository-name <your-repo-name>
```

## Login to ecr registry which we created above

```
aws ecr get-login-password --region <region-name> | docker login --username AWS --password-stdin <AWS-Account-ID>.dkr.ecr.us-east-1.amazonaws.com
```

## Build and push images to AWS registry

```
docker buildx build --platform linux/amd64 -t <AWS-Account-ID>.dkr.ecr.us-east-1.amazonaws.com/<your-repo-name>:latest .

docker push <AWS-Account-ID>.dkr.ecr.us-east-1.amazonaws.com/<your-repo-name>:latest
```

# Lambda Function creation

> Note: Lambda Function and Docker Image should be in same AWS Region

1. Go to AWS lambda Console
2. Create function
3. select create with container image option
4. Give name to your lambda function
5. Select image which we created above from browse image option
6. Create a role for Lambda function to access ECR and all the permission required for your usecase
7. Deploy the funcion
8. Edit environment variable under configuration
```
S3_BUCKET_NAME=<your-bucket-name>
```

### Test Function
Pass the url as a json

```
{
  "url": "https://www.pfizer.com",
}
```

