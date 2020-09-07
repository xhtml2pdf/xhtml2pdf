FROM python:3.7-buster
RUN mkdir code
WORKDIR /code

RUN apt-get update && \
    apt-get install -y imagemagick ghostscript

RUN apt-get update && \
    apt-get install -y vim

COPY requirements.txt /code/
RUN python -m pip install --no-cache-dir -r requirements.txt

RUN apt-get -y autoremove && \
    apt-get -y clean && \
    rm -rf /var/lib/apt/lists/*

COPY . /code/

RUN python setup.py install

CMD [ "python", "testrender/testrender.py" ]
