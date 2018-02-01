FROM python:3-alpine

RUN mkdir -p /opt/brilleaux

WORKDIR /opt/brilleaux

ENV BRILLEAUX_ELUCIDATE_URI placeholder

COPY requirements.txt /opt/brilleaux/.
RUN pip install -r requirements.txt

COPY *.json /opt/brilleaux/
COPY *.py /opt/brilleaux/

CMD ["python", "-u", "./brilleaux.py"]

