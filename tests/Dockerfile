FROM python:3.6

RUN curl -fsSL get.docker.com -o /tmp/get-docker.sh && \
    sh /tmp/get-docker.sh

COPY requirements.txt /tmp/requirements.txt
RUN pip install -r /tmp/requirements.txt

COPY tests/requirements.txt /tmp/tests/requirements.txt
RUN pip install -r /tmp/tests/requirements.txt

COPY ./ /code
WORKDIR /code

CMD pytest -n auto --verbose tests/splunk_test.py
