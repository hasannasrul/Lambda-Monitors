FROM public.ecr.aws/lambda/python@sha256:f0c3116a56d167eba8021a5d7c595f969835fbe78826303326f80de00d044733
RUN pip install requests==2.31.0
RUN pip install boto3
COPY main.py ${LAMBDA_TASK_ROOT}
CMD [ "main.handler" ]