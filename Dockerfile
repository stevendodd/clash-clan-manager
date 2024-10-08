FROM python:3.9-slim-buster

COPY requirements.txt requirements.txt
RUN pip3 install -r requirements.txt

ENV FLASK_APP=update
ENV PYTHONPATH=/clashpy

ADD static /static
COPY . .

EXPOSE 5000
CMD [ "python3", "-m" , "flask", "run", "--host=0.0.0.0"]