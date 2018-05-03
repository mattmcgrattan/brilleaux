FROM alpine:3.6

RUN apk add --update --no-cache --virtual=run-deps \
  uwsgi \
  uwsgi-python3 \
  python3 \
  nginx \
  ca-certificates

WORKDIR /opt/app
CMD ["/opt/app/run.sh"]

COPY run.sh /opt/app/
RUN chmod +x /opt/app/run.sh


COPY etc/nginx/default.conf /etc/nginx/conf.d/

COPY app/requirements.txt /opt/app/
RUN pip3 install --no-cache-dir -r /opt/app/requirements.txt

COPY app /opt/app/
RUN chmod +x /opt/app/*.py