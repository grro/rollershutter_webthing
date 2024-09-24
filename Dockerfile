FROM python:3-alpine

ENV port 8343
ENV name ?
ENV devices ?
ENV reverse_directions 'false'

RUN cd /etc
RUN mkdir app
WORKDIR /etc/app
ADD *.py /etc/app/
ADD requirements.txt /etc/app/.
RUN pip install -r requirements.txt

CMD python /etc/app/rollershutter_webthing.py $port $name $devices $reverse_directions



