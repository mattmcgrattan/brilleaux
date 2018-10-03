FROM python:3-alpine

RUN apk add python3-dev build-base linux-headers pcre-dev uwsgi-python3

RUN mkdir -p /opt/brilleaux

WORKDIR /opt/brilleaux

ENV BRILLEAUX_ELUCIDATE_URI placeholder

COPY requirements.txt /opt/brilleaux/.
RUN pip install uwsgi
RUN pip install -r requirements.txt

COPY *.json /opt/brilleaux/
COPY ./brilleaux_flask/*.py /opt/brilleaux/

CMD [ "uwsgi", "--http", "0.0.0.0:5000", \
               "--uid", "uwsgi", \
               "--plugins", "python3", \
               "--protocol", "uwsgi", \
               "--enable-threads", \
               "--master", \
               "--module", "brilleaux:app" ]

