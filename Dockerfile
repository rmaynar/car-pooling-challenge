FROM alpine:3.10

RUN apk add --no-cache python3-dev \
    && pip3 install --upgrade pip

EXPOSE 9091

COPY . /car-pooling-challenge
WORKDIR /car-pooling-challenge/api
RUN pip3 --no-cache-dir install -r ./requirements.txt
ENTRYPOINT ["python3"]
CMD ["app.py"]