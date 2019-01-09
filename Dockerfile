FROM alpine:3.6

RUN apk add --update --no-cache --virtual=run-deps python3-dev build-base linux-headers pcre-dev uwsgi uwsgi-http uwsgi-python3 ca-certificates

RUN mkdir -p /opt/brilleaux

WORKDIR /opt/brilleaux

ENV BRILLEAUX_ELUCIDATE_URI placeholder

COPY requirements.txt /opt/brilleaux/.
RUN pip3 install -r requirements.txt

COPY *.json /opt/brilleaux/
COPY ./brilleaux_flask/*.py /opt/brilleaux/
COPY ./brilleaux_flask/*.html /opt/brilleaux/


CMD [ "uwsgi", "--plugins", "http,python3", \
               "--http", "0.0.0.0:5000", \
               "--protocol", "uwsgi", \
               "--enable-threads", \
               "--master", \
               "--http-timeout", "600", \
               "--lazy", \
               "--module", "brilleaux:app" ]